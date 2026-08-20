#!/usr/bin/env python3
"""CLI for the optional external consensus coordination adapter."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.consensus import ConsensusAdapterError, ExternalConsensusAdapter, build_intent, validate_receipt
from storage.control_store import ControlStore
from tools.webui import command_vector


def _load_json(path: str) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ConsensusAdapterError("JSON input must be an object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QSOL-CONTROL external consensus coordination adapter")
    parser.add_argument("--command-json", required=True, help="external provider argv as JSON array")
    parser.add_argument("--cwd", help="optional provider working directory")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("health")
    propose = sub.add_parser("propose")
    propose.add_argument("--root", required=True, help="CONTROL store used to bind current canonical fingerprint")
    propose.add_argument("--operation", required=True)
    propose.add_argument("--params-json", required=True, help="JSON object file with intended CONTROL params")
    verify = sub.add_parser("verify")
    verify.add_argument("--receipt-json", required=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        adapter = ExternalConsensusAdapter(
            command_vector(args.command_json),
            cwd=args.cwd,
            timeout_seconds=args.timeout_seconds,
        )
        if args.command == "health":
            result = adapter.health()
        elif args.command == "propose":
            params = _load_json(args.params_json)
            fingerprint = ControlStore(args.root).fingerprint()["fingerprint"]
            intent = build_intent(
                operation=args.operation,
                params=params,
                expected_store_fingerprint=fingerprint,
            )
            result = {"intent": intent, "receipt": adapter.propose(intent)}
        else:
            receipt = _load_json(args.receipt_json)
            validate_receipt(receipt)
            result = adapter.verify(receipt)
    except (ConsensusAdapterError, OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
