#!/usr/bin/env python3
"""Operator CLI for the read-only QSOL-CONTROL ORACLE adapter."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.oracle import OracleAdapter, OracleAdapterError
from storage.control_store import StorageError


def emit(value) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def adapter(args: argparse.Namespace) -> OracleAdapter:
    return OracleAdapter(args.oracle_root)


def command_discover(args: argparse.Namespace) -> int:
    emit(adapter(args).availability())
    return 0


def command_query(args: argparse.Namespace) -> int:
    emit(
        adapter(args).query_evidence(
            args.subject,
            evaluated_at=args.at,
            max_age_seconds=args.max_age_seconds,
            suggested_searches=args.suggest_search,
        )
    )
    return 0


def command_timelock(args: argparse.Namespace) -> int:
    emit(adapter(args).timelock_status(evaluated_at=args.at))
    return 0


def command_validate_feed(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if path.is_symlink():
        raise OracleAdapterError("feed receipt input must not be a symlink")
    payload = json.loads(path.read_text(encoding="utf-8"))
    emit(adapter(args).validate_feed_receipt(payload))
    return 0


def command_store_receipt(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if path.is_symlink():
        raise OracleAdapterError("receipt input must not be a symlink")
    if path.stat().st_size > 16 * 1024 * 1024:
        raise OracleAdapterError("receipt input exceeds 16 MiB")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise OracleAdapterError("receipt input must contain a JSON object")
    emit(
        adapter(args).persist_receipt(
            args.control_root,
            payload,
            source_ref=args.source_ref,
            created_at=args.created_at,
            privacy_class=args.privacy,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QSOL-CONTROL read-only ORACLE adapter")
    parser.add_argument("--oracle-root", required=True, help="local QSOL-ORACLE repository")
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover", help="discover ORACLE protocol and capabilities")
    discover.set_defaults(func=command_discover)

    query = sub.add_parser("query", help="query exact-subject canonical evidence")
    query.add_argument("subject")
    query.add_argument("--at", help="ISO-8601 evaluation time")
    query.add_argument("--max-age-seconds", type=int, default=86400)
    query.add_argument("--suggest-search", action="append", default=[])
    query.set_defaults(func=command_query)

    timelock = sub.add_parser("timelock", help="show QSOL-CONTEXT timelock state")
    timelock.add_argument("--at", help="ISO-8601 evaluation time")
    timelock.set_defaults(func=command_timelock)

    feed = sub.add_parser("validate-feed", help="validate an ORACLE feed receipt")
    feed.add_argument("path")
    feed.set_defaults(func=command_validate_feed)

    store = sub.add_parser(
        "store-receipt",
        help="store exact verified ORACLE payload bytes in a separate CONTROL store",
    )
    store.add_argument("path")
    store.add_argument("--control-root", required=True)
    store.add_argument("--source-ref", required=True)
    store.add_argument("--created-at", required=True)
    store.add_argument("--privacy", choices=["PUBLIC", "INTERNAL", "RESTRICTED"], default="INTERNAL")
    store.set_defaults(func=command_store_receipt)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (OracleAdapterError, StorageError, OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
