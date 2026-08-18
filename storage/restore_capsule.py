#!/usr/bin/env python3
"""Deterministic cold-restore capsule container for QSOL-CONTROL.

`QSOL-RESTORE-DAT/1` is an application-defined `.dat` container. It preserves
canonical section bytes plus a compact manifest. DNA/lattice output is a
reversible derived projection of the capsule bytes, never the canonical source.

The QEC invariant identifiers recorded here are deterministic recovery lineage
only. They do not grant physical, biological, epistemic, or model-identity
meaning to the storage representation.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections import Counter
from pathlib import PurePosixPath
from typing import Any, Iterable

from storage.dna_lattice import (
    PHI_GATED_TRAVERSAL,
    decode_projection,
    encode_projection,
)

MAGIC = b"QSOL-RESTORE-DAT/1\x00"
PROTOCOL = "qsol-control-restore-capsule/1"
CONTAINER = "qsol-restore-dat/1"
PACK_SPEC_PROTOCOL = "qsol-control-restore-pack-spec/1"
LATTICE_PROFILE = "qsol-3x3x3-sierpinski-derived-memory/1"
DNA_CODEC = "qsol.dna-2bit-codon64/1"
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_ENTRY_COUNT = 4096
MAX_LOGICAL_PATH = 512
MAX_SOURCE_REF = 2048

RECOVERY_CLASSES = (
    "NEAR_SHELL",
    "MID_SHELL",
    "OUTER_SHELL",
    "RESONANCE_NODE",
    "WIGGLE_ZONE",
)
RECOVERY_RANK = {name: index for index, name in enumerate(RECOVERY_CLASSES)}

# Integer-thousandths representation of QSOL-PHI-INV-004. Keeping these as
# integers avoids floating-point ambiguity in the storage contract.
PHI_SHELL_MILLI = {
    "NEAR_SHELL": 1000,
    "MID_SHELL": 1618,
    "OUTER_SHELL": 2618,
    "RESONANCE_NODE": 4236,
    "WIGGLE_ZONE": 6854,
}

PRIVACY_CLASSES = {"PUBLIC", "INTERNAL", "RESTRICTED"}
BOUNDARIES = (
    "RESTORE_CAPSULE != MODEL_MEMORY",
    "RESTORED_CONTEXT != ORIGINAL_ASSISTANT_INSTANCE",
    "DNA_PROJECTION != CANONICAL_SOURCE",
    "QEC_LINEAGE != PHYSICAL_STORAGE_CLAIM",
    "RESTORE_SUCCESS != FACTUAL_TRUTH",
)


class RestoreCapsuleError(ValueError):
    """Raised when restore capsule bytes or metadata violate the contract."""


def canonical_json_bytes(value: Any) -> bytes:
    """Return the repository canonical JSON representation."""
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
    return f"sha256:{sha256_hex(data)}"


def _validate_logical_path(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_LOGICAL_PATH:
        raise RestoreCapsuleError("logical_path must contain 1..512 characters")
    if "\\" in value or "\x00" in value or "\n" in value or "\r" in value:
        raise RestoreCapsuleError("logical_path contains a forbidden character")
    path = PurePosixPath(value)
    if path.is_absolute() or value.startswith("/"):
        raise RestoreCapsuleError("logical_path must be relative")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise RestoreCapsuleError("logical_path must not contain empty, dot, or parent segments")
    canonical = path.as_posix()
    if canonical != value:
        raise RestoreCapsuleError("logical_path must already be canonical POSIX form")
    return value


def _validate_text(value: Any, field: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise RestoreCapsuleError(f"{field} must contain 1..{maximum} characters")
    if "\x00" in value:
        raise RestoreCapsuleError(f"{field} contains NUL")
    return value


def _validate_entry_input(entry: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise RestoreCapsuleError("each capsule entry must be an object")
    allowed = {
        "logical_path",
        "data",
        "kind",
        "privacy_class",
        "recovery_class",
        "source_ref",
    }
    extra = sorted(set(entry) - allowed)
    if extra:
        raise RestoreCapsuleError(f"capsule entry contains unsupported fields: {extra}")

    logical_path = _validate_logical_path(entry.get("logical_path"))
    data = entry.get("data")
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise RestoreCapsuleError(f"entry {logical_path} data must be bytes-like")
    raw = bytes(data)
    kind = _validate_text(entry.get("kind"), "kind", maximum=128)
    privacy = entry.get("privacy_class")
    if privacy not in PRIVACY_CLASSES:
        raise RestoreCapsuleError(f"entry {logical_path} privacy_class is invalid")
    recovery_class = entry.get("recovery_class")
    if recovery_class not in RECOVERY_RANK:
        raise RestoreCapsuleError(f"entry {logical_path} recovery_class is invalid")
    source_ref = entry.get("source_ref")
    if source_ref is not None:
        source_ref = _validate_text(source_ref, "source_ref", maximum=MAX_SOURCE_REF)

    return {
        "logical_path": logical_path,
        "data": raw,
        "kind": kind,
        "privacy_class": privacy,
        "recovery_class": recovery_class,
        "source_ref": source_ref,
    }


def _restore_order(entries: Iterable[dict[str, Any]]) -> list[str]:
    return [
        entry["logical_path"]
        for entry in sorted(
            entries,
            key=lambda item: (
                RECOVERY_RANK[item["recovery_class"]],
                item["logical_path"].encode("utf-8"),
            ),
        )
    ]


def pack_capsule(entries: Iterable[dict[str, Any]]) -> bytes:
    """Build byte-identical capsule bytes for byte-identical declared entries."""
    normalized = [_validate_entry_input(entry) for entry in entries]
    if not normalized:
        raise RestoreCapsuleError("restore capsule requires at least one entry")
    if len(normalized) > MAX_ENTRY_COUNT:
        raise RestoreCapsuleError(f"restore capsule exceeds {MAX_ENTRY_COUNT} entries")

    normalized.sort(key=lambda item: item["logical_path"].encode("utf-8"))
    paths = [entry["logical_path"] for entry in normalized]
    if len(paths) != len(set(paths)):
        raise RestoreCapsuleError("restore capsule logical paths must be unique")

    manifest_entries: list[dict[str, Any]] = []
    payload_parts: list[bytes] = []
    for entry in normalized:
        raw = entry["data"]
        payload_parts.append(raw)
        manifest_entry = {
            "logical_path": entry["logical_path"],
            "kind": entry["kind"],
            "privacy_class": entry["privacy_class"],
            "recovery_class": entry["recovery_class"],
            "phi_shell_milli": PHI_SHELL_MILLI[entry["recovery_class"]],
            "size_bytes": len(raw),
            "sha256": sha256_hex(raw),
        }
        if entry["source_ref"] is not None:
            manifest_entry["source_ref"] = entry["source_ref"]
        manifest_entries.append(manifest_entry)

    payload = b"".join(payload_parts)
    manifest_base = {
        "protocol": PROTOCOL,
        "container": CONTAINER,
        "version": 1,
        "authority": "none",
        "derived_from_source_records": True,
        "entry_order": "utf8-byte-lexicographic-logical-path",
        "restore_order": _restore_order(normalized),
        "entries": manifest_entries,
        "payload_size_bytes": len(payload),
        "payload_sha256": sha256_hex(payload),
        "lattice_profile": LATTICE_PROFILE,
        "dna_codec": DNA_CODEC,
        "qec_recovery_lineage": {
            "ouroboros_feedback_loop": "QSOL-OURO-INV-006",
            "phi_scale_node": "QSOL-PHI-INV-004",
            "e8_triality_lock": "QSOL-E8-INV-005",
            "semantics": "deterministic recovery scheduling lineage only",
        },
        "boundaries": list(BOUNDARIES),
    }
    manifest_id = sha256_ref(canonical_json_bytes(manifest_base))
    manifest = {"manifest_id": manifest_id, **manifest_base}
    manifest_bytes = canonical_json_bytes(manifest)
    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        raise RestoreCapsuleError("restore manifest exceeds size limit")

    return MAGIC + struct.pack(">Q", len(manifest_bytes)) + manifest_bytes + payload


def _validate_manifest_entry(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RestoreCapsuleError("manifest entry must be an object")
    allowed = {
        "logical_path",
        "kind",
        "privacy_class",
        "recovery_class",
        "phi_shell_milli",
        "size_bytes",
        "sha256",
        "source_ref",
    }
    extra = sorted(set(value) - allowed)
    if extra:
        raise RestoreCapsuleError(f"manifest entry contains unsupported fields: {extra}")

    path = _validate_logical_path(value.get("logical_path"))
    kind = _validate_text(value.get("kind"), "kind", maximum=128)
    privacy = value.get("privacy_class")
    if privacy not in PRIVACY_CLASSES:
        raise RestoreCapsuleError(f"manifest entry {path} privacy_class is invalid")
    recovery_class = value.get("recovery_class")
    if recovery_class not in RECOVERY_RANK:
        raise RestoreCapsuleError(f"manifest entry {path} recovery_class is invalid")
    if value.get("phi_shell_milli") != PHI_SHELL_MILLI[recovery_class]:
        raise RestoreCapsuleError(f"manifest entry {path} phi shell drift")
    size = value.get("size_bytes")
    if not isinstance(size, int) or size < 0:
        raise RestoreCapsuleError(f"manifest entry {path} size_bytes is invalid")
    digest = value.get("sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise RestoreCapsuleError(f"manifest entry {path} sha256 is invalid")
    source_ref = value.get("source_ref")
    if source_ref is not None:
        _validate_text(source_ref, "source_ref", maximum=MAX_SOURCE_REF)
    return value


def parse_capsule(capsule: bytes) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Parse and verify a capsule without trusting embedded metadata."""
    raw = bytes(capsule)
    header_len = len(MAGIC) + 8
    if len(raw) < header_len or not raw.startswith(MAGIC):
        raise RestoreCapsuleError("restore capsule magic mismatch")
    manifest_len = struct.unpack(">Q", raw[len(MAGIC):header_len])[0]
    if manifest_len < 2 or manifest_len > MAX_MANIFEST_BYTES:
        raise RestoreCapsuleError("restore manifest length is invalid")
    manifest_end = header_len + manifest_len
    if manifest_end > len(raw):
        raise RestoreCapsuleError("restore capsule ended inside manifest")

    try:
        manifest = json.loads(raw[header_len:manifest_end].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RestoreCapsuleError("restore manifest is not valid UTF-8 JSON") from exc
    if not isinstance(manifest, dict):
        raise RestoreCapsuleError("restore manifest must be an object")

    allowed_manifest = {
        "manifest_id",
        "protocol",
        "container",
        "version",
        "authority",
        "derived_from_source_records",
        "entry_order",
        "restore_order",
        "entries",
        "payload_size_bytes",
        "payload_sha256",
        "lattice_profile",
        "dna_codec",
        "qec_recovery_lineage",
        "boundaries",
    }
    extra_manifest = sorted(set(manifest) - allowed_manifest)
    if extra_manifest:
        raise RestoreCapsuleError(f"restore manifest contains unsupported fields: {extra_manifest}")
    if manifest.get("protocol") != PROTOCOL or manifest.get("container") != CONTAINER:
        raise RestoreCapsuleError("restore protocol/container mismatch")
    if manifest.get("version") != 1:
        raise RestoreCapsuleError("unsupported restore capsule version")
    if manifest.get("authority") != "none":
        raise RestoreCapsuleError("restore capsule must not claim authority")
    if manifest.get("derived_from_source_records") is not True:
        raise RestoreCapsuleError("restore capsule must remain a derived transport")
    if manifest.get("entry_order") != "utf8-byte-lexicographic-logical-path":
        raise RestoreCapsuleError("restore capsule entry-order contract mismatch")
    if manifest.get("lattice_profile") != LATTICE_PROFILE or manifest.get("dna_codec") != DNA_CODEC:
        raise RestoreCapsuleError("restore lattice/DNA contract mismatch")
    if manifest.get("boundaries") != list(BOUNDARIES):
        raise RestoreCapsuleError("restore epistemic boundary contract mismatch")
    qec = manifest.get("qec_recovery_lineage")
    expected_qec = {
        "ouroboros_feedback_loop": "QSOL-OURO-INV-006",
        "phi_scale_node": "QSOL-PHI-INV-004",
        "e8_triality_lock": "QSOL-E8-INV-005",
        "semantics": "deterministic recovery scheduling lineage only",
    }
    if qec != expected_qec:
        raise RestoreCapsuleError("QEC recovery-lineage contract mismatch")

    manifest_id = manifest.get("manifest_id")
    base = {key: value for key, value in manifest.items() if key != "manifest_id"}
    if manifest_id != sha256_ref(canonical_json_bytes(base)):
        raise RestoreCapsuleError("restore manifest identity mismatch")

    entries_value = manifest.get("entries")
    if not isinstance(entries_value, list) or not entries_value:
        raise RestoreCapsuleError("restore manifest entries must be a non-empty list")
    if len(entries_value) > MAX_ENTRY_COUNT:
        raise RestoreCapsuleError("restore manifest entry count exceeds limit")
    manifest_entries = [_validate_manifest_entry(entry) for entry in entries_value]
    paths = [entry["logical_path"] for entry in manifest_entries]
    if paths != sorted(paths, key=lambda item: item.encode("utf-8")):
        raise RestoreCapsuleError("restore manifest entries are not canonically ordered")
    if len(paths) != len(set(paths)):
        raise RestoreCapsuleError("restore manifest contains duplicate logical paths")

    payload = raw[manifest_end:]
    if manifest.get("payload_size_bytes") != len(payload):
        raise RestoreCapsuleError("restore payload size mismatch")
    if manifest.get("payload_sha256") != sha256_hex(payload):
        raise RestoreCapsuleError("restore payload hash mismatch")

    extracted: list[dict[str, Any]] = []
    offset = 0
    for entry in manifest_entries:
        size = entry["size_bytes"]
        end = offset + size
        section = payload[offset:end]
        if len(section) != size:
            raise RestoreCapsuleError(f"restore payload ended inside {entry['logical_path']}")
        if sha256_hex(section) != entry["sha256"]:
            raise RestoreCapsuleError(f"restore entry hash mismatch: {entry['logical_path']}")
        extracted.append({**entry, "data": section})
        offset = end
    if offset != len(payload):
        raise RestoreCapsuleError("restore payload contains unclaimed trailing bytes")

    expected_restore_order = _restore_order(manifest_entries)
    if manifest.get("restore_order") != expected_restore_order:
        raise RestoreCapsuleError("restore schedule does not match declared recovery classes")
    return manifest, extracted


def verify_capsule(capsule: bytes) -> dict[str, Any]:
    """Verify integrity plus canonical fixed-point reconstruction."""
    raw = bytes(capsule)
    manifest, extracted = parse_capsule(raw)
    repack_entries = [
        {
            "logical_path": entry["logical_path"],
            "data": entry["data"],
            "kind": entry["kind"],
            "privacy_class": entry["privacy_class"],
            "recovery_class": entry["recovery_class"],
            "source_ref": entry.get("source_ref"),
        }
        for entry in extracted
    ]
    rebuilt = pack_capsule(repack_entries)
    if rebuilt != raw:
        raise RestoreCapsuleError("restore capsule is not a canonical fixed point")

    privacy_counts = Counter(entry["privacy_class"] for entry in extracted)
    recovery_counts = Counter(entry["recovery_class"] for entry in extracted)
    return {
        "protocol": PROTOCOL,
        "status": "verified",
        "capsule_sha256": sha256_hex(raw),
        "manifest_id": manifest["manifest_id"],
        "entry_count": len(extracted),
        "payload_size_bytes": manifest["payload_size_bytes"],
        "privacy_counts": {key: privacy_counts[key] for key in sorted(privacy_counts)},
        "recovery_class_counts": {
            key: recovery_counts[key] for key in RECOVERY_CLASSES if recovery_counts[key]
        },
        "restore_order": manifest["restore_order"],
        "fixed_point": True,
        "authority": "none",
    }


def recovery_schedule(capsule: bytes) -> tuple[str, ...]:
    """Return the deterministic QEC-lineage restore schedule."""
    manifest, _ = parse_capsule(capsule)
    return tuple(manifest["restore_order"])


def capsule_contains_restricted(capsule: bytes) -> bool:
    """Return whether any section is marked RESTRICTED."""
    _, entries = parse_capsule(capsule)
    return any(entry["privacy_class"] == "RESTRICTED" for entry in entries)


def encode_capsule_dna(capsule: bytes) -> dict[str, Any]:
    """Encode verified capsule bytes using CONTROL's existing DNA codec."""
    verify_capsule(capsule)
    projection = encode_projection(bytes(capsule), traversal_id=PHI_GATED_TRAVERSAL)
    projection["restore_capsule_protocol"] = PROTOCOL
    projection["restore_capsule_sha256"] = sha256_hex(bytes(capsule))
    return projection


def decode_capsule_dna(projection: dict[str, Any]) -> bytes:
    """Decode a DNA projection and require a valid canonical restore capsule."""
    expected_protocol = projection.get("restore_capsule_protocol")
    expected_sha = projection.get("restore_capsule_sha256")
    projection_copy = dict(projection)
    projection_copy.pop("restore_capsule_protocol", None)
    projection_copy.pop("restore_capsule_sha256", None)
    capsule = decode_projection(projection_copy)
    if expected_protocol != PROTOCOL:
        raise RestoreCapsuleError("DNA projection restore-capsule protocol mismatch")
    if expected_sha != sha256_hex(capsule):
        raise RestoreCapsuleError("DNA projection restore-capsule hash mismatch")
    verify_capsule(capsule)
    return capsule
