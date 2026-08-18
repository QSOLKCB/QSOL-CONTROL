#!/usr/bin/env python3
"""Dependency-free semantic validator for QSOL cold-restore contracts."""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schema" / "restore-pack-spec.schema.json"
VALID = ROOT / "examples" / "schema" / "restore-pack-spec.valid.json"
INVALID = ROOT / "examples" / "schema" / "restore-pack-spec.invalid.json"
RECOVERY_CLASSES = {
    "NEAR_SHELL",
    "MID_SHELL",
    "OUTER_SHELL",
    "RESONANCE_NODE",
    "WIGGLE_ZONE",
}
CAPSULE_RE = re.compile(r"^[A-Za-z0-9._-]{1,256}\.dat$")


def load_json(path: Path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain an object")
    return value


def validate_path(value, field):
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError(f"{field} must contain 1..512 characters")
    if "\\" in value or "\x00" in value or "\n" in value or "\r" in value:
        raise ValueError(f"{field} contains forbidden characters")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{field} must be a canonical relative path")
    if path.as_posix() != value:
        raise ValueError(f"{field} must already be canonical POSIX form")


def validate_pack_spec(value):
    if set(value) != {"protocol", "capsule", "recovery_class", "entries"}:
        raise ValueError("restore pack spec fields mismatch")
    if value["protocol"] != "qsol-control-restore-pack-spec/1":
        raise ValueError("restore pack spec protocol mismatch")
    if not isinstance(value["capsule"], str) or CAPSULE_RE.fullmatch(value["capsule"]) is None:
        raise ValueError("restore pack capsule name is invalid")
    if value["recovery_class"] not in RECOVERY_CLASSES:
        raise ValueError("restore pack recovery class is invalid")
    entries = value["entries"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= 4096:
        raise ValueError("restore pack entries count is invalid")
    seen = set()
    for entry in entries:
        required = {
            "logical_path", "source_path", "kind", "privacy_class",
            "recovery_class", "source_ref",
        }
        if not isinstance(entry, dict) or set(entry) != required:
            raise ValueError("restore pack entry fields mismatch")
        validate_path(entry["logical_path"], "logical_path")
        validate_path(entry["source_path"], "source_path")
        if entry["logical_path"] in seen:
            raise ValueError("restore pack logical paths must be unique")
        seen.add(entry["logical_path"])
        if not isinstance(entry["kind"], str) or not 1 <= len(entry["kind"]) <= 128:
            raise ValueError("restore pack entry kind is invalid")
        if entry["privacy_class"] not in {"PUBLIC", "INTERNAL", "RESTRICTED"}:
            raise ValueError("restore pack privacy class is invalid")
        if entry["recovery_class"] != value["recovery_class"]:
            raise ValueError("restore pack entries must use the capsule recovery class")
        if not isinstance(entry["source_ref"], str) or not 1 <= len(entry["source_ref"]) <= 2048:
            raise ValueError("restore pack source_ref is invalid")


def validate():
    schema = load_json(SCHEMA)
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise ValueError("restore pack schema must declare JSON Schema draft 2020-12")
    if not schema.get("$id"):
        raise ValueError("restore pack schema requires $id")
    validate_pack_spec(load_json(VALID))
    try:
        validate_pack_spec(load_json(INVALID))
    except ValueError:
        pass
    else:
        raise ValueError("invalid restore pack fixture unexpectedly passed")

    docs = (ROOT / "docs" / "COLD-RESTORE.md").read_text(encoding="utf-8")
    for phrase in (
        "RESTORE_CAPSULE != MODEL_MEMORY",
        "RESTORED_CONTEXT != ORIGINAL_ASSISTANT_INSTANCE",
        "DNA_PROJECTION != CANONICAL_SOURCE",
        "Do **not** delete a live account to test disaster recovery.",
    ):
        if phrase not in docs:
            raise ValueError(f"cold restore documentation missing boundary: {phrase}")

    return {
        "protocol": "qsol-control-restore-pack-spec/1",
        "status": "valid",
        "recovery_classes": 5,
        "schema_draft": schema["$schema"],
    }


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2, sort_keys=True))
