#!/usr/bin/env python3
"""Read-only QSOL-ORACLE adapter for QSOL-CONTROL.

The adapter discovers and verifies a local ORACLE repository, exposes evidence-only
queries and timelock state, and can persist verified ORACLE payloads into a
separate CONTROL store by exact payload identity.

It intentionally has no ORACLE write path. CONTROL may cache references and exact
payload bytes, but it cannot append, rewrite, correct, supersede, or relabel the
ORACLE ledger through this adapter.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from storage.control_store import ControlStore, StorageError, canonical_json_bytes

ORACLE_PROTOCOL = "QSOL-ORACLE/1"
FEED_PROTOCOL = "QSOL-ORACLE-FEED/1"
TIMELOCK_PROTOCOL = "QSOL-TIMELOCK/1"
ADAPTER_PROTOCOL = "qsol-control-oracle-adapter/1"
QUERY_PROTOCOL = "qsol-control-oracle-evidence-response/1"
RECEIPT_REF_PROTOCOL = "qsol-control-oracle-receipt-ref/1"

MAX_MANIFEST_BYTES = 1024 * 1024
MAX_LEDGER_BYTES = 64 * 1024 * 1024
MAX_CONTRACT_BYTES = 1024 * 1024
MAX_RECEIPT_BYTES = 16 * 1024 * 1024
MAX_LEDGER_EVENTS = 100_000
MAX_SUGGESTED_SEARCHES = 32
DEFAULT_MAX_AGE_SECONDS = 24 * 60 * 60
PROTOCOL_RE = re.compile(r"^QSOL-ORACLE/([0-9]+)$")
SEMVER_RE = re.compile(r"^([0-9]+)\.([0-9]+)\.([0-9]+)$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RESPONSE_STATES = {"known", "conflict", "unknown"}
EVENT_EVIDENCE_STATES = {"observed", "conflict", "unknown"}
FRESHNESS_STATES = {"fresh", "stale", "undated", "future-dated"}
FORBIDDEN_SECRET_MARKERS = (
    "ghp_",
    "github_pat_",
    "Bearer ",
    "-----BEGIN PRIVATE KEY-----",
    "AKIA",
)


class OracleAdapterError(ValueError):
    """Raised when ORACLE discovery, integrity, or read-only boundaries fail."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_hash(value: Any) -> str:
    return _sha256(canonical_json_bytes(value))


def _parse_time(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise OracleAdapterError("timestamp must be a non-empty ISO-8601 string")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise OracleAdapterError("timestamp must be valid ISO-8601") from exc
    if parsed.tzinfo is None:
        raise OracleAdapterError("timestamp must include an explicit UTC offset")
    return parsed


def _normalize_time(value: str) -> str:
    return (
        _parse_time(value)
        .astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _read_bounded(path: Path, maximum: int, label: str) -> bytes:
    if path.is_symlink():
        raise OracleAdapterError(f"{label} must not be a symlink")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise OracleAdapterError(f"{label} is unavailable") from exc
    if size > maximum:
        raise OracleAdapterError(f"{label} exceeds byte limit")
    try:
        with path.open("rb") as handle:
            data = handle.read(maximum + 1)
    except OSError as exc:
        raise OracleAdapterError(f"{label} cannot be read") from exc
    if len(data) > maximum:
        raise OracleAdapterError(f"{label} exceeds byte limit")
    return data


def _json_object(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OracleAdapterError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise OracleAdapterError(f"{label} must contain a JSON object")
    return value


def _safe_relative(root: Path, relative: Any, label: str) -> Path:
    if not isinstance(relative, str) or not relative or len(relative) > 1024:
        raise OracleAdapterError(f"{label} must be a non-empty repository-relative path")
    if "\\" in relative or "\x00" in relative:
        raise OracleAdapterError(f"{label} contains a forbidden character")
    path = PurePosixPath(relative)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise OracleAdapterError(f"{label} is not a safe relative path")
    candidate = root.joinpath(*path.parts)
    try:
        resolved_root = root.resolve()
        resolved_candidate = candidate.resolve(strict=False)
    except OSError as exc:
        raise OracleAdapterError(f"{label} cannot be resolved") from exc
    if resolved_candidate != resolved_root and resolved_root not in resolved_candidate.parents:
        raise OracleAdapterError(f"{label} escapes the ORACLE root")
    return candidate


def _reject_obvious_secrets(value: Any, label: str) -> None:
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise OracleAdapterError(f"{label} must be JSON serializable") from exc
    for marker in FORBIDDEN_SECRET_MARKERS:
        if marker in text:
            raise OracleAdapterError(f"{label} contains a forbidden credential marker")


def _freshness(
    source_time: str | None,
    evaluated_at: str,
    max_age_seconds: int,
) -> dict[str, Any]:
    if not isinstance(max_age_seconds, int) or isinstance(max_age_seconds, bool) or max_age_seconds < 0:
        raise OracleAdapterError("max_age_seconds must be a non-negative integer")
    evaluated = _parse_time(evaluated_at).astimezone(timezone.utc)
    if source_time is None:
        return {
            "state": "undated",
            "source_time": None,
            "evaluated_at": _normalize_time(evaluated_at),
            "max_age_seconds": max_age_seconds,
            "age_seconds": None,
            "stale_means_false": False,
            "fresh_means_true": False,
        }
    source = _parse_time(source_time).astimezone(timezone.utc)
    age = int((evaluated - source).total_seconds())
    if age < 0:
        state = "future-dated"
    elif age <= max_age_seconds:
        state = "fresh"
    else:
        state = "stale"
    return {
        "state": state,
        "source_time": _normalize_time(source_time),
        "evaluated_at": _normalize_time(evaluated_at),
        "max_age_seconds": max_age_seconds,
        "age_seconds": age,
        "stale_means_false": False,
        "fresh_means_true": False,
    }


class OracleAdapter:
    """Fail-closed read-only adapter over one local QSOL-ORACLE repository."""

    def __init__(self, oracle_root: str | Path):
        self.root = Path(oracle_root)

    def _manifest(self) -> tuple[dict[str, Any], bytes]:
        path = self.root / "manifest.json"
        data = _read_bounded(path, MAX_MANIFEST_BYTES, "ORACLE manifest")
        manifest = _json_object(data, "ORACLE manifest")
        protocol = manifest.get("protocol")
        match = PROTOCOL_RE.fullmatch(protocol) if isinstance(protocol, str) else None
        if match is None or int(match.group(1)) != 1:
            raise OracleAdapterError("unsupported ORACLE protocol major")
        schema_version = manifest.get("schema_version")
        if not isinstance(schema_version, str) or SEMVER_RE.fullmatch(schema_version) is None:
            raise OracleAdapterError("ORACLE schema_version must use semantic versioning")
        if manifest.get("ledger_model") != "single-writer-append-only":
            raise OracleAdapterError("ORACLE ledger model must be single-writer-append-only")
        states = manifest.get("response_states")
        if not isinstance(states, list) or not RESPONSE_STATES.issubset(set(states)):
            raise OracleAdapterError("ORACLE manifest does not expose required response states")
        _safe_relative(self.root, manifest.get("ledger"), "ORACLE ledger path")
        if manifest.get("founding_timelock") is not None:
            _safe_relative(
                self.root, manifest.get("founding_timelock"), "ORACLE timelock path"
            )
        return manifest, data

    def discover(self) -> dict[str, Any]:
        manifest, manifest_bytes = self._manifest()
        capabilities = [
            "evidence-query-read-only",
            "ledger-integrity-verification",
            "receipt-payload-identity",
            "freshness-indicator",
        ]
        if manifest.get("founding_timelock"):
            capabilities.append("timelock-status")
        if manifest.get("feed_schema") and manifest.get("collectors"):
            capabilities.append("feed-receipt-verification")
        return {
            "protocol": ADAPTER_PROTOCOL,
            "availability": "available",
            "oracle_protocol": manifest["protocol"],
            "oracle_schema_version": manifest["schema_version"],
            "oracle_ledger_model": manifest["ledger_model"],
            "manifest_sha256": _sha256(manifest_bytes),
            "capabilities": capabilities,
            "write_capabilities": [],
            "authority": "none",
        }

    def availability(self) -> dict[str, Any]:
        try:
            discovery = self.discover()
            ledger = self._verified_ledger()
        except OracleAdapterError as exc:
            return {
                "protocol": ADAPTER_PROTOCOL,
                "availability": "unavailable",
                "reason": str(exc),
                "write_capabilities": [],
                "authority": "none",
            }
        return {
            **discovery,
            "ledger_events": len(ledger),
            "ledger_head": ledger[-1]["event_hash"],
        }

    def _verified_ledger(self) -> list[dict[str, Any]]:
        manifest, _ = self._manifest()
        ledger_path = _safe_relative(self.root, manifest["ledger"], "ORACLE ledger path")
        data = _read_bounded(ledger_path, MAX_LEDGER_BYTES, "ORACLE ledger")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise OracleAdapterError("ORACLE ledger is not UTF-8") from exc
        events: list[dict[str, Any]] = []
        for line_number, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line:
                continue
            if len(events) >= MAX_LEDGER_EVENTS:
                raise OracleAdapterError("ORACLE ledger exceeds event-count limit")
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise OracleAdapterError(
                    f"ORACLE ledger line {line_number} is invalid JSON"
                ) from exc
            if not isinstance(event, dict):
                raise OracleAdapterError(
                    f"ORACLE ledger line {line_number} must be an object"
                )
            events.append(event)
        if not events:
            raise OracleAdapterError("ORACLE ledger must contain a genesis event")

        provenance_kinds = manifest.get("provenance_kinds")
        if not isinstance(provenance_kinds, list) or not provenance_kinds:
            raise OracleAdapterError("ORACLE manifest provenance_kinds is invalid")
        allowed_provenance = set(provenance_kinds)

        previous: str | None = None
        seen_hashes: set[str] = set()
        seen_ids: set[str] = set()
        for index, event in enumerate(events):
            required = {
                "protocol", "sequence", "event_id", "event_type", "subject",
                "observed_at", "source", "provenance_kind", "evidence",
                "authority", "previous_hash", "note", "event_hash",
            }
            if not required.issubset(event):
                raise OracleAdapterError(f"ORACLE event {index} is missing required fields")
            if event.get("protocol") != ORACLE_PROTOCOL:
                raise OracleAdapterError(f"ORACLE event {index} protocol mismatch")
            if event.get("authority") != "observation-only":
                raise OracleAdapterError(f"ORACLE event {index} authority escalation")
            if event.get("sequence") != index:
                raise OracleAdapterError(f"ORACLE event {index} sequence mismatch")
            event_id = event.get("event_id")
            if not isinstance(event_id, str) or not event_id:
                raise OracleAdapterError(f"ORACLE event {index} event_id is invalid")
            if event_id in seen_ids:
                raise OracleAdapterError(f"ORACLE event {index} duplicates event_id")
            seen_ids.add(event_id)
            _parse_time(event.get("observed_at"))
            if not isinstance(event.get("event_type"), str) or not event["event_type"]:
                raise OracleAdapterError(f"ORACLE event {index} event_type is invalid")
            if not isinstance(event.get("subject"), str) or not event["subject"]:
                raise OracleAdapterError(f"ORACLE event {index} subject is invalid")
            source = event.get("source")
            if (
                not isinstance(source, dict)
                or not isinstance(source.get("kind"), str)
                or not source.get("kind")
                or not isinstance(source.get("locator"), str)
                or not source.get("locator")
            ):
                raise OracleAdapterError(f"ORACLE event {index} source is invalid")
            if event.get("provenance_kind") not in allowed_provenance:
                raise OracleAdapterError(f"ORACLE event {index} provenance kind is invalid")
            evidence = event.get("evidence")
            if (
                not isinstance(evidence, dict)
                or evidence.get("state") not in EVENT_EVIDENCE_STATES
            ):
                raise OracleAdapterError(f"ORACLE event {index} evidence state is invalid")
            payload_sha = evidence.get("payload_sha256")
            if payload_sha is not None and (
                not isinstance(payload_sha, str) or SHA256_RE.fullmatch(payload_sha) is None
            ):
                raise OracleAdapterError(
                    f"ORACLE event {index} payload_sha256 is invalid"
                )
            if event.get("previous_hash") != previous:
                raise OracleAdapterError(f"ORACLE event {index} previous_hash mismatch")
            derived_from = event.get("derived_from")
            if derived_from is not None:
                if (
                    not isinstance(derived_from, list)
                    or not derived_from
                    or len(derived_from) != len(set(derived_from))
                ):
                    raise OracleAdapterError(
                        f"ORACLE event {index} derived_from is invalid"
                    )
                for reference in derived_from:
                    if not isinstance(reference, str) or SHA256_RE.fullmatch(reference) is None:
                        raise OracleAdapterError(
                            f"ORACLE event {index} derived_from hash is invalid"
                        )
                    if reference not in seen_hashes:
                        raise OracleAdapterError(
                            f"ORACLE event {index} references non-earlier evidence"
                        )
            supplied_hash = event.get("event_hash")
            if not isinstance(supplied_hash, str) or SHA256_RE.fullmatch(supplied_hash) is None:
                raise OracleAdapterError(f"ORACLE event {index} event_hash is invalid")
            basis = dict(event)
            basis.pop("event_hash", None)
            expected_hash = _canonical_hash(basis)
            if supplied_hash != expected_hash:
                raise OracleAdapterError(f"ORACLE event {index} event_hash mismatch")
            seen_hashes.add(supplied_hash)
            previous = supplied_hash
        return events

    @staticmethod
    def _response_state(events: list[dict[str, Any]]) -> str:
        states = [event["evidence"]["state"] for event in events]
        if "conflict" in states:
            return "conflict"
        if any(
            event.get("provenance_kind") in {"correction", "supersession"}
            or event.get("event_type") in {"evidence.correction", "evidence.supersession"}
            for event in events
        ):
            return "unknown"
        if "observed" in states:
            return "known"
        return "unknown"

    @staticmethod
    def _event_ref(event: dict[str, Any]) -> dict[str, Any]:
        return {
            "event_id": event["event_id"],
            "event_hash": event["event_hash"],
            "event_type": event["event_type"],
            "subject": event["subject"],
            "observed_at": event["observed_at"],
            "source": event["source"],
            "provenance_kind": event["provenance_kind"],
            "evidence_state": event["evidence"]["state"],
            "payload_sha256": event["evidence"]["payload_sha256"],
            "authority": "oracle-observation-reference",
        }

    def query_evidence(
        self,
        subject: str,
        *,
        evaluated_at: str | None = None,
        max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
        suggested_searches: Iterable[str] = (),
    ) -> dict[str, Any]:
        if not isinstance(subject, str) or not subject.strip() or len(subject) > 2048:
            raise OracleAdapterError("subject must contain 1..2048 characters")
        searches = list(suggested_searches)
        if len(searches) > MAX_SUGGESTED_SEARCHES:
            raise OracleAdapterError("too many suggested searches")
        if (
            any(not isinstance(item, str) or not item.strip() or len(item) > 2048 for item in searches)
            or len(searches) != len(set(searches))
        ):
            raise OracleAdapterError("suggested searches must be unique non-empty strings")

        manifest, _ = self._manifest()
        events = self._verified_ledger()
        relevant = [event for event in events if event.get("subject") == subject]
        state = self._response_state(relevant)
        at = evaluated_at or datetime.now(timezone.utc).isoformat()
        source_time = relevant[-1]["observed_at"] if relevant else None
        refs = [self._event_ref(event) for event in relevant]
        ledger_head = events[-1]["event_hash"]
        result: dict[str, Any] = {
            "protocol": QUERY_PROTOCOL,
            "oracle_protocol": manifest["protocol"],
            "oracle_schema_version": manifest["schema_version"],
            "availability": "available",
            "subject": subject,
            "state": state,
            "evidence_refs": refs,
            "ledger_head": ledger_head,
            "freshness": _freshness(source_time, at, max_age_seconds),
            "suggested_searches": sorted(searches, key=lambda value: value.encode("utf-8")),
            "search_suggestions_are_evidence": False,
            "authority": "none",
        }
        if state == "unknown" and not relevant:
            result["missing_evidence"] = ["no canonical ORACLE event for exact subject"]
        elif state == "unknown":
            result["missing_evidence"] = ["canonical events do not establish an observed state"]
        else:
            result["missing_evidence"] = []
        result["response_sha256"] = _canonical_hash(result)
        return result

    def timelock_status(self, *, evaluated_at: str | None = None) -> dict[str, Any]:
        manifest, _ = self._manifest()
        relative = manifest.get("founding_timelock")
        if not isinstance(relative, str):
            raise OracleAdapterError("ORACLE manifest has no founding timelock")
        path = _safe_relative(self.root, relative, "ORACLE timelock path")
        data = _read_bounded(path, MAX_CONTRACT_BYTES, "ORACLE timelock")
        contract = _json_object(data, "ORACLE timelock")
        if contract.get("protocol") != TIMELOCK_PROTOCOL:
            raise OracleAdapterError("unsupported ORACLE timelock protocol")
        if contract.get("fail_closed") is not True:
            raise OracleAdapterError("ORACLE timelock is not fail-closed")
        not_before = contract.get("not_before")
        deadline = _parse_time(not_before)
        at_text = evaluated_at or datetime.now(timezone.utc).isoformat()
        at = _parse_time(at_text)
        state = "eligible" if at >= deadline else "locked"

        events = self._verified_ledger()
        contract_digest = _canonical_hash(contract)
        witnesses = [
            event
            for event in events
            if event.get("subject") == contract.get("subject")
            and event.get("evidence", {}).get("payload_sha256") == contract_digest
        ]
        result = {
            "protocol": ADAPTER_PROTOCOL,
            "oracle_protocol": manifest["protocol"],
            "contract_protocol": TIMELOCK_PROTOCOL,
            "contract_id": contract.get("contract_id"),
            "subject": contract.get("subject"),
            "evaluated_at": _normalize_time(at_text),
            "not_before": _normalize_time(not_before),
            "state": state,
            "contract_sha256": contract_digest,
            "witness_refs": [self._event_ref(event) for event in witnesses],
            "witnessed": bool(witnesses),
            "execution_authorized": False,
            "fail_closed": True,
            "authority": "none",
        }
        result["status_sha256"] = _canonical_hash(result)
        return result

    def validate_feed_receipt(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict) or payload.get("protocol") != FEED_PROTOCOL:
            raise OracleAdapterError("feed receipt protocol mismatch")
        collector = payload.get("collector")
        subject = payload.get("subject")
        if not isinstance(collector, str) or not collector.strip():
            raise OracleAdapterError("feed receipt collector must be non-empty")
        if not isinstance(subject, str) or not subject.strip():
            raise OracleAdapterError("feed receipt subject must be non-empty")
        source = payload.get("source")
        if not isinstance(source, dict):
            raise OracleAdapterError("feed receipt source must be an object")
        locator = source.get("locator")
        payload_sha = source.get("payload_sha256")
        if not isinstance(locator, str) or not locator.strip():
            raise OracleAdapterError("feed receipt source locator must be non-empty")
        if not isinstance(payload_sha, str) or SHA256_RE.fullmatch(payload_sha) is None:
            raise OracleAdapterError("feed receipt source payload SHA-256 is invalid")
        acquisition = payload.get("acquisition")
        if not isinstance(acquisition, dict) or acquisition.get("mode") not in {"fixture", "network"}:
            raise OracleAdapterError("feed receipt acquisition mode is invalid")
        if payload.get("authority") != "observation-only":
            raise OracleAdapterError("feed receipt authority must remain observation-only")
        if payload.get("truth_claim") is not False:
            raise OracleAdapterError("feed receipt must not claim semantic truth")
        freshness = payload.get("freshness")
        if (
            not isinstance(freshness, dict)
            or freshness.get("state") not in FRESHNESS_STATES
            or freshness.get("stale_means_false") is not False
            or freshness.get("fresh_means_true") is not False
        ):
            raise OracleAdapterError("feed receipt freshness semantics are invalid")
        evaluated_at = freshness.get("evaluated_at")
        if evaluated_at is not None:
            _parse_time(evaluated_at)
        source_time = freshness.get("source_time")
        if source_time is not None:
            _parse_time(source_time)
        observation = payload.get("observation")
        if not isinstance(observation, dict):
            raise OracleAdapterError("feed receipt observation must be an object")
        if payload.get("observation_sha256") != _canonical_hash(observation):
            raise OracleAdapterError("feed receipt observation SHA-256 mismatch")
        supplied = payload.get("receipt_sha256")
        if not isinstance(supplied, str) or SHA256_RE.fullmatch(supplied) is None:
            raise OracleAdapterError("feed receipt SHA-256 is invalid")
        basis = dict(payload)
        basis.pop("receipt_sha256", None)
        if supplied != _canonical_hash(basis):
            raise OracleAdapterError("feed receipt SHA-256 mismatch")
        return {
            "protocol": RECEIPT_REF_PROTOCOL,
            "oracle_protocol": FEED_PROTOCOL,
            "collector": collector,
            "subject": subject,
            "source_ref": f"oracle-feed:sha256:{supplied}",
            "payload_sha256": _canonical_hash(payload),
            "oracle_receipt_sha256": supplied,
            "freshness": freshness,
            "authority": "reference-only",
        }

    def _verify_cached_query_response(self, payload: dict[str, Any]) -> str:
        supplied = payload.get("response_sha256")
        if not isinstance(supplied, str) or SHA256_RE.fullmatch(supplied) is None:
            raise OracleAdapterError("CONTROL ORACLE response identity is invalid")
        basis = dict(payload)
        basis.pop("response_sha256", None)
        if supplied != _canonical_hash(basis):
            raise OracleAdapterError("CONTROL ORACLE response identity mismatch")

        ledger = self._verified_ledger()
        ledger_head = payload.get("ledger_head")
        head_index = next(
            (index for index, event in enumerate(ledger) if event["event_hash"] == ledger_head),
            None,
        )
        if head_index is None:
            raise OracleAdapterError("CONTROL ORACLE response ledger head is not in verified history")
        historical = ledger[: head_index + 1]
        subject = payload.get("subject")
        if not isinstance(subject, str) or not subject:
            raise OracleAdapterError("CONTROL ORACLE response subject is invalid")
        relevant = [event for event in historical if event.get("subject") == subject]
        expected_refs = [self._event_ref(event) for event in relevant]
        if payload.get("evidence_refs") != expected_refs:
            raise OracleAdapterError("CONTROL ORACLE response evidence references do not match verified history")
        if payload.get("state") != self._response_state(relevant):
            raise OracleAdapterError("CONTROL ORACLE response state does not match verified history")
        return supplied

    def _verify_cached_timelock_status(self, payload: dict[str, Any]) -> str:
        supplied = payload.get("status_sha256")
        if not isinstance(supplied, str) or SHA256_RE.fullmatch(supplied) is None:
            raise OracleAdapterError("ORACLE adapter status identity is invalid")
        basis = dict(payload)
        basis.pop("status_sha256", None)
        if supplied != _canonical_hash(basis):
            raise OracleAdapterError("ORACLE adapter status identity mismatch")
        evaluated_at = payload.get("evaluated_at")
        expected = self.timelock_status(evaluated_at=evaluated_at)
        if expected != payload:
            raise OracleAdapterError("ORACLE timelock status does not match verified parent state")
        return supplied

    def _verify_parent_timelock_contract(self, payload: dict[str, Any]) -> str:
        manifest, _ = self._manifest()
        relative = manifest.get("founding_timelock")
        if not isinstance(relative, str):
            raise OracleAdapterError("ORACLE manifest has no founding timelock")
        path = _safe_relative(self.root, relative, "ORACLE timelock path")
        canonical = _json_object(
            _read_bounded(path, MAX_CONTRACT_BYTES, "ORACLE timelock"),
            "ORACLE timelock",
        )
        if canonical != payload:
            raise OracleAdapterError("timelock receipt does not match the parent contract")
        if payload.get("protocol") != TIMELOCK_PROTOCOL or payload.get("fail_closed") is not True:
            raise OracleAdapterError("timelock receipt contract is invalid")
        digest = _canonical_hash(payload)
        ledger = self._verified_ledger()
        witnessed = any(
            event.get("subject") == payload.get("subject")
            and event.get("evidence", {}).get("payload_sha256") == digest
            for event in ledger
        )
        if not witnessed:
            raise OracleAdapterError("timelock receipt is not witnessed by verified ORACLE history")
        return digest

    def persist_receipt(
        self,
        control_root: str | Path,
        payload: dict[str, Any],
        *,
        source_ref: str,
        created_at: str,
        privacy_class: str = "INTERNAL",
    ) -> dict[str, Any]:
        if not isinstance(source_ref, str) or not source_ref.strip() or len(source_ref) > 2048:
            raise OracleAdapterError("source_ref must contain 1..2048 characters")
        _parse_time(created_at)
        oracle_root = self.root.resolve()
        control = Path(control_root).resolve()
        if (
            control == oracle_root
            or oracle_root in control.parents
            or control in oracle_root.parents
        ):
            raise OracleAdapterError(
                "CONTROL receipt storage must not overlap the ORACLE repository"
            )
        _reject_obvious_secrets(payload, "ORACLE receipt payload")
        raw = canonical_json_bytes(payload)
        if len(raw) > MAX_RECEIPT_BYTES:
            raise OracleAdapterError("ORACLE receipt exceeds storage byte limit")

        protocol = payload.get("protocol")
        if protocol == FEED_PROTOCOL:
            verified = self.validate_feed_receipt(payload)
            oracle_identity = verified["oracle_receipt_sha256"]
        elif protocol == ORACLE_PROTOCOL:
            supplied = payload.get("event_hash")
            if not isinstance(supplied, str) or SHA256_RE.fullmatch(supplied) is None:
                raise OracleAdapterError("ORACLE event receipt hash is invalid")
            basis = dict(payload)
            basis.pop("event_hash", None)
            if supplied != _canonical_hash(basis):
                raise OracleAdapterError("ORACLE event receipt hash mismatch")
            if payload.get("authority") != "observation-only":
                raise OracleAdapterError("ORACLE event receipt authority escalation")
            ledger = self._verified_ledger()
            canonical_event = next(
                (event for event in ledger if event["event_hash"] == supplied),
                None,
            )
            if canonical_event is None or canonical_json_bytes(canonical_event) != raw:
                raise OracleAdapterError("ORACLE event receipt is not present in verified parent history")
            oracle_identity = supplied
        elif protocol == QUERY_PROTOCOL:
            oracle_identity = self._verify_cached_query_response(payload)
        elif protocol == ADAPTER_PROTOCOL and "status_sha256" in payload:
            oracle_identity = self._verify_cached_timelock_status(payload)
        elif protocol == TIMELOCK_PROTOCOL:
            oracle_identity = self._verify_parent_timelock_contract(payload)
        else:
            raise OracleAdapterError("unsupported ORACLE receipt payload protocol")

        payload_sha = _sha256(raw)
        store = ControlStore(control)
        record = store.put_file(
            raw,
            filename=f"oracle-receipt-{payload_sha[:16]}.json",
            media_type="application/json",
            created_at=created_at,
            privacy_class=privacy_class,
            retention_class="ARCHIVE",
            source={"kind": "qsol-oracle-reference", "locator": source_ref},
            metadata={
                "protocol": RECEIPT_REF_PROTOCOL,
                "oracle_protocol": protocol,
                "source_ref": source_ref,
                "payload_sha256": payload_sha,
                "oracle_identity": oracle_identity,
                "authority": "reference-only",
                "copied_authority": False,
            },
        )
        return {
            "protocol": RECEIPT_REF_PROTOCOL,
            "file_id": record["file_id"],
            "object_id": record["object_id"],
            "source_ref": source_ref,
            "payload_sha256": payload_sha,
            "oracle_identity": oracle_identity,
            "authority": "reference-only",
        }
