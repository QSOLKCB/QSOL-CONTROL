#!/usr/bin/env python3
"""Operator CLI for deterministic QSOL cold-restore capsules."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from storage.restore_capsule import (
    PACK_SPEC_PROTOCOL,
    RestoreCapsuleError,
    capsule_contains_restricted,
    decode_capsule_dna,
    encode_capsule_dna,
    pack_capsule,
    parse_capsule,
    verify_capsule,
)


def emit(value) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def load_json(path: Path):
    if path.is_symlink():
        raise RestoreCapsuleError(f"refusing symlink input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def refuse_symlink_output(path: Path) -> None:
    if path.is_symlink():
        raise RestoreCapsuleError(f"refusing symlink output: {path}")


def command_pack(args: argparse.Namespace) -> int:
    spec_path = Path(args.spec).resolve()
    spec = load_json(spec_path)
    if not isinstance(spec, dict) or spec.get("protocol") != PACK_SPEC_PROTOCOL:
        raise RestoreCapsuleError("restore pack spec protocol mismatch")
    entries = spec.get("entries")
    if not isinstance(entries, list) or not entries:
        raise RestoreCapsuleError("restore pack spec requires a non-empty entries list")

    base = spec_path.parent
    prepared = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise RestoreCapsuleError(f"pack entry {index} must be an object")
        allowed = {
            "logical_path", "source_path", "kind", "privacy_class",
            "recovery_class", "source_ref",
        }
        extra = sorted(set(entry) - allowed)
        if extra:
            raise RestoreCapsuleError(f"pack entry {index} has unsupported fields: {extra}")
        source_path = entry.get("source_path")
        if not isinstance(source_path, str) or not source_path:
            raise RestoreCapsuleError(f"pack entry {index} source_path is invalid")
        source = (base / source_path).resolve()
        try:
            source.relative_to(base.resolve())
        except ValueError as exc:
            raise RestoreCapsuleError("pack source escapes the spec directory") from exc
        if source.is_symlink() or not source.is_file():
            raise RestoreCapsuleError(f"pack source is missing or symlinked: {source_path}")
        prepared.append(
            {
                "logical_path": entry.get("logical_path"),
                "data": source.read_bytes(),
                "kind": entry.get("kind"),
                "privacy_class": entry.get("privacy_class"),
                "recovery_class": entry.get("recovery_class"),
                "source_ref": entry.get("source_ref"),
            }
        )

    capsule = pack_capsule(prepared)
    output = Path(args.output)
    refuse_symlink_output(output)
    output.write_bytes(capsule)
    report = verify_capsule(capsule)
    report["output"] = str(output)
    emit(report)
    return 0


def command_verify(args: argparse.Namespace) -> int:
    path = Path(args.capsule)
    if path.is_symlink():
        raise RestoreCapsuleError("verify refuses symlink capsule inputs")
    emit(verify_capsule(path.read_bytes()))
    return 0


def command_inspect(args: argparse.Namespace) -> int:
    path = Path(args.capsule)
    if path.is_symlink():
        raise RestoreCapsuleError("inspect refuses symlink capsule inputs")
    manifest, _ = parse_capsule(path.read_bytes())
    emit(manifest)
    return 0


def command_unpack(args: argparse.Namespace) -> int:
    path = Path(args.capsule)
    if path.is_symlink():
        raise RestoreCapsuleError("unpack refuses symlink capsule inputs")
    capsule = path.read_bytes()
    report = verify_capsule(capsule)
    _, entries = parse_capsule(capsule)
    destination = Path(args.output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)

    written = []
    for entry in entries:
        target = destination / entry["logical_path"]
        resolved_parent = target.parent.resolve()
        try:
            resolved_parent.relative_to(destination)
        except ValueError as exc:
            raise RestoreCapsuleError("unpack target escapes destination") from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            raise RestoreCapsuleError(f"unpack refuses symlink target: {target}")
        if target.exists() and not args.overwrite:
            raise RestoreCapsuleError(f"unpack target exists: {target}")
        target.write_bytes(entry["data"])
        written.append(entry["logical_path"])

    emit({**report, "output_dir": str(destination), "written": written})
    return 0


def command_dna_export(args: argparse.Namespace) -> int:
    path = Path(args.capsule)
    if path.is_symlink():
        raise RestoreCapsuleError("dna-export refuses symlink capsule inputs")
    capsule = path.read_bytes()
    restricted = capsule_contains_restricted(capsule)
    if restricted and not args.allow_restricted:
        raise RestoreCapsuleError("RESTRICTED restore capsule DNA export requires --allow-restricted")
    if restricted and not args.acknowledge_reversible_sensitive_export:
        raise RestoreCapsuleError(
            "RESTRICTED restore capsule DNA export also requires --acknowledge-reversible-sensitive-export"
        )
    projection = encode_capsule_dna(capsule)
    output = Path(args.output)
    refuse_symlink_output(output)
    output.write_text(
        json.dumps(projection, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    emit(
        {
            "status": "written",
            "output": str(output),
            "restricted": restricted,
            "projection_id": projection["projection_id"],
            "restore_capsule_sha256": projection["restore_capsule_sha256"],
        }
    )
    return 0


def command_dna_decode(args: argparse.Namespace) -> int:
    path = Path(args.projection)
    if path.is_symlink():
        raise RestoreCapsuleError("dna-decode refuses symlink projection inputs")
    projection = load_json(path)
    if not isinstance(projection, dict):
        raise RestoreCapsuleError("DNA projection must contain an object")
    capsule = decode_capsule_dna(projection)
    output = Path(args.output)
    refuse_symlink_output(output)
    output.write_bytes(capsule)
    emit({**verify_capsule(capsule), "output": str(output)})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QSOL cold-restore capsule operations")
    sub = parser.add_subparsers(dest="command", required=True)

    pack = sub.add_parser("pack", help="build one QSOL-RESTORE-DAT/1 capsule")
    pack.add_argument("--spec", required=True)
    pack.add_argument("--output", required=True)
    pack.set_defaults(func=command_pack)

    verify = sub.add_parser("verify", help="verify capsule integrity and fixed-point reconstruction")
    verify.add_argument("capsule")
    verify.set_defaults(func=command_verify)

    inspect = sub.add_parser("inspect", help="print the verified embedded capsule manifest")
    inspect.add_argument("capsule")
    inspect.set_defaults(func=command_inspect)

    unpack = sub.add_parser("unpack", help="verify and safely unpack a capsule")
    unpack.add_argument("capsule")
    unpack.add_argument("--output-dir", required=True)
    unpack.add_argument("--overwrite", action="store_true")
    unpack.set_defaults(func=command_unpack)

    dna_export = sub.add_parser("dna-export", help="encode a capsule using CONTROL's DNA/lattice codec")
    dna_export.add_argument("capsule")
    dna_export.add_argument("--output", required=True)
    dna_export.add_argument("--allow-restricted", action="store_true")
    dna_export.add_argument("--acknowledge-reversible-sensitive-export", action="store_true")
    dna_export.set_defaults(func=command_dna_export)

    dna_decode = sub.add_parser("dna-decode", help="decode and verify a restore capsule DNA projection")
    dna_decode.add_argument("projection")
    dna_decode.add_argument("--output", required=True)
    dna_decode.set_defaults(func=command_dna_decode)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (RestoreCapsuleError, OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
