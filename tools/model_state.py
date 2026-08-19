#!/usr/bin/env python3
"""Operator CLI for the QSOL-CONTROL model-state registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from storage.control_store import StorageError
from storage.model_state_registry import ModelStateError, ModelStateRegistry

MAX_DESCRIPTOR_BYTES = 4 * 1024 * 1024


def _load_json(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    if path.is_symlink():
        raise ModelStateError("descriptor must not be a symbolic link")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ModelStateError("descriptor is unavailable") from exc
    if size > MAX_DESCRIPTOR_BYTES:
        raise ModelStateError("descriptor exceeds byte limit")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ModelStateError("descriptor is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ModelStateError("descriptor must contain a JSON object")
    return value


def _emit(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QSOL-CONTROL model-state registry")
    parser.add_argument("--root", default=".qsol-control-store", help="CONTROL storage root")
    sub = parser.add_subparsers(dest="command", required=True)

    capture = sub.add_parser("capture", help="capture one immutable model-state record")
    capture.add_argument("--descriptor", required=True, help="JSON model-state capture descriptor")
    capture.add_argument("--model-artifact")
    capture.add_argument("--weight-artifact")
    capture.add_argument("--tokenizer-artifact")

    show = sub.add_parser("show", help="show one model-state record")
    show.add_argument("state_id")

    verify = sub.add_parser("verify", help="verify one model-state record")
    verify.add_argument("state_id")

    listing = sub.add_parser("list", help="list model-state records")
    listing.add_argument("--run-id")

    compare = sub.add_parser("compare-states", help="compare two model-state records")
    compare.add_argument("left_state_id")
    compare.add_argument("right_state_id")

    compare_runs = sub.add_parser("compare-runs", help="compare model states across two CONTROL runs")
    compare_runs.add_argument("left_run_id")
    compare_runs.add_argument("right_run_id")

    export = sub.add_parser("export", help="write deterministic future-AI archaeology export")
    export.add_argument("--state-id", action="append", default=[])
    export.add_argument("--run-id", action="append", default=[])
    export.add_argument("--all", action="store_true")
    export.add_argument("--allow-restricted", action="store_true")
    export.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    registry = ModelStateRegistry(args.root)
    try:
        if args.command == "capture":
            descriptor = _load_json(args.descriptor)
            allowed = {
                "captured_at",
                "model",
                "execution",
                "system",
                "field_provenance",
                "privacy_class",
            }
            unknown = set(descriptor) - allowed
            if unknown:
                raise ModelStateError(
                    "descriptor contains unsupported fields: " + ", ".join(sorted(unknown))
                )
            artifacts = {
                role: path
                for role, path in (
                    ("model", args.model_artifact),
                    ("weights", args.weight_artifact),
                    ("tokenizer", args.tokenizer_artifact),
                )
                if path is not None
            }
            record = registry.capture(
                captured_at=descriptor.get("captured_at"),
                model=descriptor.get("model"),
                execution=descriptor.get("execution"),
                system=descriptor.get("system"),
                field_provenance=descriptor.get("field_provenance"),
                privacy_class=descriptor.get("privacy_class", "INTERNAL"),
                local_artifacts=artifacts,
                # The registry's system.control_run_id is the canonical run link.
                # Phase 4 does not mutate the immutable run record merely to add a
                # late model-state reference.
                link_run_event=False,
            )
            _emit(record)
            return 0
        if args.command == "show":
            _emit(registry.get_state(args.state_id))
            return 0
        if args.command == "verify":
            _emit(registry.verify_state(args.state_id))
            return 0
        if args.command == "list":
            _emit({"states": registry.list_states(run_id=args.run_id)})
            return 0
        if args.command == "compare-states":
            _emit(registry.compare_states(args.left_state_id, args.right_state_id))
            return 0
        if args.command == "compare-runs":
            _emit(registry.compare_runs(args.left_run_id, args.right_run_id))
            return 0
        if args.command == "export":
            export = registry.write_archaeology_export(
                args.output,
                state_ids=args.state_id,
                run_ids=args.run_id,
                include_all=args.all,
                allow_restricted=args.allow_restricted,
            )
            _emit(export)
            return 0
        parser.error("unknown command")
    except (ModelStateError, StorageError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
