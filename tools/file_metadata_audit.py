#!/usr/bin/env python3
"""Audit persisted CONTROL File/Collection metadata for obvious secrets.

This is an import/read-side complement to write-time secret rejection. It never
redacts in place: a suspicious canonical record fails closed and must be repaired at
its source rather than silently rewritten under the same identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

MAX_RECORD_BYTES = 4 * 1024 * 1024
MAX_RECORDS = 100_000
SHA256_REF = re.compile(r"^sha256:[0-9a-f]{64}$")
FORBIDDEN_KEYS = {
    "apikey",
    "accesstoken",
    "refreshtoken",
    "authtoken",
    "bearertoken",
    "authorization",
    "clientsecret",
    "privatekey",
    "credential",
    "credentials",
    "password",
    "passwd",
    "sessiontoken",
    "cookie",
    "setcookie",
}
FORBIDDEN_MARKERS = (
    "ghp_",
    "github_pat_",
    "gho_",
    "ghs_",
    "glpat-",
    "xoxb-",
    "xoxp-",
    "Bearer ",
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "AKIA",
)
CREDENTIAL_QUERY = re.compile(
    r"(?i)(?:^|[?&;\s])(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd)=([^&;\s]+)"
)


class MetadataAuditError(ValueError):
    """Raised when imported/persisted metadata violates the secret policy."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_ref(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _normalize_key(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def reject_secrets(value: Any, where: str = "metadata") -> None:
    """Recursively reject credential-labelled keys and high-confidence values."""

    stack: list[tuple[Any, str]] = [(value, where)]
    while stack:
        current, path = stack.pop()
        if isinstance(current, dict):
            for key, child in current.items():
                if not isinstance(key, str):
                    raise MetadataAuditError(f"{path}: metadata keys must be strings")
                if _normalize_key(key) in FORBIDDEN_KEYS:
                    raise MetadataAuditError(f"{path}.{key}: credential-labelled field is forbidden")
                stack.append((child, f"{path}.{key}"))
        elif isinstance(current, list):
            for index, child in enumerate(current):
                stack.append((child, f"{path}[{index}]"))
        elif isinstance(current, str):
            if any(marker in current for marker in FORBIDDEN_MARKERS):
                raise MetadataAuditError(f"{path}: forbidden credential marker detected")
            if CREDENTIAL_QUERY.search(current):
                raise MetadataAuditError(f"{path}: credential-bearing locator/query detected")
        elif current is None or isinstance(current, (bool, int, float)):
            continue
        else:
            raise MetadataAuditError(f"{path}: unsupported metadata value type")


def _reject_constant(value: str) -> None:
    raise MetadataAuditError(f"non-finite JSON number rejected: {value}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise MetadataAuditError(f"duplicate JSON member: {key}")
        out[key] = value
    return out


def _load_record(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise MetadataAuditError(f"record must be a regular non-symlink file: {path}")
    size = path.stat().st_size
    if size > MAX_RECORD_BYTES:
        raise MetadataAuditError(f"record exceeds {MAX_RECORD_BYTES} byte limit: {path}")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except MetadataAuditError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise MetadataAuditError(f"invalid canonical JSON record: {path}") from exc
    if not isinstance(value, dict):
        raise MetadataAuditError(f"record root must be an object: {path}")
    return value


def _audit_file_record(path: Path) -> None:
    record = _load_record(path)
    if record.get("protocol") != "qsol-control-file/1":
        raise MetadataAuditError(f"unexpected File protocol: {path}")
    file_id = record.get("file_id")
    if not isinstance(file_id, str) or SHA256_REF.fullmatch(file_id) is None:
        raise MetadataAuditError(f"invalid file_id: {path}")
    if path.stem != file_id.split(":", 1)[1]:
        raise MetadataAuditError(f"File record path/identity mismatch: {path}")
    payload = {key: value for key, value in record.items() if key != "file_id"}
    if sha256_ref(canonical_json_bytes(payload)) != file_id:
        raise MetadataAuditError(f"File record content identity mismatch: {path}")
    reject_secrets(record.get("source"), "file.source")
    reject_secrets(record.get("metadata"), "file.metadata")


def _audit_collection_descriptor(path: Path) -> None:
    record = _load_record(path)
    if record.get("protocol") != "qsol-control-collection/1":
        raise MetadataAuditError(f"unexpected Collection protocol: {path}")
    reject_secrets(record.get("metadata"), "collection.metadata")


def audit_store(root: str | Path) -> dict[str, Any]:
    store = Path(root)
    if store.is_symlink() or not store.is_dir():
        raise MetadataAuditError("CONTROL store root must be an existing non-symlink directory")

    files_dir = store / "records" / "files"
    collections_dir = store / "records" / "collections"
    file_paths = sorted(files_dir.glob("*.json")) if files_dir.is_dir() else []
    collection_paths = (
        sorted(collections_dir.glob("*/collection.json")) if collections_dir.is_dir() else []
    )
    if len(file_paths) + len(collection_paths) > MAX_RECORDS:
        raise MetadataAuditError("metadata audit record count exceeds limit")

    for path in file_paths:
        _audit_file_record(path)
    for path in collection_paths:
        _audit_collection_descriptor(path)

    return {
        "status": "clean",
        "file_records": len(file_paths),
        "collection_descriptors": len(collection_paths),
        "redaction_performed": False,
        "forbidden_material_persisted": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit CONTROL File/Collection metadata for secrets")
    parser.add_argument("--root", required=True, help="existing CONTROL store root")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = audit_store(args.root)
    except MetadataAuditError as exc:
        print(f"metadata audit failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(result, sort_keys=True, separators=(",", ":"))
        if args.json
        else json.dumps(result, indent=2, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
