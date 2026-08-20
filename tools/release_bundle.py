#!/usr/bin/env python3
"""Build and verify byte-reproducible QSOL-CONTROL release bundles.

Release ZIPs use ZIP_STORED only. Verification validates archive bounds before reading
members, never extracts the archive, and never accepts compressed untrusted payloads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from storage.archive_safety import ArchiveSafetyError, validate_zip_archive

INVENTORY_PATH = ROOT / "release" / "release-inventory.json"
PROTOCOL = "qsol-control-release-bundle/1"
SCHEMA_VERSION = "1.0.0"
CONTRACT_VERSION = "2.6.0"
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
MEMBER_MODE = 0o100644
RELEASE_BOUNDARIES = [
    "RELEASE_BUNDLE != PUBLICATION_AUTHORITY",
    "RELEASE_HASH != SEMANTIC_TRUTH",
    "REPRODUCIBLE_BYTES != REPRODUCIBLE_LIVE_INFERENCE",
    "ARCHIVE_VERIFY != ARCHIVE_EXECUTE",
    "COMPRESSED_UNTRUSTED_INPUT != ACCEPTED_BY_DEFAULT",
]


class ReleaseError(ValueError):
    """Raised when release inventory/build/verification violates the contract."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_ref(data: bytes) -> str:
    return "sha256:" + sha256_hex(data)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ReleaseError(f"duplicate JSON member: {key}")
        out[key] = value
    return out


def _reject_constant(value: str) -> None:
    raise ReleaseError(f"non-finite JSON number rejected: {value}")


def load_json(path: Path, *, max_bytes: int = 4 * 1024 * 1024) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ReleaseError(f"JSON input must be a regular non-symlink file: {path}")
    if path.stat().st_size > max_bytes:
        raise ReleaseError(f"JSON input exceeds byte limit: {path}")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except ReleaseError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ReleaseError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ReleaseError(f"JSON root must be an object: {path}")
    return value


def canonical_relative_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ReleaseError("release inventory path must be canonical relative POSIX")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ReleaseError("release inventory path contains absolute/dot/parent segment")
    if path.as_posix() != value:
        raise ReleaseError("release inventory path is not canonical POSIX")
    return value


def load_inventory(source_root: Path) -> dict[str, Any]:
    path = source_root / "release" / "release-inventory.json"
    inventory = load_json(path)
    if inventory.get("protocol") != "qsol-control-release-inventory/1":
        raise ReleaseError("release inventory protocol mismatch")
    if inventory.get("repository_contract_version") != CONTRACT_VERSION:
        raise ReleaseError("release inventory contract version mismatch")
    for field in ("top_level_files", "roots", "extra_files", "excluded_names", "excluded_suffixes"):
        if not isinstance(inventory.get(field), list) or any(not isinstance(x, str) or not x for x in inventory[field]):
            raise ReleaseError(f"release inventory {field} must be a string array")
    if inventory.get("symlinks_allowed") is not False:
        raise ReleaseError("release inventory must forbid symlinks")
    for field in ("max_file_count", "max_file_bytes", "max_total_bytes"):
        value = inventory.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ReleaseError(f"release inventory {field} invalid")
    return inventory


def _resolve_file(source_root: Path, relative: str) -> Path:
    canonical_relative_path(relative)
    candidate = source_root
    for part in PurePosixPath(relative).parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ReleaseError(f"release inventory traverses symlink: {relative}")
    if not candidate.is_file():
        raise ReleaseError(f"release inventory file missing: {relative}")
    try:
        candidate.resolve().relative_to(source_root.resolve())
    except ValueError as exc:
        raise ReleaseError(f"release inventory file escapes source root: {relative}") from exc
    return candidate


def collect_files(source_root: Path, inventory: dict[str, Any]) -> list[dict[str, Any]]:
    if source_root.is_symlink() or not source_root.is_dir():
        raise ReleaseError("source root must be an existing non-symlink directory")
    excluded_names = set(inventory["excluded_names"])
    excluded_suffixes = tuple(inventory["excluded_suffixes"])
    relatives: set[str] = set()

    for relative in inventory["top_level_files"] + inventory["extra_files"]:
        relatives.add(canonical_relative_path(relative))

    for root_name in inventory["roots"]:
        root_relative = canonical_relative_path(root_name)
        root_path = source_root / root_relative
        if root_path.is_symlink() or not root_path.is_dir():
            raise ReleaseError(f"release inventory root missing or symlinked: {root_relative}")
        for path in root_path.rglob("*"):
            relative = path.relative_to(source_root).as_posix()
            if path.is_symlink():
                raise ReleaseError(f"symlink inside release inventory root: {relative}")
            if not path.is_file():
                continue
            parts = PurePosixPath(relative).parts
            if any(part in excluded_names for part in parts):
                continue
            if excluded_suffixes and relative.endswith(excluded_suffixes):
                continue
            relatives.add(canonical_relative_path(relative))

    ordered = sorted(relatives, key=lambda value: value.encode("utf-8"))
    if len(ordered) > inventory["max_file_count"]:
        raise ReleaseError("release file count exceeds inventory limit")
    files: list[dict[str, Any]] = []
    total = 0
    for relative in ordered:
        path = _resolve_file(source_root, relative)
        size = path.stat().st_size
        if size > inventory["max_file_bytes"]:
            raise ReleaseError(f"release file exceeds byte limit: {relative}")
        total += size
        if total > inventory["max_total_bytes"]:
            raise ReleaseError("release total file bytes exceed inventory limit")
        files.append({"path": relative, "size_bytes": size, "sha256": sha256_file(path)})
    if not files:
        raise ReleaseError("release inventory resolved to no files")
    return files


def _tree_sha256(files: list[dict[str, Any]]) -> str:
    projection = [
        {"path": row["path"], "size_bytes": row["size_bytes"], "sha256": row["sha256"]}
        for row in files
    ]
    return sha256_hex(canonical_json_bytes(projection))


def build_manifest(*, release_version: str, source_commit: str, files: list[dict[str, Any]]) -> dict[str, Any]:
    if SEMVER.fullmatch(release_version) is None:
        raise ReleaseError("release_version must be MAJOR.MINOR.PATCH")
    if SHA40.fullmatch(source_commit) is None:
        raise ReleaseError("source_commit must be 40 lowercase hex")
    payload = {
        "type": "qsol-control-release-manifest",
        "protocol": PROTOCOL,
        "schema_version": SCHEMA_VERSION,
        "release_version": release_version,
        "repository_contract_version": CONTRACT_VERSION,
        "source_commit": source_commit,
        "source_tree_sha256": _tree_sha256(files),
        "inventory_protocol": "qsol-control-release-inventory/1",
        "file_count": len(files),
        "total_file_bytes": sum(row["size_bytes"] for row in files),
        "files": files,
        "archive_format": "zip",
        "compression": "ZIP_STORED",
        "authority": "release-integrity-only",
        "semantic_authority_claimed": False,
        "boundaries": RELEASE_BOUNDARIES,
    }
    return {"release_id": sha256_ref(canonical_json_bytes(payload)), **payload}


def validate_manifest(manifest: dict[str, Any]) -> None:
    required = {
        "release_id", "type", "protocol", "schema_version", "release_version",
        "repository_contract_version", "source_commit", "source_tree_sha256",
        "inventory_protocol", "file_count", "total_file_bytes", "files",
        "archive_format", "compression", "authority", "semantic_authority_claimed",
        "boundaries",
    }
    if set(manifest) != required:
        raise ReleaseError("release manifest field set mismatch")
    if manifest["type"] != "qsol-control-release-manifest" or manifest["protocol"] != PROTOCOL:
        raise ReleaseError("release manifest protocol mismatch")
    if manifest["schema_version"] != SCHEMA_VERSION or manifest["repository_contract_version"] != CONTRACT_VERSION:
        raise ReleaseError("release manifest version mismatch")
    if SEMVER.fullmatch(manifest["release_version"]) is None or SHA40.fullmatch(manifest["source_commit"]) is None:
        raise ReleaseError("release manifest release/source version invalid")
    if not isinstance(manifest["source_tree_sha256"], str) or SHA64.fullmatch(manifest["source_tree_sha256"]) is None:
        raise ReleaseError("release manifest source_tree_sha256 invalid")
    if manifest["inventory_protocol"] != "qsol-control-release-inventory/1":
        raise ReleaseError("release inventory protocol mismatch")
    if manifest["archive_format"] != "zip" or manifest["compression"] != "ZIP_STORED":
        raise ReleaseError("release archive contract mismatch")
    if manifest["authority"] != "release-integrity-only" or manifest["semantic_authority_claimed"] is not False:
        raise ReleaseError("release authority boundary mismatch")
    if manifest["boundaries"] != RELEASE_BOUNDARIES:
        raise ReleaseError("release boundaries drift")
    files = manifest["files"]
    if not isinstance(files, list) or not files or len(files) != manifest["file_count"]:
        raise ReleaseError("release file count mismatch")
    prior: bytes | None = None
    total = 0
    seen: set[str] = set()
    for row in files:
        if not isinstance(row, dict) or set(row) != {"path", "size_bytes", "sha256"}:
            raise ReleaseError("release file entry shape mismatch")
        relative = canonical_relative_path(row["path"])
        encoded = relative.encode("utf-8")
        if prior is not None and prior >= encoded:
            raise ReleaseError("release files must be strictly UTF-8 sorted")
        prior = encoded
        if relative in seen:
            raise ReleaseError("duplicate release file path")
        seen.add(relative)
        if not isinstance(row["size_bytes"], int) or isinstance(row["size_bytes"], bool) or row["size_bytes"] < 0:
            raise ReleaseError("release file size invalid")
        if not isinstance(row["sha256"], str) or SHA64.fullmatch(row["sha256"]) is None:
            raise ReleaseError("release file hash invalid")
        total += row["size_bytes"]
    if total != manifest["total_file_bytes"]:
        raise ReleaseError("release total_file_bytes mismatch")
    if _tree_sha256(files) != manifest["source_tree_sha256"]:
        raise ReleaseError("release source tree fingerprint mismatch")
    payload = {key: value for key, value in manifest.items() if key != "release_id"}
    if manifest["release_id"] != sha256_ref(canonical_json_bytes(payload)):
        raise ReleaseError("release manifest identity mismatch")


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_TIME)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = (MEMBER_MODE & 0xFFFF) << 16
    info.extra = b""
    info.comment = b""
    return info


def build_release(*, source_root: Path, output: Path, release_version: str, source_commit: str) -> dict[str, Any]:
    inventory = load_inventory(source_root)
    files = collect_files(source_root, inventory)
    manifest = build_manifest(release_version=release_version, source_commit=source_commit, files=files)
    validate_manifest(manifest)
    manifest_bytes = canonical_json_bytes(manifest) + b"\n"
    if output.is_symlink() or output.exists():
        raise ReleaseError("release output must not already exist or be a symlink")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "w+b") as raw:
            with zipfile.ZipFile(raw, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
                archive.comment = b""
                members: list[tuple[str, bytes | Path]] = [("RELEASE.json", manifest_bytes)]
                members.extend((row["path"], source_root / row["path"]) for row in files)
                for name, source in sorted(members, key=lambda item: item[0].encode("utf-8")):
                    data = source if isinstance(source, bytes) else source.read_bytes()
                    archive.writestr(_zip_info(name), data)
    except Exception:
        if output.exists():
            output.unlink()
        raise
    verification = verify_release(output)
    return {**verification, "release_id": manifest["release_id"], "source_tree_sha256": manifest["source_tree_sha256"]}


def verify_release(path: str | Path) -> dict[str, Any]:
    archive_path = Path(path)
    try:
        safety = validate_zip_archive(archive_path)
    except ArchiveSafetyError as exc:
        raise ReleaseError(str(exc)) from exc
    try:
        with zipfile.ZipFile(archive_path, "r", allowZip64=True) as archive:
            names = archive.namelist()
            if "RELEASE.json" not in names:
                raise ReleaseError("release archive is missing RELEASE.json")
            raw_manifest = archive.read("RELEASE.json")
            if len(raw_manifest) > 4 * 1024 * 1024:
                raise ReleaseError("RELEASE.json exceeds byte limit")
            try:
                manifest = json.loads(
                    raw_manifest.decode("utf-8"),
                    object_pairs_hook=_pairs,
                    parse_constant=_reject_constant,
                )
            except ReleaseError:
                raise
            except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
                raise ReleaseError("invalid RELEASE.json") from exc
            if not isinstance(manifest, dict):
                raise ReleaseError("RELEASE.json root must be an object")
            validate_manifest(manifest)
            expected_names = {"RELEASE.json", *(row["path"] for row in manifest["files"])}
            if set(names) != expected_names or len(names) != len(expected_names):
                raise ReleaseError("release archive member set mismatch")
            for row in manifest["files"]:
                data = archive.read(row["path"])
                if len(data) != row["size_bytes"] or sha256_hex(data) != row["sha256"]:
                    raise ReleaseError(f"release member identity mismatch: {row['path']}")
    except ReleaseError:
        raise
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise ReleaseError(f"release archive verification failed: {exc}") from exc
    return {
        "status": "verified",
        "protocol": PROTOCOL,
        "release_version": manifest["release_version"],
        "source_commit": manifest["source_commit"],
        "release_id": manifest["release_id"],
        "source_tree_sha256": manifest["source_tree_sha256"],
        "archive_sha256": sha256_file(archive_path),
        "member_count": safety["member_count"],
        "decompression_performed": False,
    }


def check_repository(source_root: Path = ROOT) -> dict[str, Any]:
    manifest = load_json(source_root / "manifest.json")
    bootstrap = load_json(source_root / "README4AI.md")
    migration = load_json(source_root / "ai" / "migration-policy.json")
    release_contract = load_json(source_root / "ai" / "release-contract.json")
    roadmap = (source_root / "ROADMAP.md").read_text(encoding="utf-8")
    changelog = (source_root / "CHANGELOG.md").read_text(encoding="utf-8")
    checklist = (source_root / "RELEASE-CHECKLIST.md").read_text(encoding="utf-8")
    if manifest.get("schema_version") != CONTRACT_VERSION:
        raise ReleaseError("manifest contract version is not Phase 10 target")
    if manifest.get("status", {}).get("completed_through_roadmap_phase") != 10:
        raise ReleaseError("manifest does not report completion through Phase 10")
    if bootstrap.get("contracts", {}).get("schema_version") != CONTRACT_VERSION:
        raise ReleaseError("README4AI contract version is not Phase 10 target")
    phase10 = roadmap.split("## Phase 10 — Hardening and release discipline", 1)[1].split("## Deferred / explicitly not promised yet", 1)[0]
    if "- [ ]" in phase10:
        raise ReleaseError("Phase 10 roadmap still contains unchecked items")
    if migration.get("current_contract_version") != CONTRACT_VERSION:
        raise ReleaseError("migration policy does not target Phase 10 contract")
    if release_contract.get("repository_contract_version") != CONTRACT_VERSION:
        raise ReleaseError("release contract does not target Phase 10 contract")
    if "## Unreleased" not in changelog or "Phase 10" not in changelog:
        raise ReleaseError("CHANGELOG.md is missing Phase 10 Unreleased discipline")
    for required in ("release bundle", "migration", "secret", "adversarial", "changelog"):
        if required.lower() not in checklist.lower():
            raise ReleaseError(f"release checklist missing required discipline: {required}")
    return {"status": "ready", "repository_contract_version": CONTRACT_VERSION, "phase": 10}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build/verify deterministic QSOL-CONTROL release bundles")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="validate Phase 10 release readiness")
    build = sub.add_parser("build", help="build a deterministic ZIP_STORED release bundle")
    build.add_argument("--source-root", default=str(ROOT))
    build.add_argument("--output", required=True)
    build.add_argument("--release-version", required=True)
    build.add_argument("--source-commit", required=True)
    verify = sub.add_parser("verify", help="verify a release bundle without extraction/decompression")
    verify.add_argument("archive")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "check":
            result = check_repository(ROOT)
        elif args.command == "build":
            source_root = Path(args.source_root).resolve()
            check_repository(source_root)
            result = build_release(
                source_root=source_root,
                output=Path(args.output),
                release_version=args.release_version,
                source_commit=args.source_commit,
            )
        else:
            result = verify_release(args.archive)
    except (ReleaseError, OSError) as exc:
        print(f"release error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
