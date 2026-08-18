#!/usr/bin/env python3
"""Operator CLI for QSOL-CONTROL Phase-1B interaction persistence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from storage.control_store import StorageError
from storage.interaction_store import InteractionStore


def emit(value) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def store_from(args: argparse.Namespace) -> InteractionStore:
    return InteractionStore(args.root)


def load_json_object(value: str, *, field: str) -> dict:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise StorageError(f"{field} must decode to a JSON object")
    return parsed


def command_create(args: argparse.Namespace) -> int:
    store = store_from(args)
    snapshot_id = args.snapshot_id
    if args.collection_id and snapshot_id is None:
        snapshot_id = store.storage.get_collection_snapshot(args.collection_id)["snapshot_id"]
    emit(
        store.create_run(
            question=args.question,
            mode=args.mode,
            requester_kind=args.requester_kind,
            created_at=args.created_at,
            evidence_state=args.evidence_state,
            file_ids=args.file_id,
            collection_id=args.collection_id,
            snapshot_id=snapshot_id,
            oracle_refs=args.oracle_ref,
            nexus_refs=args.nexus_ref,
            model_state_refs=args.model_state_ref,
            replayability=args.replayability,
        )
    )
    return 0


def command_append(args: argparse.Namespace) -> int:
    emit(
        store_from(args).append_event(
            args.run_id,
            kind=args.kind,
            payload=load_json_object(args.payload_json, field="payload-json"),
            occurred_at=args.occurred_at,
            epistemic_role=args.epistemic_role,
            temporal_role=args.temporal_role,
            parent_event_ids=args.parent_event_id if args.parent_event_id else None,
            file_ids=args.file_id,
            record_refs=args.record_ref,
        )
    )
    return 0


def command_show(args: argparse.Namespace) -> int:
    store = store_from(args)
    emit({"run": store.get_run(args.run_id), "events": store.list_events(args.run_id)})
    return 0


def command_verify(args: argparse.Namespace) -> int:
    emit(store_from(args).verify_run(args.run_id))
    return 0


def command_fingerprint(args: argparse.Namespace) -> int:
    emit(store_from(args).fingerprint_run(args.run_id))
    return 0


def command_export(args: argparse.Namespace) -> int:
    output = Path(args.output)
    if output.is_symlink():
        raise StorageError("export-record-set refuses symlink outputs")
    bundle = store_from(args).export_record_set(args.run_id)
    output.write_text(
        json.dumps(bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    emit({"status": "written", "run_id": args.run_id, "output": str(output)})
    return 0


def command_import(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if path.is_symlink():
        raise StorageError("import-record-set refuses symlink inputs")
    value = json.loads(path.read_text(encoding="utf-8"))
    emit(store_from(args).import_record_set(value))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QSOL-CONTROL interaction persistence")
    parser.add_argument("--root", default=".qsol-control-store", help="storage directory")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="create one immutable interaction/run record")
    create.add_argument("--question", required=True)
    create.add_argument("--mode", choices=["evidence_only", "council"], required=True)
    create.add_argument("--requester-kind", choices=["human", "ai", "system"], required=True)
    create.add_argument("--created-at", required=True)
    create.add_argument(
        "--evidence-state",
        choices=["known", "conflict", "unknown", "unavailable"],
        default="unknown",
    )
    create.add_argument("--file-id", action="append", default=[])
    create.add_argument("--collection-id")
    create.add_argument("--snapshot-id")
    create.add_argument("--oracle-ref", action="append", default=[])
    create.add_argument("--nexus-ref", action="append", default=[])
    create.add_argument("--model-state-ref", action="append", default=[])
    create.add_argument("--replayability", choices=["R0", "R1", "R2", "R3"], default="R0")
    create.set_defaults(func=command_create)

    append = sub.add_parser("append", help="append one immutable run event")
    append.add_argument("run_id")
    append.add_argument(
        "--kind",
        choices=["question", "response", "evidence", "receipt", "model_state"],
        required=True,
    )
    append.add_argument("--payload-json", required=True, help="JSON object payload")
    append.add_argument("--occurred-at", required=True)
    append.add_argument("--epistemic-role", choices=["observed", "derived", "unresolved"])
    append.add_argument("--temporal-role", choices=["current", "historical", "recovery"])
    append.add_argument("--parent-event-id", action="append", default=[])
    append.add_argument("--file-id", action="append", default=[])
    append.add_argument("--record-ref", action="append", default=[])
    append.set_defaults(func=command_append)

    show = sub.add_parser("show", help="show run plus ordered event history")
    show.add_argument("run_id")
    show.set_defaults(func=command_show)

    verify = sub.add_parser("verify", help="verify one run and its event lineage")
    verify.add_argument("run_id")
    verify.set_defaults(func=command_verify)

    fingerprint = sub.add_parser("fingerprint", help="fingerprint one canonical run")
    fingerprint.add_argument("run_id")
    fingerprint.set_defaults(func=command_fingerprint)

    export = sub.add_parser("export-record-set", help="export canonical run/event JSON")
    export.add_argument("run_id")
    export.add_argument("--output", required=True)
    export.set_defaults(func=command_export)

    import_cmd = sub.add_parser("import-record-set", help="import verified run/event JSON")
    import_cmd.add_argument("path")
    import_cmd.set_defaults(func=command_import)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (StorageError, OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
