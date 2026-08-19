#!/usr/bin/env python3
"""Launch the local QSOL-CONTROL Phase 5 human WebUI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from webui.server import WebUIConfig, WebUIError, serve

MAX_MEMBERS_BYTES = 4 * 1024 * 1024


def read_members(path_value: str | None) -> tuple[dict[str, Any], ...]:
    if path_value is None:
        return ()
    path = Path(path_value)
    if path.is_symlink():
        raise WebUIError("Council member descriptor must not be a symlink")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise WebUIError("Council member descriptor is unavailable") from exc
    if size > MAX_MEMBERS_BYTES:
        raise WebUIError("Council member descriptor exceeds 4 MiB")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise WebUIError("Council member descriptor must be valid UTF-8 JSON") from exc
    if not isinstance(value, list) or not value or len(value) > 64:
        raise WebUIError("Council member descriptor must contain 1..64 objects")
    if any(not isinstance(item, dict) for item in value):
        raise WebUIError("Council member descriptor entries must be objects")
    return tuple(value)


def command_vector(value: str | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise WebUIError("--nexus-command-json must be valid JSON") from exc
    if (
        not isinstance(decoded, list)
        or not decoded
        or len(decoded) > 128
        or not all(isinstance(item, str) and item for item in decoded)
    ):
        raise WebUIError("--nexus-command-json must decode to a bounded non-empty string array")
    return tuple(decoded)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="QSOL-CONTROL local loopback human WebUI"
    )
    parser.add_argument("--root", default=".qsol-control-store", help="CONTROL storage root")
    parser.add_argument("--bind", default="127.0.0.1", choices=["127.0.0.1", "::1", "localhost"])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--oracle-root", help="optional local QSOL-ORACLE repository")
    parser.add_argument(
        "--nexus-command-json",
        help='optional JSON argv array for NEXUS, e.g. ["python3","-m","nexus_runtime"]',
    )
    parser.add_argument("--nexus-cwd", help="optional NEXUS working directory")
    parser.add_argument("--nexus-members", help="optional default Council member JSON array")
    parser.add_argument("--nexus-timeout-seconds", type=float, default=1800.0)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        config = WebUIConfig(
            control_root=Path(args.root),
            oracle_root=Path(args.oracle_root) if args.oracle_root else None,
            nexus_command=command_vector(args.nexus_command_json),
            nexus_cwd=Path(args.nexus_cwd) if args.nexus_cwd else None,
            nexus_timeout_seconds=args.nexus_timeout_seconds,
            default_council_members=read_members(args.nexus_members),
            bind=args.bind,
            port=args.port,
        )
        serve(config)
        return 0
    except (WebUIError, OSError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
