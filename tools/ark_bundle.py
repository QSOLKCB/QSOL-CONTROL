#!/usr/bin/env python3
"""Operator CLI for minimum QSOL-CONTROL -> ARK recovery bundles."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from storage.ark_recovery_bundle import (
    ArkBundleError,
    build_ark_bundle,
    bundle_privacy_class,
    restore_ark_bundle,
    verify_ark_bundle,
)
from storage.control_store import StorageError
from storage.interaction_store import InteractionStore


def emit(value) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def _atomic_owner_write(path: Path, data: bytes) -> None:
    if path.is_symlink():
        raise ArkBundleError("output path must not be a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp = Path(temp_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        os.chmod(path, 0o600)
    finally:
        if temp.exists():
            temp.unlink()


def command_export(args: argparse.Namespace) -> int:
    store = InteractionStore(args.root)
    capsule = build_ark_bundle(store, args.run_id)
    privacy = bundle_privacy_class(capsule)
    if privacy == "RESTRICTED":
        if not args.allow_restricted:
            raise ArkBundleError("RESTRICTED recovery export requires --allow-restricted")
        if not args.acknowledge_recovery_export:
            raise ArkBundleError(
                "RESTRICTED recovery export requires --acknowledge-recovery-export"
            )
        if not args.actor or not args.actor.strip():
            raise ArkBundleError("RESTRICTED recovery export requires --actor")
    output = Path(args.output)
    _atomic_owner_write(output, capsule)
    report = verify_ark_bundle(capsule)
    emit(
        {
            **report,
            "output": str(output),
            "file_mode": "0600",
            "actor": args.actor if privacy == "RESTRICTED" else None,
        }
    )
    return 0


def command_verify(args: argparse.Namespace) -> int:
    path = Path(args.bundle)
    if path.is_symlink():
        raise ArkBundleError("bundle input must not be a symlink")
    emit(verify_ark_bundle(path.read_bytes()))
    return 0


def command_restore(args: argparse.Namespace) -> int:
    path = Path(args.bundle)
    if path.is_symlink():
        raise ArkBundleError("bundle input must not be a symlink")
    emit(restore_ark_bundle(path.read_bytes(), args.target))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QSOL-CONTROL minimum ARK recovery bundle")
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export", help="export one run as a minimum ARK recovery capsule")
    export.add_argument("--root", default=".qsol-control-store")
    export.add_argument("run_id")
    export.add_argument("--output", required=True)
    export.add_argument("--allow-restricted", action="store_true")
    export.add_argument("--acknowledge-recovery-export", action="store_true")
    export.add_argument("--actor")
    export.set_defaults(func=command_export)

    verify = sub.add_parser("verify", help="verify a bundle by offline reconstruction")
    verify.add_argument("bundle")
    verify.set_defaults(func=command_verify)

    restore = sub.add_parser("restore", help="restore a bundle into a new CONTROL store")
    restore.add_argument("bundle")
    restore.add_argument("--target", required=True)
    restore.set_defaults(func=command_restore)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (ArkBundleError, StorageError, OSError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
