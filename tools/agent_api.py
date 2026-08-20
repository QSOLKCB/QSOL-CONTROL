#!/usr/bin/env python3
"""Launch the QSOL-CONTROL Phase 6 structured AI / agent API over JSONL stdio."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.dispatcher import AgentAPIDispatcher
from api.stdio import serve_stdio
from tools.webui import command_vector, read_members
from webui.common import WebUIConfig, WebUIError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="QSOL-CONTROL Phase 6 structured AI / agent API (JSONL stdio)"
    )
    parser.add_argument("--root", default=".qsol-control-store", help="CONTROL storage root")
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
        )
        serve_stdio(AgentAPIDispatcher(config))
        return 0
    except (WebUIError, OSError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
