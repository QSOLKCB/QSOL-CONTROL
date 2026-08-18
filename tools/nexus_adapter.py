#!/usr/bin/env python3
"""Operator CLI for the QSOL-CONTROL read/invoke-only NEXUS Council adapter."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.nexus import NexusAdapterError, NexusCouncilAdapter
from storage.control_store import StorageError

MAX_INPUT_BYTES = 4 * 1024 * 1024


def emit(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def read_bounded_json(path_value: str, *, label: str) -> Any:
    path = Path(path_value)
    if path.is_symlink():
        raise NexusAdapterError(f"{label} refuses symlink input")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise NexusAdapterError(f"{label} input is unavailable") from exc
    if size > MAX_INPUT_BYTES:
        raise NexusAdapterError(f"{label} input exceeds {MAX_INPUT_BYTES} bytes")
    with path.open("rb") as handle:
        raw = handle.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise NexusAdapterError(f"{label} input exceeds {MAX_INPUT_BYTES} bytes")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NexusAdapterError(f"{label} input is not valid UTF-8 JSON") from exc


def command_vector(value: str) -> list[str]:
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise NexusAdapterError("--nexus-command-json must be valid JSON") from exc
    if not isinstance(decoded, list) or not decoded or not all(
        isinstance(item, str) and item for item in decoded
    ):
        raise NexusAdapterError("--nexus-command-json must decode to a non-empty string array")
    return decoded


def adapter_from(args: argparse.Namespace) -> NexusCouncilAdapter:
    return NexusCouncilAdapter.from_command(
        command_vector(args.nexus_command_json),
        cwd=args.nexus_cwd,
        timeout_seconds=args.timeout_seconds,
    )


def command_discover(args: argparse.Namespace) -> int:
    with adapter_from(args) as adapter:
        emit(adapter.discover())
    return 0


def command_run(args: argparse.Namespace) -> int:
    members = read_bounded_json(args.members, label="members")
    if not isinstance(members, list):
        raise NexusAdapterError("members JSON must contain an array")
    with adapter_from(args) as adapter:
        result = adapter.run_council(
            question=args.question,
            members=members,
            evidence_refs=args.evidence_ref,
            evidence_state=args.evidence_state,
            mode=args.mode,
            control_root=args.control_root,
            control_run_id=args.control_run_id,
            created_at=args.created_at,
            privacy_class=args.privacy,
        )
    emit(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="QSOL-CONTROL local JSONL/stdio NEXUS Council adapter"
    )
    parser.add_argument(
        "--nexus-command-json",
        required=True,
        help='JSON argv array, e.g. ["python3","-m","nexus_runtime","--world","/secure/world"]',
    )
    parser.add_argument("--nexus-cwd", help="optional local working directory for NEXUS")
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover", help="query system.health and system.operations")
    discover.set_defaults(func=command_discover)

    run = sub.add_parser("run", help="submit one Council question and verify the committed result")
    run.add_argument("--question", required=True)
    run.add_argument("--members", required=True, help="JSON array of requested Council member descriptors")
    run.add_argument("--evidence-ref", action="append", default=[])
    run.add_argument("--evidence-state", default="UNTESTED")
    run.add_argument("--mode", default="analytical")
    run.add_argument("--control-root", help="optional CONTROL store for verified NEXUS artifacts")
    run.add_argument("--control-run-id", help="optional existing qsol-control-interaction/2 run to link")
    run.add_argument("--created-at", help="required when --control-root is supplied")
    run.add_argument("--privacy", choices=["PUBLIC", "INTERNAL", "RESTRICTED"], default="INTERNAL")
    run.set_defaults(func=command_run)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "run":
        if args.control_run_id is not None and args.control_root is None:
            parser.error("--control-run-id requires --control-root")
        if args.control_root is not None and args.created_at is None:
            parser.error("--control-root requires --created-at")
    try:
        return args.func(args)
    except (NexusAdapterError, StorageError, OSError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
