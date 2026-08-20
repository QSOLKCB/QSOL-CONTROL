from __future__ import annotations

import json
import sys
from typing import Any, BinaryIO

from .common import (
    MAX_REQUEST_BYTES,
    AgentAPIError,
    canonical_json_bytes,
    error_envelope,
)
from .dispatcher import AgentAPIDispatcher


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise AgentAPIError("INVALID_JSON", f"duplicate JSON object member: {key}")
        value[key] = item
    return value


def _reject_nonstandard_constant(value: str) -> None:
    raise AgentAPIError(
        "INVALID_JSON", f"non-standard JSON numeric constant is forbidden: {value}"
    )


def process_line(dispatcher: AgentAPIDispatcher, raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_REQUEST_BYTES:
        return error_envelope(
            "unknown",
            None,
            AgentAPIError("RESOURCE_LIMIT", "request exceeds agent API byte limit"),
        )
    try:
        text = raw.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_nonstandard_constant,
        )
    except AgentAPIError as exc:
        return error_envelope("unknown", None, exc)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        return error_envelope(
            "unknown",
            None,
            AgentAPIError("INVALID_JSON", "request must be valid UTF-8 JSON"),
        )
    return dispatcher.handle(value)


def serve_stdio(
    dispatcher: AgentAPIDispatcher,
    *,
    input_stream: BinaryIO | None = None,
    output_stream: BinaryIO | None = None,
) -> None:
    source = input_stream or sys.stdin.buffer
    sink = output_stream or sys.stdout.buffer
    while True:
        raw = source.readline(MAX_REQUEST_BYTES + 2)
        if not raw:
            return
        if len(raw) > MAX_REQUEST_BYTES and not raw.endswith(b"\n"):
            while raw and not raw.endswith(b"\n"):
                raw = source.readline(MAX_REQUEST_BYTES + 2)
            response = error_envelope(
                "unknown",
                None,
                AgentAPIError("RESOURCE_LIMIT", "request exceeds agent API byte limit"),
            )
        elif not raw.strip():
            continue
        else:
            response = process_line(dispatcher, raw)
        sink.write(canonical_json_bytes(response) + b"\n")
        sink.flush()
