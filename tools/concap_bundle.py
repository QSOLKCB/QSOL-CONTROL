#!/usr/bin/env python3
"""CLI for deterministic portable CONCAP bundle construction and verification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from storage.concap_bundle import (
    ConcapBundleError,
    build_bundle,
    canonical_json_bytes,
    verify_bundle,
    write_deterministic_zip,
)


def emit(value) -> None:
    sys.stdout.buffer.write(canonical_json_bytes(value) + b"\n")


def command_build(args: argparse.Namespace) -> int:
    report = build_bundle(
        source_root=Path(args.source_root),
        export_spec_path=Path(args.export_spec),
        output_dir=Path(args.output_dir),
    )
    if args.zip_output:
        report = {
            **report,
            "zip_output": args.zip_output,
            "zip_sha256": write_deterministic_zip(
                Path(args.output_dir), Path(args.zip_output)
            ),
        }
    emit(report)
    return 0


def command_verify(args: argparse.Namespace) -> int:
    emit(verify_bundle(Path(args.bundle)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and verify transport-neutral portable CONCAP bundles"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="build a portable bundle from an explicit export spec")
    build.add_argument("--source-root", required=True)
    build.add_argument("--export-spec", required=True)
    build.add_argument("--output-dir", required=True)
    build.add_argument("--zip-output", help="optional deterministic ZIP written outside the bundle")
    build.set_defaults(func=command_build)

    verify = sub.add_parser("verify", help="verify a portable bundle and every contained restore object")
    verify.add_argument("--bundle", required=True)
    verify.set_defaults(func=command_verify)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (ConcapBundleError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"CONCAP bundle error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
