from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

AGENT_API_PROTOCOL = "qsol-control-agent-api/1"
AGENT_REQUEST_PROTOCOL = "qsol-control-agent-request/1"
AGENT_RESPONSE_PROTOCOL = "qsol-control-agent-response/1"
AGENT_ERROR_PROTOCOL = "qsol-control-agent-error/1"

MAX_REQUEST_BYTES = 8 * 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_REQUEST_ID_CHARACTERS = 256
MAX_CALLER_ID_CHARACTERS = 256
MAX_REQUESTS_PER_CALLER = 1000
MAX_MUTATIONS_PER_CALLER = 200
MAX_REQUESTS_PER_PROCESS = 1000
MAX_MUTATIONS_PER_PROCESS = 200
MAX_MODEL_STATES = 100
MAX_LATTICE_RECORDS = 1000
MAX_LATTICE_RUNS = 100

REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,256}$")
LATTICE_RE = re.compile(r"^L\[[0-2],[0-2],[0-2]\](?:/L\[[0-2],[0-2],[0-2]\])*$")

MUTATION_OPERATIONS = {
    "control.ask",
    "control.file.put",
    "control.collection.create",
    "control.replay.execute",
}

OPERATIONS = (
    "control.health",
    "control.capabilities",
    "control.ask",
    "control.file.put",
    "control.file.get",
    "control.collection.create",
    "control.collection.snapshot",
    "control.collection.search",
    "control.run.get",
    "control.run.compare",
    "control.replay.classify",
    "control.replay.execute",
    "control.replay.get",
    "control.research.timeline",
    "control.evidence.get",
    "control.council.get",
    "control.models.get",
    "control.memory.get",
    "control.memory.trace",
)

FORBIDDEN_NORMALIZED_KEYS = {
    "truth_score",
    "truth_percentage",
    "probability_true",
    "verified_by_consensus",
    "epistemic_privilege",
    "authority_override",
    "oracle_write",
    "oracle_append",
    "world_create",
    "worldstore_mutation",
    "vote_weight",
    "ballot_override",
    "consensus_threshold_override",
    "hidden_chain_of_thought",
    "chain_of_thought",
    "reasoning_trace",
    "private_reasoning",
    "scratchpad",
    "api_key",
    "access_token",
    "refresh_token",
    "client_secret",
    "private_key",
    "authorization",
    "password",
}


class AgentAPIError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "details": self.details,
        }


@dataclass(frozen=True)
class Caller:
    kind: str
    caller_id: str

    @property
    def quota_key(self) -> str:
        return f"{self.kind}:{self.caller_id}"


@dataclass
class QuotaState:
    requests: int = 0
    mutations: int = 0


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def require_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AgentAPIError("INVALID_REQUEST", f"{field} must be an object")
    return value


def require_string(value: Any, field: str, *, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentAPIError("INVALID_REQUEST", f"{field} must be a non-empty string")
    if len(value) > maximum:
        raise AgentAPIError("RESOURCE_LIMIT", f"{field} exceeds {maximum} characters")
    return value


def require_int(value: Any, field: str, *, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise AgentAPIError(
            "INVALID_REQUEST", f"{field} must be an integer in {minimum}..{maximum}"
        )
    return value


def parse_caller(value: Any) -> Caller:
    caller = require_object(value, "caller")
    if set(caller) != {"kind", "id"}:
        raise AgentAPIError(
            "INVALID_REQUEST", "caller must contain exactly kind and id"
        )
    kind = caller.get("kind")
    if kind not in {"human", "ai"}:
        raise AgentAPIError("INVALID_REQUEST", "caller.kind must be human or ai")
    caller_id = require_string(
        caller.get("id"), "caller.id", maximum=MAX_CALLER_ID_CHARACTERS
    )
    return Caller(kind=kind, caller_id=caller_id)


def reject_forbidden_fields(value: Any) -> None:
    stack = [value]
    visited = 0
    while stack:
        current = stack.pop()
        visited += 1
        if visited > 100_000:
            raise AgentAPIError("RESOURCE_LIMIT", "request structure exceeds validation limit")
        if isinstance(current, dict):
            for key, item in current.items():
                if not isinstance(key, str):
                    raise AgentAPIError("INVALID_REQUEST", "request object keys must be strings")
                normalized = re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")
                if normalized in FORBIDDEN_NORMALIZED_KEYS:
                    raise AgentAPIError(
                        "AUTHORITY_ESCALATION",
                        f"field {key!r} is forbidden at the agent API boundary",
                    )
                stack.append(item)
        elif isinstance(current, list):
            stack.extend(current)


def validate_request_envelope(value: Any) -> tuple[str, Caller, str, dict[str, Any]]:
    request = require_object(value, "request")
    if set(request) != {"protocol", "request_id", "caller", "operation", "params"}:
        raise AgentAPIError(
            "INVALID_REQUEST",
            "request must contain exactly protocol, request_id, caller, operation, and params",
        )
    if request.get("protocol") != AGENT_REQUEST_PROTOCOL:
        raise AgentAPIError("UNSUPPORTED_PROTOCOL", "agent request protocol mismatch")
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or REQUEST_ID_RE.fullmatch(request_id) is None:
        raise AgentAPIError("INVALID_REQUEST", "request_id is invalid")
    caller = parse_caller(request.get("caller"))
    operation = request.get("operation")
    if operation not in OPERATIONS:
        raise AgentAPIError("UNKNOWN_OPERATION", "unsupported operation")
    params = require_object(request.get("params"), "params")
    reject_forbidden_fields(params)
    return request_id, caller, operation, params


def success_envelope(
    request_id: str,
    operation: str,
    result: Any,
) -> dict[str, Any]:
    value = {
        "protocol": AGENT_RESPONSE_PROTOCOL,
        "request_id": request_id,
        "operation": operation,
        "ok": True,
        "result": result,
        "authority": "orchestration-only",
    }
    if len(canonical_json_bytes(value)) > MAX_RESPONSE_BYTES:
        raise AgentAPIError("RESOURCE_LIMIT", "response exceeds agent API byte limit")
    return value


def error_envelope(
    request_id: str,
    operation: str | None,
    error: AgentAPIError,
) -> dict[str, Any]:
    value = {
        "protocol": AGENT_ERROR_PROTOCOL,
        "request_id": request_id,
        "operation": operation,
        "ok": False,
        "error": error.as_dict(),
        "authority": "none",
    }
    try:
        if len(canonical_json_bytes(value)) <= MAX_RESPONSE_BYTES:
            return value
    except (TypeError, ValueError, RecursionError):
        pass

    fallback = {
        "protocol": AGENT_ERROR_PROTOCOL,
        "request_id": request_id[:MAX_REQUEST_ID_CHARACTERS],
        "operation": operation[:256] if isinstance(operation, str) else None,
        "ok": False,
        "error": {
            "code": "RESOURCE_LIMIT",
            "message": "error response exceeded agent API byte limit",
            "retryable": False,
            "details": {"original_code": error.code},
        },
        "authority": "none",
    }
    if len(canonical_json_bytes(fallback)) > MAX_RESPONSE_BYTES:
        raise RuntimeError("bounded agent API error envelope exceeds response limit")
    return fallback
