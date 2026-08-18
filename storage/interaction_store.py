#!/usr/bin/env python3
"""Deterministic Phase-1B interaction and lattice persistence for QSOL-CONTROL.

This module layers append-only interaction/run persistence on top of the canonical
Phase-1A :class:`ControlStore`. It owns storage mechanics only. Lattice placement,
hash integrity, and lineage never confer evidence or truth authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator

from storage.control_store import (
    ControlStore,
    StorageError,
    canonical_json_bytes,
    sha256_ref,
)

SHA256_REF_RE = re.compile(r"^sha256:([0-9a-f]{64})$")
RUN_PROTOCOL = "qsol-control-interaction/2"
EVENT_PROTOCOL = "qsol-control-run-event/1"
RECORD_SET_PROTOCOL = "qsol-control-run-record-set/1"
FINGERPRINT_PROTOCOL = "qsol-control-run-fingerprint/1"
VERIFICATION_PROTOCOL = "qsol-control-run-verification/1"
LATTICE_PROFILE = "qsol-3x3x3-sierpinski-derived-memory/1"

INFORMATION_X = {"question": 0, "response": 1, "evidence": 2}
EPISTEMIC_Y = {"observed": 0, "derived": 1, "unresolved": 2}
TEMPORAL_Z = {"current": 0, "historical": 1, "recovery": 2}
EVENT_KINDS = {"question", "response", "evidence", "receipt", "model_state"}
MODES = {"evidence_only", "council"}
REQUESTER_KINDS = {"human", "ai", "system"}
EVIDENCE_STATES = {"known", "conflict", "unknown", "unavailable"}
REPLAYABILITY = {"R0", "R1", "R2", "R3"}
PRIVACY_CLASSES = {"PUBLIC", "INTERNAL", "RESTRICTED"}
PRIVACY_RANK = {"PUBLIC": 0, "INTERNAL": 1, "RESTRICTED": 2}
FORBIDDEN_SECRET_MARKERS = (
    "ghp_",
    "github_pat_",
    "Bearer ",
    "-----BEGIN PRIVATE KEY-----",
    "AKIA",
)
MAX_IMPORTED_EVENTS = 100_000
MAX_RECORD_SET_BYTES = 16 * 1024 * 1024

RUN_KEYS = {
    "run_id", "protocol", "question_sha256", "question", "mode", "requester_kind",
    "created_at", "evidence_state", "oracle_refs", "nexus_refs", "record_refs",
    "file_ids", "collection_ref", "model_state_refs", "lattice_refs",
    "lattice_profile", "replayability", "authority",
}
QUESTION_KEYS = {"text", "sha256", "lattice_address", "epistemic_role", "temporal_role"}
EVENT_KEYS = {
    "event_id", "protocol", "run_id", "sequence", "previous_event_id",
    "parent_event_ids", "kind", "occurred_at", "epistemic_role", "temporal_role",
    "lattice_address", "file_ids", "record_refs", "payload", "authority",
}
MODEL_STATE_KEYS = {
    "protocol", "state_id", "captured_at", "model", "execution", "system",
    "hidden_chain_of_thought_captured",
}
MODEL_KEYS = {
    "provider", "runtime", "runtime_version", "model_id", "revision", "weight_hash",
    "tokenizer_identity", "quantization", "metadata_provenance",
}
EXECUTION_KEYS = {
    "council_seat", "mode", "stochastic", "seed", "context_limit", "sampling",
    "tool_permissions",
}
SYSTEM_KEYS = {
    "control_run_id", "nexus_identity", "oracle_refs", "substrate_identity",
    "hardware_runtime_metadata",
}
MODEL_PROVENANCE = {
    "observed", "provider_reported", "locally_verified", "inferred", "unknown",
}


def _validate_timestamp(value: str) -> str:
    if not isinstance(value, str):
        raise StorageError("timestamp must be an ISO-8601 string")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise StorageError("timestamp must be valid ISO-8601") from exc
    if parsed.tzinfo is None:
        raise StorageError("timestamp must include an explicit UTC offset")
    return value


def _digest(reference: str, *, field: str = "content reference") -> str:
    if not isinstance(reference, str):
        raise StorageError(f"{field} must be a sha256 reference")
    match = SHA256_REF_RE.fullmatch(reference)
    if match is None:
        raise StorageError(f"invalid {field}: {reference!r}")
    return match.group(1)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temp_path = Path(handle.name)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StorageError(f"cannot read canonical JSON record: {path}") from exc
    if not isinstance(value, dict):
        raise StorageError(f"canonical record must be an object: {path}")
    return value


def _reject_obvious_secrets(value: Any, field: str) -> None:
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise StorageError(f"{field} must be JSON serializable") from exc
    for marker in FORBIDDEN_SECRET_MARKERS:
        if marker in text:
            raise StorageError(f"{field} contains forbidden credential marker")


def _sorted_refs(values: Iterable[str], *, field: str) -> list[str]:
    normalized = list(values)
    if any(not isinstance(value, str) for value in normalized):
        raise StorageError(f"{field} must contain only sha256 references")
    if len(normalized) != len(set(normalized)):
        raise StorageError(f"{field} must not contain duplicate identities")
    for value in normalized:
        _digest(value, field=field)
    return sorted(normalized, key=lambda value: value.encode("ascii"))


def _sorted_strings(values: Iterable[str], *, field: str) -> list[str]:
    normalized = list(values)
    if any(not isinstance(value, str) or not value for value in normalized):
        raise StorageError(f"{field} must contain non-empty strings")
    if len(normalized) != len(set(normalized)):
        raise StorageError(f"{field} must not contain duplicates")
    return sorted(normalized, key=lambda value: value.encode("utf-8"))


def lattice_address(information_role: str, epistemic_role: str, temporal_role: str) -> str:
    try:
        x = INFORMATION_X[information_role]
    except KeyError as exc:
        raise StorageError("information_role must be question, response, or evidence") from exc
    try:
        y = EPISTEMIC_Y[epistemic_role]
    except KeyError as exc:
        raise StorageError("unknown epistemic_role") from exc
    try:
        z = TEMPORAL_Z[temporal_role]
    except KeyError as exc:
        raise StorageError("unknown temporal_role") from exc
    return f"L[{x},{y},{z}]"


class InteractionStore:
    """Append-only run/event persistence backed by a Phase-1A ControlStore."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.storage = ControlStore(self.root)
        self.runs = self.root / "records" / "runs"
        self.events = self.root / "records" / "run-events"
        self.run_heads = self.root / "records" / "run-heads"
        self.locks = self.root / ".locks"
        for path in (self.runs, self.events, self.run_heads, self.locks):
            path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _identity(payload: dict[str, Any]) -> str:
        return sha256_ref(canonical_json_bytes(payload))

    def _run_path(self, run_id: str) -> Path:
        return self.runs / f"{_digest(run_id, field='run_id')}.json"

    def _event_path(self, event_id: str) -> Path:
        return self.events / f"{_digest(event_id, field='event_id')}.json"

    def _head_path(self, run_id: str) -> Path:
        return self.run_heads / f"{_digest(run_id, field='run_id')}.json"

    def _lock_path(self, run_id: str) -> Path:
        digest = _sha256_hex(f"run:{_digest(run_id, field='run_id')}".encode("ascii"))
        return self.locks / f"{digest}.lock"

    @contextmanager
    def _exclusive_run_lock(self, run_id: str) -> Iterator[None]:
        path = self._lock_path(run_id)
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise StorageError(f"writer lock already held for run {run_id}") from exc
        try:
            os.write(fd, b"qsol-control-run-single-writer-lock\n")
            os.fsync(fd)
        finally:
            os.close(fd)
        try:
            yield
        finally:
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    def _empty_head(self, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "event_id": None, "sequence": -1}

    def _run_has_event_records(self, run_id: str) -> bool:
        for path in self.events.glob("*.json"):
            try:
                event = _read_json(path)
            except StorageError:
                continue
            if event.get("run_id") == run_id:
                return True
        return False

    def _validate_store_refs(self, *, file_ids: Iterable[str], collection_id: str | None,
                             snapshot_id: str | None) -> tuple[list[str], dict[str, str] | None]:
        ordered_files = _sorted_refs(file_ids, field="file_ids")
        for file_id in ordered_files:
            self.storage.get_file_record(file_id)
        collection_ref = None
        if (collection_id is None) != (snapshot_id is None):
            raise StorageError("collection_id and snapshot_id must be supplied together")
        if collection_id is not None and snapshot_id is not None:
            _digest(collection_id, field="collection_id")
            _digest(snapshot_id, field="snapshot_id")
            self.storage.get_collection_snapshot(collection_id, snapshot_id)
            collection_ref = {"collection_id": collection_id, "snapshot_id": snapshot_id}
        return ordered_files, collection_ref

    def create_run(self, *, question: str, mode: str, requester_kind: str, created_at: str,
                   evidence_state: str = "unknown", file_ids: Iterable[str] = (),
                   collection_id: str | None = None, snapshot_id: str | None = None,
                   oracle_refs: Iterable[str] = (), nexus_refs: Iterable[str] = (),
                   model_state_refs: Iterable[str] = (), replayability: str = "R3") -> dict[str, Any]:
        if not isinstance(question, str) or not question.strip():
            raise StorageError("question must be a non-empty string")
        _reject_obvious_secrets(question, "question")
        if mode not in MODES:
            raise StorageError("mode must be evidence_only or council")
        if requester_kind not in REQUESTER_KINDS:
            raise StorageError("unknown requester_kind")
        if evidence_state not in EVIDENCE_STATES:
            raise StorageError("unknown evidence_state")
        if replayability not in REPLAYABILITY:
            raise StorageError("unknown replayability class")
        timestamp = _validate_timestamp(created_at)
        ordered_files, collection_ref = self._validate_store_refs(
            file_ids=file_ids, collection_id=collection_id, snapshot_id=snapshot_id)
        ordered_models = _sorted_refs(model_state_refs, field="model_state_refs")
        oracle = _sorted_strings(oracle_refs, field="oracle_refs")
        nexus = _sorted_strings(nexus_refs, field="nexus_refs")
        if evidence_state != "unknown" and not oracle:
            raise StorageError("non-unknown evidence_state requires at least one ORACLE provenance reference")
        question_sha256 = _sha256_hex(question.encode("utf-8"))
        question_lattice = lattice_address("question", "derived", "current")
        record_refs: list[str] = list(ordered_files)
        if collection_ref is not None:
            record_refs.extend([collection_ref["collection_id"], collection_ref["snapshot_id"]])
        if not record_refs:
            record_refs = [f"question:sha256:{question_sha256}"]
        payload: dict[str, Any] = {
            "protocol": RUN_PROTOCOL,
            "question_sha256": question_sha256,
            "question": {"text": question, "sha256": question_sha256,
                         "lattice_address": question_lattice, "epistemic_role": "derived",
                         "temporal_role": "current"},
            "mode": mode, "requester_kind": requester_kind, "created_at": timestamp,
            "evidence_state": evidence_state, "oracle_refs": oracle, "nexus_refs": nexus,
            "record_refs": record_refs, "file_ids": ordered_files, "collection_ref": collection_ref,
            "model_state_refs": ordered_models, "lattice_refs": [question_lattice],
            "lattice_profile": LATTICE_PROFILE, "replayability": replayability,
            "authority": "storage-only",
        }
        run_id = self._identity(payload)
        record = {"run_id": run_id, **payload}
        path = self._run_path(run_id)
        encoded = canonical_json_bytes(record)
        with self._exclusive_run_lock(run_id):
            if path.exists():
                if path.read_bytes() != encoded:
                    raise StorageError("run identity collision detected")
                self._validate_run_semantics(record)
                head_path = self._head_path(run_id)
                if not head_path.is_file():
                    if self._run_has_event_records(run_id):
                        raise StorageError("existing run is missing HEAD while event records still exist")
                    _atomic_write(head_path, canonical_json_bytes(self._empty_head(run_id)))
                else:
                    self._read_head(run_id)
                return record
            _atomic_write(path, encoded)
            _atomic_write(self._head_path(run_id), canonical_json_bytes(self._empty_head(run_id)))
        return record

    def get_run(self, run_id: str) -> dict[str, Any]:
        path = self._run_path(run_id)
        if not path.is_file():
            raise StorageError(f"unknown run_id: {run_id}")
        record = _read_json(path)
        if record.get("run_id") != run_id:
            raise StorageError("run record/path identity mismatch")
        payload = {key: value for key, value in record.items() if key != "run_id"}
        if self._identity(payload) != run_id:
            raise StorageError("run record content identity mismatch")
        self._validate_run_semantics(record)
        return record

    def _validate_run_semantics(self, record: dict[str, Any]) -> None:
        if set(record) != RUN_KEYS:
            raise StorageError("run record fields do not match qsol-control-interaction/2")
        if record.get("protocol") != RUN_PROTOCOL:
            raise StorageError("unknown interaction protocol")
        if record.get("authority") != "storage-only":
            raise StorageError("interaction authority must remain storage-only")
        if record.get("mode") not in MODES:
            raise StorageError("invalid run mode")
        if record.get("requester_kind") not in REQUESTER_KINDS:
            raise StorageError("invalid requester_kind")
        evidence_state = record.get("evidence_state")
        if evidence_state not in EVIDENCE_STATES:
            raise StorageError("invalid evidence_state")
        if record.get("replayability") not in REPLAYABILITY:
            raise StorageError("invalid replayability")
        _validate_timestamp(record.get("created_at"))
        question = record.get("question")
        if not isinstance(question, dict) or set(question) != QUESTION_KEYS:
            raise StorageError("run question does not match the canonical question object")
        text = question.get("text")
        if not isinstance(text, str) or not text.strip():
            raise StorageError("run question text must be non-empty")
        _reject_obvious_secrets(text, "run question")
        digest = _sha256_hex(text.encode("utf-8"))
        if digest != record.get("question_sha256") or digest != question.get("sha256"):
            raise StorageError("question content hash mismatch")
        if question.get("epistemic_role") != "derived" or question.get("temporal_role") != "current":
            raise StorageError("canonical run question must be derived/current")
        expected_address = lattice_address("question", question.get("epistemic_role"),
                                           question.get("temporal_role"))
        if question.get("lattice_address") != expected_address:
            raise StorageError("question lattice address is not deterministic from recorded roles")
        if record.get("lattice_profile") != LATTICE_PROFILE:
            raise StorageError("unknown lattice profile")
        if record.get("lattice_refs") != [expected_address]:
            raise StorageError("run lattice_refs must contain exactly the canonical question address")
        oracle = record.get("oracle_refs")
        nexus = record.get("nexus_refs")
        if not isinstance(oracle, list) or oracle != _sorted_strings(oracle, field="oracle_refs"):
            raise StorageError("oracle_refs are not in canonical order")
        if not isinstance(nexus, list) or nexus != _sorted_strings(nexus, field="nexus_refs"):
            raise StorageError("nexus_refs are not in canonical order")
        if evidence_state != "unknown" and not oracle:
            raise StorageError("non-unknown evidence_state requires at least one ORACLE provenance reference")
        file_ids = record.get("file_ids")
        if not isinstance(file_ids, list) or file_ids != _sorted_refs(file_ids, field="file_ids"):
            raise StorageError("file_ids are not in canonical order")
        for file_id in file_ids:
            self.storage.get_file_record(file_id)
        collection_ref = record.get("collection_ref")
        if collection_ref is not None:
            if not isinstance(collection_ref, dict) or set(collection_ref) != {"collection_id", "snapshot_id"}:
                raise StorageError("collection_ref must contain exact collection/snapshot identities")
            collection_id = collection_ref.get("collection_id")
            snapshot_id = collection_ref.get("snapshot_id")
            _digest(collection_id, field="collection_id")
            _digest(snapshot_id, field="snapshot_id")
            self.storage.get_collection_snapshot(collection_id, snapshot_id)
        model_refs = record.get("model_state_refs")
        if not isinstance(model_refs, list) or model_refs != _sorted_refs(model_refs, field="model_state_refs"):
            raise StorageError("model_state_refs are not in canonical order")
        refs = record.get("record_refs")
        if (not isinstance(refs, list) or not refs or
                any(not isinstance(value, str) or not value for value in refs) or
                len(refs) != len(set(refs))):
            raise StorageError("record_refs must be a non-empty unique string array")
        _reject_obvious_secrets(refs, "run record_refs")

    def _read_head(self, run_id: str) -> dict[str, Any]:
        head = _read_json(self._head_path(run_id))
        if set(head) != {"run_id", "event_id", "sequence"}:
            raise StorageError("run HEAD contains unexpected fields")
        if head.get("run_id") != run_id:
            raise StorageError("run HEAD belongs to a different run")
        event_id = head.get("event_id")
        sequence = head.get("sequence")
        if event_id is None:
            if sequence != -1:
                raise StorageError("empty run HEAD must use sequence -1")
        else:
            _digest(event_id, field="event_id")
            if not isinstance(sequence, int) or sequence < 0:
                raise StorageError("run HEAD sequence must be non-negative")
        return head

    @staticmethod
    def _validate_model_state_payload(payload: dict[str, Any], *, run_id: str) -> None:
        if set(payload) != MODEL_STATE_KEYS:
            raise StorageError("model_state payload does not match qsol-control-model-state/1")
        if payload.get("protocol") != "qsol-control-model-state/1":
            raise StorageError("model_state protocol mismatch")
        _digest(payload.get("state_id"), field="model_state state_id")
        _validate_timestamp(payload.get("captured_at"))
        if payload.get("hidden_chain_of_thought_captured") is not False:
            raise StorageError("model_state must never capture hidden chain-of-thought")
        model = payload.get("model")
        if not isinstance(model, dict) or not {"provider", "runtime", "model_id"} <= set(model):
            raise StorageError("model_state model descriptor is incomplete")
        if not set(model) <= MODEL_KEYS:
            raise StorageError("model_state model contains unexpected fields")
        for field in ("provider", "runtime", "model_id"):
            if not isinstance(model[field], str) or not model[field]:
                raise StorageError(f"model_state model.{field} must be non-empty")
        provenance = model.get("metadata_provenance")
        if provenance is not None and provenance not in MODEL_PROVENANCE:
            raise StorageError("model_state metadata_provenance is invalid")
        execution = payload.get("execution")
        if not isinstance(execution, dict) or not set(execution) <= EXECUTION_KEYS:
            raise StorageError("model_state execution descriptor is invalid")
        context_limit = execution.get("context_limit")
        if context_limit is not None and (not isinstance(context_limit, int) or context_limit < 1):
            raise StorageError("model_state context_limit is invalid")
        sampling = execution.get("sampling")
        if sampling is not None and not isinstance(sampling, dict):
            raise StorageError("model_state sampling must be an object")
        permissions = execution.get("tool_permissions")
        if permissions is not None:
            if (not isinstance(permissions, list) or any(not isinstance(item, str) for item in permissions)
                    or len(permissions) != len(set(permissions))):
                raise StorageError("model_state tool_permissions must be unique strings")
        system = payload.get("system")
        if not isinstance(system, dict) or "control_run_id" not in system:
            raise StorageError("model_state system descriptor is incomplete")
        if not set(system) <= SYSTEM_KEYS:
            raise StorageError("model_state system contains unexpected fields")
        _digest(system.get("control_run_id"), field="model_state control_run_id")
        if system.get("control_run_id") != run_id:
            raise StorageError("model_state control_run_id must match the containing run")
        oracle_refs = system.get("oracle_refs")
        if oracle_refs is not None:
            _sorted_strings(oracle_refs, field="model_state oracle_refs")
        hardware = system.get("hardware_runtime_metadata")
        if hardware is not None and not isinstance(hardware, dict):
            raise StorageError("model_state hardware_runtime_metadata must be an object")
        _reject_obvious_secrets(payload, "model_state payload")

    def _validate_event_semantics(self, event: dict[str, Any], *, require_store_refs: bool = True) -> None:
        if set(event) != EVENT_KEYS:
            raise StorageError("run event fields do not match qsol-control-run-event/1")
        if event.get("protocol") != EVENT_PROTOCOL:
            raise StorageError("unknown run event protocol")
        if event.get("authority") != "storage-only":
            raise StorageError("run event authority must remain storage-only")
        run_id = event.get("run_id")
        _digest(run_id, field="run_id")
        event_id = event.get("event_id")
        _digest(event_id, field="event_id")
        sequence = event.get("sequence")
        if not isinstance(sequence, int) or sequence < 0:
            raise StorageError("event sequence must be a non-negative integer")
        previous = event.get("previous_event_id")
        if previous is not None:
            _digest(previous, field="previous_event_id")
        parents = event.get("parent_event_ids")
        if not isinstance(parents, list) or parents != _sorted_refs(parents, field="parent_event_ids"):
            raise StorageError("parent_event_ids are not in canonical order")
        kind = event.get("kind")
        if kind not in EVENT_KINDS:
            raise StorageError("unknown event kind")
        _validate_timestamp(event.get("occurred_at"))
        payload = event.get("payload")
        if not isinstance(payload, dict):
            raise StorageError("event payload must be an object")
        _reject_obvious_secrets(payload, "event payload")
        if kind == "model_state":
            self._validate_model_state_payload(payload, run_id=run_id)
        file_ids = event.get("file_ids")
        if not isinstance(file_ids, list) or file_ids != _sorted_refs(file_ids, field="file_ids"):
            raise StorageError("event file_ids are not in canonical order")
        if require_store_refs:
            for file_id in file_ids:
                self.storage.get_file_record(file_id)
        refs = event.get("record_refs")
        if not isinstance(refs, list) or any(not isinstance(value, str) or not value for value in refs):
            raise StorageError("event record_refs must be an array of non-empty strings")
        if refs != sorted(set(refs), key=lambda value: value.encode("utf-8")):
            raise StorageError("event record_refs must be unique and canonically ordered")
        _reject_obvious_secrets(refs, "event record_refs")
        if kind in INFORMATION_X:
            epistemic_role = event.get("epistemic_role")
            temporal_role = event.get("temporal_role")
            expected = lattice_address(kind, epistemic_role, temporal_role)
            if event.get("lattice_address") != expected:
                raise StorageError("event lattice address is not deterministic from recorded roles")
            if epistemic_role == "derived" and not (parents or file_ids or refs):
                raise StorageError("derived events require explicit input lineage references")
        else:
            if event.get("lattice_address") is not None:
                raise StorageError("receipt/model_state events do not claim a top-level Q/R/E lattice cell")
            if event.get("epistemic_role") is not None or event.get("temporal_role") is not None:
                raise StorageError("non-Q/R/E events must not invent lattice-axis roles")
        basis = {key: value for key, value in event.items() if key != "event_id"}
        if self._identity(basis) != event_id:
            raise StorageError("run event content identity mismatch")

    def get_event(self, event_id: str) -> dict[str, Any]:
        path = self._event_path(event_id)
        if not path.is_file():
            raise StorageError(f"unknown event_id: {event_id}")
        event = _read_json(path)
        if event.get("event_id") != event_id:
            raise StorageError("event record/path identity mismatch")
        self._validate_event_semantics(event)
        return event

    def append_event(self, run_id: str, *, kind: str, payload: dict[str, Any], occurred_at: str,
                     epistemic_role: str | None = None, temporal_role: str | None = None,
                     parent_event_ids: Iterable[str] | None = None, file_ids: Iterable[str] = (),
                     record_refs: Iterable[str] = ()) -> dict[str, Any]:
        self.get_run(run_id)
        if kind not in EVENT_KINDS:
            raise StorageError("unknown event kind")
        if not isinstance(payload, dict):
            raise StorageError("event payload must be an object")
        _reject_obvious_secrets(payload, "event payload")
        if kind == "model_state":
            self._validate_model_state_payload(payload, run_id=run_id)
        timestamp = _validate_timestamp(occurred_at)
        ordered_files = _sorted_refs(file_ids, field="file_ids")
        for file_id in ordered_files:
            self.storage.get_file_record(file_id)
        ordered_record_refs = _sorted_strings(record_refs, field="record_refs")
        _reject_obvious_secrets(ordered_record_refs, "record_refs")
        if kind in INFORMATION_X:
            if epistemic_role is None or temporal_role is None:
                raise StorageError("question/response/evidence events require epistemic and temporal roles")
            address = lattice_address(kind, epistemic_role, temporal_role)
        else:
            if epistemic_role is not None or temporal_role is not None:
                raise StorageError("receipt/model_state events do not use Q/R/E lattice-axis roles")
            address = None
        with self._exclusive_run_lock(run_id):
            head = self._read_head(run_id)
            previous_event_id = head["event_id"]
            sequence = head["sequence"] + 1
            if parent_event_ids is None:
                parents = [] if previous_event_id is None else [previous_event_id]
            else:
                parents = _sorted_refs(parent_event_ids, field="parent_event_ids")
            if kind in INFORMATION_X and epistemic_role == "derived" and not (
                    parents or ordered_files or ordered_record_refs):
                raise StorageError("derived events require explicit input lineage references")
            for parent in parents:
                parent_event = self.get_event(parent)
                if parent_event.get("run_id") != run_id:
                    raise StorageError("lineage parent belongs to a different run")
                if parent_event.get("sequence", -1) >= sequence:
                    raise StorageError("lineage parent must precede the appended event")
            basis = {
                "protocol": EVENT_PROTOCOL, "run_id": run_id, "sequence": sequence,
                "previous_event_id": previous_event_id, "parent_event_ids": parents,
                "kind": kind, "occurred_at": timestamp, "epistemic_role": epistemic_role,
                "temporal_role": temporal_role, "lattice_address": address,
                "file_ids": ordered_files, "record_refs": ordered_record_refs,
                "payload": payload, "authority": "storage-only",
            }
            event_id = self._identity(basis)
            event = {"event_id": event_id, **basis}
            path = self._event_path(event_id)
            encoded = canonical_json_bytes(event)
            if path.exists():
                if path.read_bytes() != encoded:
                    raise StorageError("run event identity collision detected")
            else:
                _atomic_write(path, encoded)
            _atomic_write(self._head_path(run_id), canonical_json_bytes(
                {"run_id": run_id, "event_id": event_id, "sequence": sequence}))
        return event

    def _list_events_from_head(self, run_id: str, head: dict[str, Any]) -> list[dict[str, Any]]:
        if head["event_id"] is None:
            return []
        events: list[dict[str, Any]] = []
        cursor = head["event_id"]
        expected_sequence = head["sequence"]
        seen: set[str] = set()
        while cursor is not None:
            if cursor in seen:
                raise StorageError("run previous-event lineage loop detected")
            seen.add(cursor)
            event = self.get_event(cursor)
            if event.get("run_id") != run_id:
                raise StorageError("run event belongs to a different run")
            if event.get("sequence") != expected_sequence:
                raise StorageError("run event sequence chain is discontinuous")
            events.append(event)
            cursor = event.get("previous_event_id")
            expected_sequence -= 1
        if expected_sequence != -1:
            raise StorageError("run event chain terminated before sequence zero")
        events.reverse()
        return events

    def list_events(self, run_id: str) -> list[dict[str, Any]]:
        self.get_run(run_id)
        return self._list_events_from_head(run_id, self._read_head(run_id))

    @staticmethod
    def _check_parent_dag(events: list[dict[str, Any]]) -> None:
        by_id = {event["event_id"]: event for event in events}
        state: dict[str, int] = {}
        for root in by_id:
            if state.get(root) == 2:
                continue
            stack: list[tuple[str, bool]] = [(root, False)]
            while stack:
                event_id, exiting = stack.pop()
                if exiting:
                    state[event_id] = 2
                    continue
                current = state.get(event_id, 0)
                if current == 1:
                    raise StorageError("run event lineage loop detected")
                if current == 2:
                    continue
                state[event_id] = 1
                stack.append((event_id, True))
                event = by_id[event_id]
                for parent in reversed(event["parent_event_ids"]):
                    if parent not in by_id:
                        raise StorageError("run event references a missing lineage parent")
                    parent_state = state.get(parent, 0)
                    if parent_state == 1:
                        raise StorageError("run event lineage loop detected")
                    if parent_state != 2:
                        stack.append((parent, False))

    def _capture_run_state(self, run_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        with self._exclusive_run_lock(run_id):
            run = self.get_run(run_id)
            head = self._read_head(run_id)
            events = self._list_events_from_head(run_id, head)
        return run, events

    def _verify_bound_objects(self, run: dict[str, Any], events: list[dict[str, Any]]) -> None:
        checked: set[str] = set()
        for file_id in run["file_ids"]:
            if file_id not in checked:
                self.storage.read_file(file_id)
                checked.add(file_id)
        collection_ref = run["collection_ref"]
        if collection_ref is not None:
            snapshot = self.storage.get_collection_snapshot(
                collection_ref["collection_id"], collection_ref["snapshot_id"])
            for file_id in snapshot["members"]:
                if file_id not in checked:
                    self.storage.read_file(file_id)
                    checked.add(file_id)
        for event in events:
            for file_id in event["file_ids"]:
                if file_id not in checked:
                    self.storage.read_file(file_id)
                    checked.add(file_id)

    def _strictest_privacy(self, run: dict[str, Any], events: list[dict[str, Any]]) -> str:
        classes = ["PUBLIC"]
        def add_file(file_id: str) -> None:
            privacy = self.storage.get_file_record(file_id).get("privacy_class")
            if privacy not in PRIVACY_CLASSES:
                raise StorageError("referenced File has unknown privacy class")
            classes.append(privacy)
        for file_id in run["file_ids"]:
            add_file(file_id)
        collection_ref = run["collection_ref"]
        if collection_ref is not None:
            collection = self.storage.get_collection(collection_ref["collection_id"])
            privacy = collection.get("privacy_class")
            if privacy not in PRIVACY_CLASSES:
                raise StorageError("referenced Collection has unknown privacy class")
            classes.append(privacy)
            snapshot = self.storage.get_collection_snapshot(
                collection_ref["collection_id"], collection_ref["snapshot_id"])
            for file_id in snapshot["members"]:
                add_file(file_id)
        for event in events:
            for file_id in event["file_ids"]:
                add_file(file_id)
        return max(classes, key=lambda value: PRIVACY_RANK[value])

    def _fingerprint_from_snapshot(self, run: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
        inventory = {
            "protocol": FINGERPRINT_PROTOCOL, "run_id": run["run_id"],
            "run_record_sha256": _sha256_hex(canonical_json_bytes(run)),
            "event_ids": [event["event_id"] for event in events],
            "event_record_sha256": [_sha256_hex(canonical_json_bytes(event)) for event in events],
            "file_ids": run["file_ids"], "collection_ref": run["collection_ref"],
            "lattice_profile": run["lattice_profile"], "authority": "integrity-not-truth",
        }
        return {**inventory, "fingerprint": self._identity(inventory)}

    def _verify_snapshot(self, run: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
        self._check_parent_dag(events)
        by_id = {event["event_id"]: event for event in events}
        for event in events:
            for parent_id in event["parent_event_ids"]:
                if by_id[parent_id]["sequence"] >= event["sequence"]:
                    raise StorageError("lineage parent must precede child sequence")
        self._verify_bound_objects(run, events)
        fingerprint = self._fingerprint_from_snapshot(run, events)
        return {"protocol": VERIFICATION_PROTOCOL, "status": "valid", "run_id": run["run_id"],
                "events": len(events), "file_ids": len(run["file_ids"]),
                "collection_snapshot_id": (run["collection_ref"]["snapshot_id"]
                    if run["collection_ref"] is not None else None),
                "fingerprint": fingerprint["fingerprint"]}

    def verify_run(self, run_id: str) -> dict[str, Any]:
        run, events = self._capture_run_state(run_id)
        return self._verify_snapshot(run, events)

    def fingerprint_run(self, run_id: str) -> dict[str, Any]:
        run, events = self._capture_run_state(run_id)
        self._verify_bound_objects(run, events)
        return self._fingerprint_from_snapshot(run, events)

    def export_record_set(self, run_id: str) -> dict[str, Any]:
        run, events = self._capture_run_state(run_id)
        self._verify_snapshot(run, events)
        return {"protocol": RECORD_SET_PROTOCOL, "privacy_class": self._strictest_privacy(run, events),
                "run": run, "events": events}

    def import_record_set(self, record_set: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(record_set, dict) or record_set.get("protocol") != RECORD_SET_PROTOCOL:
            raise StorageError("unknown run record-set protocol")
        if set(record_set) != {"protocol", "privacy_class", "run", "events"}:
            raise StorageError("run record-set contains unexpected fields")
        if len(canonical_json_bytes(record_set)) > MAX_RECORD_SET_BYTES:
            raise StorageError("run record-set exceeds import byte limit")
        run = record_set.get("run")
        events = record_set.get("events")
        privacy_class = record_set.get("privacy_class")
        if privacy_class not in PRIVACY_CLASSES:
            raise StorageError("run record-set privacy_class is invalid")
        if not isinstance(run, dict) or not isinstance(events, list):
            raise StorageError("run record-set must contain run object and events array")
        if len(events) > MAX_IMPORTED_EVENTS:
            raise StorageError("run record-set exceeds event count limit")
        run_id = run.get("run_id")
        _digest(run_id, field="run_id")
        payload = {key: value for key, value in run.items() if key != "run_id"}
        if self._identity(payload) != run_id:
            raise StorageError("imported run identity mismatch")
        self._validate_run_semantics(run)
        seen_ids: set[str] = set()
        by_sequence: dict[int, dict[str, Any]] = {}
        by_id: dict[str, dict[str, Any]] = {}
        for event in events:
            if not isinstance(event, dict):
                raise StorageError("imported event must be an object")
            event_id = event.get("event_id")
            _digest(event_id, field="event_id")
            if event_id in seen_ids:
                raise StorageError("duplicate event identity in import")
            seen_ids.add(event_id)
            self._validate_event_semantics(event)
            if event.get("run_id") != run_id:
                raise StorageError("imported event belongs to a different run")
            sequence = event["sequence"]
            if sequence in by_sequence:
                raise StorageError("duplicate event sequence in import")
            by_sequence[sequence] = event
            by_id[event_id] = event
        ordered = [by_sequence[index] for index in sorted(by_sequence)]
        if ordered and [event["sequence"] for event in ordered] != list(range(len(ordered))):
            raise StorageError("imported event sequence must be contiguous from zero")
        for index, event in enumerate(ordered):
            expected_previous = None if index == 0 else ordered[index - 1]["event_id"]
            if event.get("previous_event_id") != expected_previous:
                raise StorageError("imported previous-event chain is discontinuous")
            for parent_id in event["parent_event_ids"]:
                parent = by_id.get(parent_id)
                if parent is None:
                    raise StorageError("imported event references missing lineage parent")
                if parent["sequence"] >= event["sequence"]:
                    raise StorageError("imported lineage parent must precede child")
        self._check_parent_dag(ordered)
        if privacy_class != self._strictest_privacy(run, ordered):
            raise StorageError("run record-set privacy_class does not match referenced storage")
        run_path = self._run_path(run_id)
        with self._exclusive_run_lock(run_id):
            if run_path.exists() and run_path.read_bytes() != canonical_json_bytes(run):
                raise StorageError("run identity collision during import")
            if run_path.exists():
                head_path = self._head_path(run_id)
                if not head_path.is_file():
                    raise StorageError("existing run is missing its HEAD record")
                current_events = self._list_events_from_head(run_id, self._read_head(run_id))
                current_ids = [event["event_id"] for event in current_events]
                imported_ids = [event["event_id"] for event in ordered]
                if len(imported_ids) < len(current_ids):
                    raise StorageError("import would truncate append-only run history")
                if imported_ids[:len(current_ids)] != current_ids:
                    raise StorageError("import would rewrite or roll back append-only run history")
            else:
                _atomic_write(run_path, canonical_json_bytes(run))
            for event in ordered:
                path = self._event_path(event["event_id"])
                encoded_event = canonical_json_bytes(event)
                if path.exists() and path.read_bytes() != encoded_event:
                    raise StorageError("event identity collision during import")
                if not path.exists():
                    _atomic_write(path, encoded_event)
            head = {"run_id": run_id, "event_id": ordered[-1]["event_id"] if ordered else None,
                    "sequence": ordered[-1]["sequence"] if ordered else -1}
            _atomic_write(self._head_path(run_id), canonical_json_bytes(head))
        return self.verify_run(run_id)
