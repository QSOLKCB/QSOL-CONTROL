#!/usr/bin/env python3
"""Local JSONL/stdio adapter from QSOL-CONTROL to QSOL-NEXUS.

CONTROL may invoke NEXUS Council execution and preserve externally visible
artifacts. NEXUS remains authoritative for WorldStore history, roster semantics,
phase ordering, ballot contents, vote weight, consensus thresholds, receipts,
and governance.

This module never requests or stores hidden chain-of-thought. Phase submissions,
ballot rationales, receipts, and other values accepted here are public/runtime-
visible NEXUS outputs only.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import select
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Sequence

from storage.control_store import ControlStore, StorageError, canonical_json_bytes
from storage.interaction_store import InteractionStore

ADAPTER_PROTOCOL = "qsol-control-nexus-adapter/1"
DISCOVERY_PROTOCOL = "qsol-control-nexus-discovery/1"
COUNCIL_RESPONSE_PROTOCOL = "qsol-control-nexus-council-response/1"
RECEIPT_REF_PROTOCOL = "qsol-control-nexus-receipt-ref/1"
SUPPORTED_NEXUS_PROTOCOL_MAJOR = 0
NEXUS_PROTOCOL_RE = re.compile(r"^nexus/([0-9]+)\.([0-9]+)$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
OBJECT_REF_RE = re.compile(r"^object:[0-9a-f]{64}$")
BALLOT_REF_RE = re.compile(r"^ballot:[0-9a-f]{64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

MAX_REQUEST_BYTES = 4 * 1024 * 1024
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
MAX_MEMBERS = 32
MAX_EVIDENCE_REFS = 4096
MAX_QUESTION_CHARS = 32768
MAX_COMMAND_ARGS = 128
MAX_ARG_CHARS = 8192
DEFAULT_TIMEOUT_SECONDS = 1800.0

REQUIRED_OPERATIONS = (
    "system.health",
    "system.operations",
    "council.run",
    "world.inspect",
    "receipt.verify",
)
READ_OPERATIONS_USED = frozenset(
    {
        "system.health",
        "system.operations",
        "world.inspect",
        "receipt.verify",
        "council.epoch.verify",
    }
)
MUTATION_OPERATIONS_EXPOSED = ("council.run",)

FORBIDDEN_GOVERNANCE_FIELDS = frozenset(
    {
        "vote_weight",
        "epistemic_privilege",
        "ballot",
        "ballots",
        "ballot_commitment",
        "ballot_commitments",
        "consensus_threshold",
        "consensus_numerator",
        "consensus_denominator",
        "roster_authority",
        "worldstore",
        "world_store",
        "world_state",
    }
)
FORBIDDEN_REASONING_KEYS = frozenset(
    {
        "chain_of_thought",
        "chain-of-thought",
        "hidden_chain_of_thought",
        "hidden_reasoning",
        "private_reasoning",
        "internal_reasoning",
        "reasoning_trace",
        "scratchpad",
        "private_scratchpad",
    }
)
FORBIDDEN_SECRET_MARKERS = (
    "ghp_",
    "github_pat_",
    "Bearer ",
    "-----BEGIN PRIVATE KEY-----",
    "AKIA",
)


class NexusAdapterError(ValueError):
    """Raised when transport, discovery, integrity, or governance checks fail."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_hash(value: Any) -> str:
    return _sha256(canonical_json_bytes(value))


def _nexus_ref(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(
        prefix.encode("utf-8") + b"\0" + canonical_json_bytes(value)
    ).hexdigest()
    return f"{prefix}:{digest}"


def _validate_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise NexusAdapterError(f"{label} must be a JSON object")
    return value


def _validate_ref(value: Any, label: str) -> str:
    if not isinstance(value, str) or OBJECT_REF_RE.fullmatch(value) is None:
        raise NexusAdapterError(
            f"{label} must be an object: reference with exactly 64 lowercase hex digits"
        )
    return value


def _reject_obvious_secrets(value: Any, label: str) -> None:
    try:
        text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise NexusAdapterError(f"{label} must be bounded JSON data") from exc
    for marker in FORBIDDEN_SECRET_MARKERS:
        if marker in text:
            raise NexusAdapterError(f"{label} contains forbidden credential material")


def _reject_hidden_reasoning(value: Any, label: str) -> None:
    stack: list[Any] = [value]
    visited = 0
    while stack:
        current = stack.pop()
        visited += 1
        if visited > 1_000_000:
            raise NexusAdapterError(f"{label} exceeds reasoning-scan node limit")
        if isinstance(current, dict):
            for key, item in current.items():
                if not isinstance(key, str):
                    raise NexusAdapterError(f"{label} contains a non-string object key")
                if key.casefold() in FORBIDDEN_REASONING_KEYS:
                    raise NexusAdapterError(
                        f"{label} exposes forbidden hidden-reasoning field {key!r}"
                    )
                stack.append(item)
        elif isinstance(current, list):
            stack.extend(current)


def _reject_governance_controls(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise NexusAdapterError(f"{label} must be an object")
    stack: list[tuple[str, Any]] = [(label, value)]
    while stack:
        path, current = stack.pop()
        if isinstance(current, dict):
            for key, item in current.items():
                if not isinstance(key, str):
                    raise NexusAdapterError(f"{path} contains a non-string object key")
                if key.casefold() in FORBIDDEN_GOVERNANCE_FIELDS:
                    raise NexusAdapterError(
                        f"CONTROL does not expose NEXUS governance field {key!r}"
                    )
                stack.append((f"{path}.{key}", item))
        elif isinstance(current, list):
            for index, item in enumerate(current):
                stack.append((f"{path}[{index}]", item))


def _validate_world_object(raw: Any, expected_ref: str, expected_type: str) -> dict[str, Any]:
    obj = _validate_object(raw, "NEXUS WorldStore object")
    if set(obj) != {"object_id", "object_type", "payload", "provenance"}:
        raise NexusAdapterError("NEXUS WorldStore object schema is invalid")
    if obj.get("object_id") != expected_ref:
        raise NexusAdapterError("NEXUS WorldStore object/ref mismatch")
    if obj.get("object_type") != expected_type:
        raise NexusAdapterError(
            f"NEXUS WorldStore object is not expected type {expected_type!r}"
        )
    if not isinstance(obj.get("payload"), dict) or not isinstance(obj.get("provenance"), dict):
        raise NexusAdapterError("NEXUS WorldStore object has invalid payload/provenance")
    expected = _nexus_ref(
        "object",
        {
            "object_type": obj["object_type"],
            "payload": obj["payload"],
            "provenance": obj["provenance"],
        },
    )
    if expected != expected_ref:
        raise NexusAdapterError("NEXUS WorldStore object failed content-address verification")
    return obj


class _JsonlStdioTransport:
    """One persistent local subprocess carrying one JSON object per stdio line."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        cwd: str | Path | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        command_values = list(command)
        if not command_values or len(command_values) > MAX_COMMAND_ARGS:
            raise NexusAdapterError("NEXUS command must contain 1..128 arguments")
        if any(
            not isinstance(item, str)
            or not item
            or len(item) > MAX_ARG_CHARS
            or "\x00" in item
            for item in command_values
        ):
            raise NexusAdapterError("NEXUS command contains an invalid argument")
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or timeout_seconds <= 0
        ):
            raise NexusAdapterError("timeout_seconds must be a positive number")
        self.command = tuple(command_values)
        self.cwd = None if cwd is None else Path(cwd)
        self.timeout_seconds = float(timeout_seconds)
        self._process: subprocess.Popen[bytes] | None = None
        self._stdout_buffer = bytearray()

    def start(self) -> None:
        if self._process is not None:
            return
        try:
            self._process = subprocess.Popen(
                self.command,
                cwd=None if self.cwd is None else str(self.cwd),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                shell=False,
                bufsize=0,
            )
        except OSError as exc:
            raise NexusAdapterError("local NEXUS JSONL process could not be started") from exc
        if self._process.stdin is None or self._process.stdout is None:
            self.close()
            raise NexusAdapterError("local NEXUS JSONL process lacks stdio pipes")

    def request(self, request: dict[str, Any]) -> dict[str, Any]:
        self.start()
        assert self._process is not None
        assert self._process.stdin is not None
        raw = canonical_json_bytes(request) + b"\n"
        if len(raw) > MAX_REQUEST_BYTES:
            raise NexusAdapterError("NEXUS JSONL request exceeds CONTROL byte limit")
        if self._process.poll() is not None:
            raise NexusAdapterError("local NEXUS JSONL process exited unexpectedly")
        try:
            self._process.stdin.write(raw)
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise NexusAdapterError("local NEXUS JSONL request pipe failed") from exc
        response_bytes = self._read_line()
        try:
            response = json.loads(response_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise NexusAdapterError("local NEXUS returned invalid UTF-8 JSON") from exc
        if not isinstance(response, dict):
            raise NexusAdapterError("local NEXUS response must be a JSON object")
        return response

    def _read_line(self) -> bytes:
        assert self._process is not None
        assert self._process.stdout is not None
        deadline = time.monotonic() + self.timeout_seconds
        fd = self._process.stdout.fileno()
        while True:
            newline = self._stdout_buffer.find(b"\n")
            if newline >= 0:
                line = bytes(self._stdout_buffer[:newline])
                del self._stdout_buffer[: newline + 1]
                if len(line) > MAX_RESPONSE_BYTES:
                    raise NexusAdapterError("NEXUS JSONL response exceeds CONTROL byte limit")
                return line
            if len(self._stdout_buffer) > MAX_RESPONSE_BYTES:
                raise NexusAdapterError("NEXUS JSONL response exceeds CONTROL byte limit")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise NexusAdapterError("NEXUS JSONL response timed out")
            ready, _, _ = select.select([fd], [], [], remaining)
            if not ready:
                raise NexusAdapterError("NEXUS JSONL response timed out")
            try:
                chunk = os.read(fd, min(65536, MAX_RESPONSE_BYTES + 1))
            except OSError as exc:
                raise NexusAdapterError("NEXUS JSONL response pipe failed") from exc
            if not chunk:
                code = self._process.poll()
                raise NexusAdapterError(
                    f"local NEXUS JSONL process ended before a response line (code={code})"
                )
            self._stdout_buffer.extend(chunk)

    def close(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        try:
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
        except OSError:
            pass
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2.0)


class NexusCouncilAdapter:
    """Governance-preserving CONTROL facade over the NEXUS JSONL control plane."""

    def __init__(self, transport: Any, *, owns_transport: bool = False) -> None:
        if not callable(getattr(transport, "request", None)):
            raise NexusAdapterError("NEXUS transport must provide request(object)")
        self._transport = transport
        self._owns_transport = owns_transport
        self._counter = 0
        self._discovery: dict[str, Any] | None = None

    @classmethod
    def from_command(
        cls,
        command: Sequence[str],
        *,
        cwd: str | Path | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> "NexusCouncilAdapter":
        return cls(
            _JsonlStdioTransport(command, cwd=cwd, timeout_seconds=timeout_seconds),
            owns_transport=True,
        )

    def __enter__(self) -> "NexusCouncilAdapter":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_transport:
            close = getattr(self._transport, "close", None)
            if callable(close):
                close()

    def _request(self, operation: str, **fields: Any) -> dict[str, Any]:
        self._counter += 1
        request_id = f"control-nexus-{self._counter:08d}"
        request = {"request_id": request_id, "operation": operation, **fields}
        response = self._transport.request(request)
        if response.get("request_id") not in {None, request_id}:
            raise NexusAdapterError("NEXUS response request_id mismatch")
        if response.get("status") == "error":
            error = response.get("error")
            code = error.get("code") if isinstance(error, dict) else "unknown_error"
            message = error.get("message") if isinstance(error, dict) else "NEXUS operation failed"
            raise NexusAdapterError(f"NEXUS {operation} failed [{code}]: {message}")
        if response.get("status") not in {"ok", "verified"}:
            raise NexusAdapterError(f"NEXUS {operation} returned unsupported status")
        return response

    def discover(self, *, refresh: bool = True) -> dict[str, Any]:
        if self._discovery is not None and not refresh:
            return copy.deepcopy(self._discovery)
        health = self._request("system.health")
        operations_response = self._request("system.operations")

        protocol = health.get("protocol")
        match = NEXUS_PROTOCOL_RE.fullmatch(protocol) if isinstance(protocol, str) else None
        if match is None or int(match.group(1)) != SUPPORTED_NEXUS_PROTOCOL_MAJOR:
            raise NexusAdapterError("unsupported NEXUS protocol major")
        runtime_version = health.get("runtime_version")
        if not isinstance(runtime_version, str) or SEMVER_RE.fullmatch(runtime_version) is None:
            raise NexusAdapterError("NEXUS runtime_version must use semantic versioning")
        if health.get("control_transport") != "jsonl_stdio":
            raise NexusAdapterError("NEXUS did not advertise the required jsonl_stdio transport")

        operations = operations_response.get("operations")
        if (
            not isinstance(operations, list)
            or not all(isinstance(item, str) and item for item in operations)
            or len(operations) != len(set(operations))
        ):
            raise NexusAdapterError("NEXUS system.operations response is invalid")
        missing = [operation for operation in REQUIRED_OPERATIONS if operation not in operations]
        if missing:
            raise NexusAdapterError(
                "NEXUS does not advertise required CONTROL operations: " + ", ".join(missing)
            )

        discovery = {
            "protocol": DISCOVERY_PROTOCOL,
            "availability": "available",
            "nexus_protocol": protocol,
            "nexus_runtime_version": runtime_version,
            "control_transport": health["control_transport"],
            "operations": list(operations),
            "operations_sha256": _canonical_hash(operations),
            "required_operations": list(REQUIRED_OPERATIONS),
            "optional_epoch_verification": "council.epoch.verify" in operations,
            "health": copy.deepcopy(health),
            "adapter_mutation_operations": list(MUTATION_OPERATIONS_EXPOSED),
            "direct_worldstore_mutation_exposed": False,
            "governance_override_operations": [],
            "hidden_chain_of_thought_capture": False,
            "authority": "none",
        }
        _reject_hidden_reasoning(discovery, "NEXUS discovery")
        self._discovery = discovery
        return copy.deepcopy(discovery)

    def run_council(
        self,
        *,
        question: str,
        members: Sequence[dict[str, Any]],
        evidence_refs: Iterable[str] = (),
        evidence_state: str = "UNTESTED",
        mode: str = "analytical",
        control_root: str | Path | None = None,
        control_run_id: str | None = None,
        created_at: str | None = None,
        privacy_class: str = "INTERNAL",
    ) -> dict[str, Any]:
        discovery = self.discover(refresh=True)
        self._validate_question(question)
        requested_members = self._validate_members(members)
        admitted_evidence = self._validate_evidence_refs(evidence_refs)
        if not isinstance(evidence_state, str) or not evidence_state or len(evidence_state) > 128:
            raise NexusAdapterError("evidence_state must be bounded non-empty text")
        if not isinstance(mode, str) or not mode or len(mode) > 128:
            raise NexusAdapterError("mode must be bounded non-empty text")
        _reject_obvious_secrets(
            {
                "question": question,
                "members": requested_members,
                "evidence_refs": admitted_evidence,
                "evidence_state": evidence_state,
                "mode": mode,
            },
            "NEXUS Council request",
        )

        run_response = self._request(
            "council.run",
            question=question,
            members=requested_members,
            evidence_refs=admitted_evidence,
            evidence_state=evidence_state,
            mode=mode,
        )
        session_ref = _validate_ref(run_response.get("session_ref"), "session_ref")
        receipt_ref = _validate_ref(run_response.get("receipt_ref"), "receipt_ref")

        session_object = self._inspect_world(session_ref, "council_session")
        receipt_object = self._inspect_world(receipt_ref, "receipt")
        receipt_verification = self._request("receipt.verify", receipt_ref=receipt_ref)

        epoch_ref = run_response.get("epoch_admission_receipt_ref")
        epoch_object: dict[str, Any] | None = None
        epoch_verification: dict[str, Any] | None = None
        if epoch_ref is not None:
            epoch_ref = _validate_ref(epoch_ref, "epoch_admission_receipt_ref")
            if not discovery["optional_epoch_verification"]:
                raise NexusAdapterError(
                    "NEXUS returned an epoch admission receipt without advertising verification"
                )
            epoch_object = self._inspect_world(epoch_ref, "council_epoch_admission_receipt")
            epoch_verification = self._request("council.epoch.verify", receipt_ref=epoch_ref)

        rendered = self._validate_and_render(
            discovery=discovery,
            requested_evidence_refs=admitted_evidence,
            requested_evidence_state=evidence_state,
            run_response=run_response,
            session_object=session_object,
            receipt_object=receipt_object,
            receipt_verification=receipt_verification,
            epoch_object=epoch_object,
            epoch_verification=epoch_verification,
        )

        if control_root is not None:
            if created_at is None:
                raise NexusAdapterError("created_at is required when persisting NEXUS artifacts")
            storage = self._persist_artifacts(
                control_root=control_root,
                control_run_id=control_run_id,
                created_at=created_at,
                privacy_class=privacy_class,
                run_response=run_response,
                session_object=session_object,
                receipt_object=receipt_object,
                receipt_verification=receipt_verification,
                rendered=rendered,
                epoch_object=epoch_object,
                epoch_verification=epoch_verification,
            )
            rendered = {**rendered, "storage": storage}
            basis = {key: value for key, value in rendered.items() if key != "response_sha256"}
            rendered["response_sha256"] = _canonical_hash(basis)
        return rendered

    @staticmethod
    def _validate_question(question: Any) -> None:
        if (
            not isinstance(question, str)
            or not question.strip()
            or len(question) > MAX_QUESTION_CHARS
        ):
            raise NexusAdapterError(
                f"question must contain 1..{MAX_QUESTION_CHARS} characters"
            )

    @staticmethod
    def _validate_members(members: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        values = list(members)
        if not values or len(values) > MAX_MEMBERS:
            raise NexusAdapterError(f"Council members must contain 1..{MAX_MEMBERS} seats")
        output: list[dict[str, Any]] = []
        ids: set[str] = set()
        for index, item in enumerate(values):
            if not isinstance(item, dict):
                raise NexusAdapterError(f"Council member {index} must be an object")
            _reject_governance_controls(item, f"Council member {index}")
            member_id = item.get("member_id")
            model_id = item.get("model_id")
            if not isinstance(member_id, str) or not member_id or len(member_id) > 256:
                raise NexusAdapterError(f"Council member {index} member_id is invalid")
            if not isinstance(model_id, str) or not model_id or len(model_id) > 512:
                raise NexusAdapterError(f"Council member {index} model_id is invalid")
            if member_id in ids:
                raise NexusAdapterError("Council member_id values must be unique")
            ids.add(member_id)
            output.append(copy.deepcopy(item))
        return output

    @staticmethod
    def _validate_evidence_refs(values: Iterable[str]) -> list[str]:
        refs = list(values)
        if len(refs) > MAX_EVIDENCE_REFS:
            raise NexusAdapterError("too many admitted evidence references")
        if len(refs) != len(set(refs)):
            raise NexusAdapterError("admitted evidence references must be unique")
        for ref in refs:
            _validate_ref(ref, "evidence_ref")
        return refs

    def _inspect_world(self, object_ref: str, expected_type: str) -> dict[str, Any]:
        response = self._request("world.inspect", object_ref=object_ref)
        obj = response.get("object")
        return _validate_world_object(obj, object_ref, expected_type)

    def _validate_and_render(
        self,
        *,
        discovery: dict[str, Any],
        requested_evidence_refs: list[str],
        requested_evidence_state: str,
        run_response: dict[str, Any],
        session_object: dict[str, Any],
        receipt_object: dict[str, Any],
        receipt_verification: dict[str, Any],
        epoch_object: dict[str, Any] | None,
        epoch_verification: dict[str, Any] | None,
    ) -> dict[str, Any]:
        for label, value in (
            ("council.run response", run_response),
            ("council_session", session_object),
            ("receipt", receipt_object),
            ("receipt verification", receipt_verification),
        ):
            _reject_hidden_reasoning(value, f"NEXUS {label}")

        session_ref = session_object["object_id"]
        receipt_ref = receipt_object["object_id"]
        payload = session_object["payload"]
        session_id = payload.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise NexusAdapterError("NEXUS council_session session_id is invalid")
        if run_response.get("session_id") != session_id:
            raise NexusAdapterError("council.run/session session_id mismatch")
        if run_response.get("session_ref") != session_ref:
            raise NexusAdapterError("council.run/session_ref mismatch")
        if run_response.get("receipt_ref") != receipt_ref:
            raise NexusAdapterError("council.run/receipt_ref mismatch")

        roster = payload.get("roster")
        policy = payload.get("policy")
        if not isinstance(roster, list) or not roster or not all(isinstance(row, dict) for row in roster):
            raise NexusAdapterError("NEXUS canonical roster is invalid")
        if not isinstance(policy, dict):
            raise NexusAdapterError("NEXUS Council policy is invalid")
        roster_ids: list[str] = []
        for row in roster:
            member_id = row.get("member_id")
            if not isinstance(member_id, str) or not member_id:
                raise NexusAdapterError("NEXUS canonical roster member_id is invalid")
            if member_id in roster_ids:
                raise NexusAdapterError("NEXUS canonical roster contains duplicate member_id")
            roster_ids.append(member_id)
            if type(row.get("vote_weight")) is not int or row.get("vote_weight") != 1:
                raise NexusAdapterError("NEXUS canonical roster changed ordinary vote weight")
            if row.get("epistemic_privilege") != "none":
                raise NexusAdapterError("NEXUS canonical roster changed epistemic privilege")

        if type(policy.get("vote_weight")) is not int or policy.get("vote_weight") != 1:
            raise NexusAdapterError("NEXUS Council policy changed ordinary vote weight")
        numerator = policy.get("consensus_numerator")
        denominator = policy.get("consensus_denominator")
        if (
            type(numerator) is not int
            or type(denominator) is not int
            or numerator <= 0
            or denominator <= 0
            or numerator > denominator
        ):
            raise NexusAdapterError("NEXUS consensus policy is invalid")
        phase_order = policy.get("phase_order")
        if (
            not isinstance(phase_order, list)
            or not phase_order
            or not all(isinstance(item, str) and item for item in phase_order)
            or len(phase_order) != len(set(phase_order))
        ):
            raise NexusAdapterError("NEXUS canonical phase order is invalid")
        if policy.get("ballot_sealed") is not True:
            raise NexusAdapterError("NEXUS Council did not preserve sealed-ballot policy")

        phase_submissions = payload.get("phase_submissions")
        if not isinstance(phase_submissions, dict) or set(phase_submissions) != set(phase_order):
            raise NexusAdapterError("NEXUS phase submissions do not match canonical phase order")
        rendered_phases: list[dict[str, Any]] = []
        for phase in phase_order:
            records = phase_submissions[phase]
            if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
                raise NexusAdapterError(f"NEXUS phase {phase} submissions are invalid")
            member_order = [item.get("member_id") for item in records]
            if member_order != roster_ids:
                raise NexusAdapterError(
                    f"NEXUS phase {phase} did not preserve canonical roster join order"
                )
            if any(item.get("phase") != phase for item in records):
                raise NexusAdapterError(f"NEXUS phase {phase} record label mismatch")
            rendered_phases.append(
                {"phase": phase, "submissions": copy.deepcopy(records)}
            )

        commitments = payload.get("ballot_commitments")
        revealed = payload.get("revealed_ballots")
        if (
            not isinstance(commitments, list)
            or not isinstance(revealed, list)
            or not all(isinstance(item, dict) for item in commitments + revealed)
        ):
            raise NexusAdapterError("NEXUS sealed-ballot records are invalid")
        if [item.get("member_id") for item in commitments] != roster_ids:
            raise NexusAdapterError("NEXUS ballot commitments changed canonical roster order")
        if [item.get("member_id") for item in revealed] != roster_ids:
            raise NexusAdapterError("NEXUS revealed ballots changed canonical roster order")
        if len(commitments) != len(revealed):
            raise NexusAdapterError("NEXUS ballot commitment/reveal count mismatch")
        for commitment, ballot in zip(commitments, revealed):
            supplied = commitment.get("commitment")
            if not isinstance(supplied, str) or BALLOT_REF_RE.fullmatch(supplied) is None:
                raise NexusAdapterError("NEXUS ballot commitment is invalid")
            if ballot.get("commitment") != supplied:
                raise NexusAdapterError("NEXUS ballot reveal does not match commitment record")
            expected = _nexus_ref(
                "ballot",
                {
                    "session_id": session_id,
                    "member_id": ballot.get("member_id"),
                    "choice": ballot.get("choice"),
                    "rationale": ballot.get("rationale"),
                },
            )
            if expected != supplied:
                raise NexusAdapterError("NEXUS revealed ballot failed commitment verification")

        result = payload.get("result")
        if not isinstance(result, dict):
            raise NexusAdapterError("NEXUS Council result is invalid")
        if run_response.get("result") != result:
            raise NexusAdapterError("council.run result differs from canonical session result")
        threshold = result.get("consensus_threshold")
        if threshold != {"numerator": numerator, "denominator": denominator}:
            raise NexusAdapterError("NEXUS result consensus threshold differs from session policy")
        choices = [ballot.get("choice") for ballot in revealed]
        if any(not isinstance(choice, str) or not choice for choice in choices):
            raise NexusAdapterError("NEXUS revealed ballot choice is invalid")
        expected_tally = dict(sorted(Counter(choices).items()))
        if result.get("tally") != expected_tally:
            raise NexusAdapterError("NEXUS result tally differs from revealed ballots")
        if result.get("evidence_state") != requested_evidence_state:
            raise NexusAdapterError("NEXUS result evidence_state differs from submitted state")

        minority_reports = result.get("minority_reports")
        if not isinstance(minority_reports, list) or not all(
            isinstance(item, dict) for item in minority_reports
        ):
            raise NexusAdapterError("NEXUS minority reports are invalid")
        disposition = result.get("disposition")
        expected_minority = [
            {
                "member_id": ballot.get("member_id"),
                "choice": ballot.get("choice"),
                "rationale": ballot.get("rationale"),
            }
            for ballot in revealed
            if disposition == "NO_SINGLE_DISPOSITION" or ballot.get("choice") != disposition
        ]
        if minority_reports != expected_minority:
            raise NexusAdapterError("NEXUS minority reports differ from revealed ballot record")

        evidence_snapshot_ref = _validate_ref(
            run_response.get("evidence_snapshot_ref"), "evidence_snapshot_ref"
        )
        session_evidence_ref = payload.get("evidence_snapshot_ref")
        if session_evidence_ref != evidence_snapshot_ref:
            raise NexusAdapterError("NEXUS session evidence snapshot reference mismatch")
        evidence_snapshot = self._inspect_world(evidence_snapshot_ref, "evidence_snapshot")
        included_refs = evidence_snapshot["payload"].get("included_object_refs")
        if included_refs != requested_evidence_refs:
            raise NexusAdapterError("NEXUS evidence snapshot changed admitted evidence references")
        if evidence_snapshot["payload"].get("evidence_state") != requested_evidence_state:
            raise NexusAdapterError("NEXUS evidence snapshot changed admitted evidence state")

        receipt_payload = receipt_object["payload"]
        if receipt_payload.get("operation") != "council.run":
            raise NexusAdapterError("NEXUS receipt does not bind council.run")
        if receipt_payload.get("result_ref") != session_ref:
            raise NexusAdapterError("NEXUS receipt result_ref differs from council session")
        replayable = receipt_payload.get("replayable")
        if type(replayable) is not bool:
            raise NexusAdapterError("NEXUS receipt replayable field is invalid")
        if receipt_payload.get("protocol") != discovery["nexus_protocol"]:
            raise NexusAdapterError("NEXUS receipt protocol differs from discovered runtime")
        if receipt_verification.get("status") != "verified":
            raise NexusAdapterError("NEXUS receipt verification failed")
        if receipt_verification.get("receipt_ref") != receipt_ref:
            raise NexusAdapterError("NEXUS receipt verification reference mismatch")
        if receipt_verification.get("result_ref") != session_ref:
            raise NexusAdapterError("NEXUS receipt verification result_ref mismatch")
        if receipt_verification.get("missing_refs") != []:
            raise NexusAdapterError("NEXUS receipt verification reports missing references")
        if receipt_verification.get("replayable") != replayable:
            raise NexusAdapterError("NEXUS receipt replayability verification mismatch")
        if run_response.get("execution_replayable") != replayable:
            raise NexusAdapterError("NEXUS execution replayability differs from receipt")
        if payload.get("execution_replayable") != replayable:
            raise NexusAdapterError("NEXUS session replayability differs from receipt")

        chair = run_response.get("council_chair")
        if chair is not None:
            if not isinstance(chair, dict):
                raise NexusAdapterError("NEXUS Council Chair summary is invalid")
            if chair.get("vote_weight_per_seat") != 1:
                raise NexusAdapterError("NEXUS Council Chair changed vote weight")
            if chair.get("epistemic_privilege_per_seat") != "none":
                raise NexusAdapterError("NEXUS Council Chair changed epistemic privilege")
            seats = chair.get("seats")
            if isinstance(seats, list):
                seat_ids = [seat.get("member_id") for seat in seats if isinstance(seat, dict)]
                if seat_ids != roster_ids:
                    raise NexusAdapterError("NEXUS Council Chair roster differs from session roster")

        citizenship = run_response.get("citizenship")
        if isinstance(citizenship, dict) and citizenship.get("additional_votes_created") != 0:
            raise NexusAdapterError("NEXUS citizenship layer created additional votes")

        epoch_ref: str | None = None
        if epoch_object is not None:
            _reject_hidden_reasoning(epoch_object, "NEXUS epoch admission receipt")
            epoch_ref = epoch_object["object_id"]
            if epoch_verification is None or epoch_verification.get("status") != "verified":
                raise NexusAdapterError("NEXUS epoch admission receipt verification failed")
            if epoch_verification.get("receipt_ref") != epoch_ref:
                raise NexusAdapterError("NEXUS epoch admission verification ref mismatch")
            if epoch_verification.get("session_ref") != session_ref:
                raise NexusAdapterError("NEXUS epoch admission session mismatch")
            if epoch_verification.get("vote_weight_per_seat") != 1:
                raise NexusAdapterError("NEXUS epoch admission changed vote weight")
            if epoch_verification.get("epistemic_privilege_per_seat") != "none":
                raise NexusAdapterError("NEXUS epoch admission changed epistemic privilege")

        consensus = {
            "disposition": result.get("disposition"),
            "tally": copy.deepcopy(result.get("tally")),
            "consensus_label": result.get("consensus_label"),
            "consensus_threshold": copy.deepcopy(threshold),
            "evidence_state": result.get("evidence_state"),
        }
        rendered: dict[str, Any] = {
            "protocol": COUNCIL_RESPONSE_PROTOCOL,
            "availability": "available",
            "nexus_protocol": discovery["nexus_protocol"],
            "nexus_runtime_version": discovery["nexus_runtime_version"],
            "session_id": session_id,
            "session_ref": session_ref,
            "receipt_ref": receipt_ref,
            "epoch_admission_receipt_ref": epoch_ref,
            "execution_replayable": replayable,
            "mode_id": run_response.get("mode_id"),
            "evidence_snapshot_ref": evidence_snapshot_ref,
            "world_presence_ref": run_response.get("world_presence_ref"),
            "admitted_evidence_refs": list(requested_evidence_refs),
            "roster": copy.deepcopy(roster),
            "phase_order": list(phase_order),
            "phases": rendered_phases,
            "sealed_ballot": {
                "stage": "SEALED_BALLOT",
                "sealed_before_reveal": True,
                "commitments": copy.deepcopy(commitments),
                "revealed_ballots": copy.deepcopy(revealed),
                "commitments_verified": True,
            },
            "consensus": consensus,
            "minority_reports": copy.deepcopy(minority_reports),
            "telemetry": copy.deepcopy(payload.get("telemetry")),
            "failsafe": copy.deepcopy(payload.get("failsafe")),
            "council_chair": copy.deepcopy(chair),
            "citizenship": copy.deepcopy(citizenship),
            "receipt_verification": copy.deepcopy(receipt_verification),
            "epoch_admission_verification": copy.deepcopy(epoch_verification),
            "governance": {
                "vote_weight_source": "nexus_session_roster_and_policy",
                "ballot_source": "nexus_committed_council_session",
                "roster_source": "nexus_committed_council_session",
                "phase_order_source": "nexus_committed_council_session",
                "consensus_threshold_source": "nexus_committed_council_session",
                "worldstore_history_owner": "QSOL-NEXUS",
                "control_direct_worldstore_mutation": False,
                "control_ballot_override": False,
                "control_threshold_override": False,
                "control_vote_weight_override": False,
            },
            "hidden_chain_of_thought_captured": False,
            "authority": "reference-and-render-only",
        }
        _reject_hidden_reasoning(rendered, "CONTROL NEXUS Council render")
        rendered["response_sha256"] = _canonical_hash(rendered)
        return rendered

    def _persist_artifacts(
        self,
        *,
        control_root: str | Path,
        control_run_id: str | None,
        created_at: str,
        privacy_class: str,
        run_response: dict[str, Any],
        session_object: dict[str, Any],
        receipt_object: dict[str, Any],
        receipt_verification: dict[str, Any],
        rendered: dict[str, Any],
        epoch_object: dict[str, Any] | None,
        epoch_verification: dict[str, Any] | None,
    ) -> dict[str, Any]:
        artifacts: list[tuple[str, str, dict[str, Any]]] = [
            ("council-run-response", f"nexus:session:{rendered['session_ref']}", run_response),
            ("council-session", f"nexus:session:{rendered['session_ref']}", session_object),
            ("council-receipt", f"nexus:receipt:{rendered['receipt_ref']}", receipt_object),
            (
                "council-receipt-verification",
                f"nexus:receipt:{rendered['receipt_ref']}",
                receipt_verification,
            ),
            ("council-render", f"nexus:session:{rendered['session_ref']}", rendered),
        ]
        if epoch_object is not None and epoch_verification is not None:
            artifacts.extend(
                [
                    (
                        "epoch-admission-receipt",
                        f"nexus:epoch:{epoch_object['object_id']}",
                        epoch_object,
                    ),
                    (
                        "epoch-admission-verification",
                        f"nexus:epoch:{epoch_object['object_id']}",
                        epoch_verification,
                    ),
                ]
            )

        store = ControlStore(control_root)
        file_ids: list[str] = []
        rows: list[dict[str, Any]] = []
        for kind, source_ref, payload in artifacts:
            _reject_hidden_reasoning(payload, f"persisted NEXUS {kind}")
            _reject_obvious_secrets(payload, f"persisted NEXUS {kind}")
            raw = canonical_json_bytes(payload)
            digest = _sha256(raw)
            record = store.put_file(
                raw,
                filename=f"nexus-{kind}-{digest[:16]}.json",
                media_type="application/json",
                created_at=created_at,
                privacy_class=privacy_class,
                retention_class="ARCHIVE",
                source={"kind": "qsol-nexus-reference", "locator": source_ref},
                metadata={
                    "protocol": RECEIPT_REF_PROTOCOL,
                    "artifact_kind": kind,
                    "source_ref": source_ref,
                    "payload_sha256": digest,
                    "authority": "reference-only",
                    "copied_governance_authority": False,
                    "hidden_chain_of_thought_captured": False,
                },
            )
            file_ids.append(record["file_id"])
            rows.append(
                {
                    "artifact_kind": kind,
                    "file_id": record["file_id"],
                    "object_id": record["object_id"],
                    "payload_sha256": digest,
                    "source_ref": source_ref,
                }
            )

        event_refs: list[str] = []
        if control_run_id is not None:
            interaction = InteractionStore(control_root)
            interaction.get_run(control_run_id)
            receipt_event = interaction.append_event(
                control_run_id,
                kind="receipt",
                payload={
                    "protocol": RECEIPT_REF_PROTOCOL,
                    "nexus_session_ref": rendered["session_ref"],
                    "nexus_receipt_ref": rendered["receipt_ref"],
                    "receipt_verified": True,
                    "hidden_chain_of_thought_captured": False,
                    "authority": "reference-only",
                },
                occurred_at=created_at,
                file_ids=file_ids,
                record_refs=[rendered["session_ref"], rendered["receipt_ref"]],
            )
            response_event = interaction.append_event(
                control_run_id,
                kind="response",
                payload=rendered,
                occurred_at=created_at,
                epistemic_role="derived",
                temporal_role="current",
                parent_event_ids=[receipt_event["event_id"]],
                file_ids=file_ids,
                record_refs=[rendered["session_ref"], rendered["receipt_ref"]],
            )
            event_refs = [receipt_event["event_id"], response_event["event_id"]]

        return {
            "protocol": RECEIPT_REF_PROTOCOL,
            "artifacts": rows,
            "file_ids": file_ids,
            "interaction_event_ids": event_refs,
            "authority": "reference-only",
            "hidden_chain_of_thought_captured": False,
        }


__all__ = [
    "ADAPTER_PROTOCOL",
    "COUNCIL_RESPONSE_PROTOCOL",
    "DISCOVERY_PROTOCOL",
    "NexusAdapterError",
    "NexusCouncilAdapter",
]
