#!/usr/bin/env python3
"""Optional external consensus adapter for post-roadmap CONTROL coordination.

CONTROL does not implement a consensus algorithm here. It binds an exact mutation
intent, delegates quorum formation to an external coordinator, and validates the
returned receipt. The receipt is coordination evidence only and never semantic truth.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from api.common import AgentAPIError, MUTATION_OPERATIONS, reject_forbidden_fields

ADAPTER_PROTOCOL = "qsol-control-consensus-adapter/1"
INTENT_PROTOCOL = "qsol-control-consensus-intent/1"
RECEIPT_PROTOCOL = "qsol-control-consensus-receipt/1"
PROVIDER_RESPONSE_PROTOCOL = "qsol-external-consensus-response/1"
SHA256_REF = re.compile(r"^sha256:[0-9a-f]{64}$")
TOKEN = re.compile(r"^[A-Za-z0-9._:-]{1,256}$")
MAX_COMMAND_ARGS = 64
MAX_ARG_CHARS = 8192
MAX_REQUEST_BYTES = 4 * 1024 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class ConsensusAdapterError(ValueError):
    """Raised when external coordination or receipt validation fails."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_ref(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ConsensusAdapterError(f"duplicate JSON member: {key}")
        out[key] = value
    return out


def _reject_constant(value: str) -> None:
    raise ConsensusAdapterError(f"non-finite JSON number rejected: {value}")


def _validate_command(command: Sequence[str]) -> tuple[str, ...]:
    if not isinstance(command, (list, tuple)) or not command or len(command) > MAX_COMMAND_ARGS:
        raise ConsensusAdapterError("consensus command must be a bounded non-empty argv sequence")
    out = []
    for arg in command:
        if not isinstance(arg, str) or not arg or len(arg) > MAX_ARG_CHARS or "\x00" in arg:
            raise ConsensusAdapterError("consensus command argument is invalid")
        out.append(arg)
    return tuple(out)


def build_intent(*, operation: str, params: dict[str, Any], expected_store_fingerprint: str) -> dict[str, Any]:
    if operation not in MUTATION_OPERATIONS:
        raise ConsensusAdapterError("consensus intent operation must be a known CONTROL mutation")
    if not isinstance(params, dict):
        raise ConsensusAdapterError("params must be an object")
    try:
        reject_forbidden_fields(params)
    except AgentAPIError as exc:
        raise ConsensusAdapterError(f"consensus intent rejected by Agent API boundary: {exc.message}") from exc
    if not isinstance(expected_store_fingerprint, str) or SHA256_REF.fullmatch(expected_store_fingerprint) is None:
        raise ConsensusAdapterError("expected_store_fingerprint must be a sha256: reference")
    payload = {
        "protocol": INTENT_PROTOCOL,
        "operation": operation,
        "params": params,
        "expected_store_fingerprint": expected_store_fingerprint,
        "authority": "coordination-only",
        "semantic_authority_claimed": False,
    }
    return {"intent_id": sha256_ref(canonical_json_bytes(payload)), **payload}


def validate_receipt(receipt: Any, *, expected_intent_id: str | None = None) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise ConsensusAdapterError("consensus receipt must be an object")
    required = {
        "protocol", "intent_id", "cluster_id", "epoch", "commit_index", "member_set_id",
        "quorum", "state_fingerprint", "provider_protocol", "verified", "authority",
        "semantic_authority_claimed",
    }
    if set(receipt) != required or receipt.get("protocol") != RECEIPT_PROTOCOL:
        raise ConsensusAdapterError("consensus receipt protocol/field set mismatch")
    for field in ("intent_id", "member_set_id", "state_fingerprint"):
        if not isinstance(receipt[field], str) or SHA256_REF.fullmatch(receipt[field]) is None:
            raise ConsensusAdapterError(f"consensus receipt {field} is invalid")
    if expected_intent_id is not None and receipt["intent_id"] != expected_intent_id:
        raise ConsensusAdapterError("consensus receipt is bound to a different intent")
    if not isinstance(receipt["cluster_id"], str) or TOKEN.fullmatch(receipt["cluster_id"]) is None:
        raise ConsensusAdapterError("consensus cluster_id is invalid")
    if type(receipt["epoch"]) is not int or receipt["epoch"] < 0:
        raise ConsensusAdapterError("consensus epoch is invalid")
    if type(receipt["commit_index"]) is not int or receipt["commit_index"] < 0:
        raise ConsensusAdapterError("consensus commit_index is invalid")
    quorum = receipt["quorum"]
    if not isinstance(quorum, dict) or set(quorum) != {"required", "observed"}:
        raise ConsensusAdapterError("consensus quorum shape is invalid")
    required_votes = quorum["required"]
    observed_votes = quorum["observed"]
    if type(required_votes) is not int or type(observed_votes) is not int or required_votes < 1 or observed_votes < required_votes:
        raise ConsensusAdapterError("consensus quorum threshold was not satisfied")
    if not isinstance(receipt["provider_protocol"], str) or not receipt["provider_protocol"]:
        raise ConsensusAdapterError("consensus provider_protocol is invalid")
    if receipt["verified"] is not True:
        raise ConsensusAdapterError("external consensus provider did not verify the receipt")
    if receipt["authority"] != "coordination-only" or receipt["semantic_authority_claimed"] is not False:
        raise ConsensusAdapterError("consensus receipt attempted authority escalation")
    return receipt


@dataclass
class ExternalConsensusAdapter:
    command: tuple[str, ...]
    cwd: Path | None = None
    timeout_seconds: float = 30.0

    def __init__(self, command: Sequence[str], *, cwd: str | Path | None = None, timeout_seconds: float = 30.0) -> None:
        self.command = _validate_command(command)
        self.cwd = Path(cwd) if cwd is not None else None
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or not 0.1 <= float(timeout_seconds) <= 300.0:
            raise ConsensusAdapterError("consensus timeout_seconds must be 0.1..300")
        self.timeout_seconds = float(timeout_seconds)

    def _call(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = {"protocol": ADAPTER_PROTOCOL, "operation": operation, "payload": payload}
        raw = canonical_json_bytes(request) + b"\n"
        if len(raw) > MAX_REQUEST_BYTES:
            raise ConsensusAdapterError("consensus request exceeds byte limit")
        try:
            completed = subprocess.run(
                self.command,
                input=raw,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.cwd) if self.cwd else None,
                timeout=self.timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ConsensusAdapterError("external consensus provider unavailable") from exc
        if completed.returncode != 0:
            raise ConsensusAdapterError("external consensus provider returned failure")
        if len(completed.stdout) > MAX_RESPONSE_BYTES:
            raise ConsensusAdapterError("consensus response exceeds byte limit")
        try:
            response = json.loads(
                completed.stdout.decode("utf-8"),
                object_pairs_hook=_pairs,
                parse_constant=_reject_constant,
            )
        except ConsensusAdapterError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ConsensusAdapterError("external consensus provider returned invalid JSON") from exc
        if not isinstance(response, dict) or response.get("protocol") != PROVIDER_RESPONSE_PROTOCOL or response.get("ok") is not True:
            raise ConsensusAdapterError("external consensus provider response contract mismatch")
        result = response.get("result")
        if not isinstance(result, dict):
            raise ConsensusAdapterError("external consensus provider result is invalid")
        return result

    def health(self) -> dict[str, Any]:
        result = self._call("system.health", {})
        if result.get("status") != "ok" or not isinstance(result.get("provider_protocol"), str):
            raise ConsensusAdapterError("external consensus provider health is invalid")
        return {
            "protocol": ADAPTER_PROTOCOL,
            "status": "available",
            "provider_protocol": result["provider_protocol"],
            "authority": "coordination-only",
            "consensus_algorithm_owned_by_control": False,
        }

    def propose(self, intent: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(intent, dict) or intent.get("protocol") != INTENT_PROTOCOL:
            raise ConsensusAdapterError("consensus intent protocol mismatch")
        payload = dict(intent)
        claimed = payload.pop("intent_id", None)
        if not isinstance(claimed, str) or claimed != sha256_ref(canonical_json_bytes(payload)):
            raise ConsensusAdapterError("consensus intent identity mismatch")
        result = self._call("commit.propose", intent)
        receipt = validate_receipt(result, expected_intent_id=claimed)
        if receipt["state_fingerprint"] != intent["expected_store_fingerprint"]:
            raise ConsensusAdapterError("consensus receipt is bound to a different CONTROL pre-state")
        verification = self._call("receipt.verify", receipt)
        if verification.get("verified") is not True or verification.get("intent_id") != claimed:
            raise ConsensusAdapterError("external consensus provider failed post-proposal receipt verification")
        return receipt

    def verify(self, receipt: dict[str, Any]) -> dict[str, Any]:
        local = validate_receipt(receipt)
        result = self._call("receipt.verify", receipt)
        if result.get("verified") is not True or result.get("intent_id") != local["intent_id"]:
            raise ConsensusAdapterError("external consensus receipt verification failed")
        return local
