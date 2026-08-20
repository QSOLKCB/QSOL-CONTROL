#!/usr/bin/env python3
"""Dependency-free CLI for Phase 8 repository-level CONTROL recovery packages."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from storage.ark_repository_bundle import (
    ArkRepositoryBundleError,
    DEFAULT_DNA_MAX_FILE_BYTES,
    build_repository_recovery_package,
    restore_repository_recovery_package,
    source_privacy_class,
    verify_repository_recovery_package,
)
from storage.control_store import StorageError


def emit(value) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def command_export(args: argparse.Namespace) -> int:
    privacy = source_privacy_class(args.root)
    if privacy == "RESTRICTED":
        if not args.allow_restricted:
            raise ArkRepositoryBundleError(
                "RESTRICTED repository recovery export requires --allow-restricted"
            )
        if not args.acknowledge_recovery_export:
            raise ArkRepositoryBundleError(
                "RESTRICTED repository recovery export requires --acknowledge-recovery-export"
            )
        if not args.actor or not args.actor.strip():
            raise ArkRepositoryBundleError(
                "RESTRICTED repository recovery export requires --actor"
            )
    report = build_repository_recovery_package(
        args.root,
        args.output,
        repository_root=args.repository_root,
        include_indexes=args.include_index_descriptors,
        include_dna=args.include_dna,
        dna_max_file_bytes=args.dna_max_file_bytes,
    )
    emit(
        {
            **report,
            "output": str(args.output),
            "actor": args.actor if privacy == "RESTRICTED" else None,
        }
    )
    return 0


def command_verify(args: argparse.Namespace) -> int:
    emit(verify_repository_recovery_package(args.package))
    return 0


def command_restore(args: argparse.Namespace) -> int:
    emit(restore_repository_recovery_package(args.package, args.target))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="QSOL-CONTROL Phase 8 repository-level ARK recovery bridge"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser(
        "export",
        help="export canonical CONTROL repository state into deterministic recovery capsules",
    )
    export.add_argument("--root", default=".qsol-control-store")
    export.add_argument("--repository-root", default=str(ROOT))
    export.add_argument("--output", required=True)
    export.add_argument("--include-index-descriptors", action="store_true")
    export.add_argument("--include-dna", action="store_true")
    export.add_argument(
        "--dna-max-file-bytes",
        type=int,
        default=DEFAULT_DNA_MAX_FILE_BYTES,
        help="maximum source File size eligible for optional DNA projection",
    )
    export.add_argument("--allow-restricted", action="store_true")
    export.add_argument("--acknowledge-recovery-export", action="store_true")
    export.add_argument("--actor")
    export.set_defaults(func=command_export)

    verify = sub.add_parser(
        "verify", help="verify capsules and reconstruct into a temporary standard-library store"
    )
    verify.add_argument("package")
    verify.set_defaults(func=command_verify)

    restore = sub.add_parser(
        "restore", help="reconstruct package into a new directory containing store/ and support files"
    )
    restore.add_argument("package")
    restore.add_argument("--target", required=True)
    restore.set_defaults(func=command_restore)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (ArkRepositoryBundleError, StorageError, OSError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
