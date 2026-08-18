#!/usr/bin/env python3
"""Deterministic portable CONCAP bundle builder and verifier.

Portable bundles reuse QSOL-RESTORE-DAT/1 as the exact object format. They
strip private source_ref metadata from exported object manifests while
preserving approved source payload bytes exactly.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from storage.restore_capsule import (
    PACK_SPEC_PROTOCOL,
    RestoreCapsuleError,
    pack_capsule,
    parse_capsule,
    verify_capsule,
)

EXPORT_SPEC_PROTOCOL = "qsol-control-concap-export-spec/1"
OBJECT_INDEX_PROTOCOL = "QSOL-CONCAP/OBJECT-INDEX/1"
BOOTSTRAP_PROTOCOL = "QSOL-CONCAP/BOOTSTRAP/1"
CONTAINER = "qsol-restore-dat/1"
MEDIA_TYPE = "application/vnd.qsol.restore-dat"
SCHEMA_VERSION = "1.0.0"

TOKEN = re.compile(r"^[a-z0-9_.-]+$")
CONCAP_ID = re.compile(r"^concap\.[a-z0-9_.-]+/[1-9][0-9]*$")
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")

PRIVACY_RANK = {"PUBLIC": 0, "INTERNAL": 1, "RESTRICTED": 2}

EXPORT_BOUNDARIES = (
    "PRIVATE_SOURCE != PORTABLE_BUNDLE",
    "PORTABLE_BUNDLE != PUBLICATION",
    "RESTRICTED_BUNDLE != ENCRYPTED_BUNDLE",
    "SOURCE_REF_STRIPPED != SOURCE_BYTES_ANONYMIZED",
    "MODEL_CAN_LOAD_OBJECT != MODEL_CAN_ACCESS_SOURCE_REPOSITORY",
    "QSOL-RESTORE-DAT/1 != ENCRYPTION",
)

INDEX_BOUNDARIES = (
    "PRIVATE_SOURCE != PORTABLE_BUNDLE",
    "BUNDLE_OBJECT != CANONICAL_SOURCE",
    "OBJECT_IDENTITY != TRANSPORT_LOCATION",
    "MODEL_CAN_LOAD_OBJECT != MODEL_CAN_ACCESS_SOURCE_REPOSITORY",
    "QSOL-RESTORE-DAT/1 != ENCRYPTION",
)

BOOTSTRAP_BOUNDARIES = (
    "BOOTSTRAP != PRIVATE_SOURCE",
    "OBJECT_INDEX != CAPSULE_PAYLOAD",
    "OBJECT_IDENTITY != TRANSPORT_LOCATION",
    "MODEL_CAN_LOAD_OBJECT != MODEL_CAN_ACCESS_SOURCE_REPOSITORY",
)


class ConcapBundleError(ValueError):
    """Raised when portable export or bundle bytes violate the contract."""


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


def digest(value: Any) -> str:
    return sha256_ref(canonical_json_bytes(value))


def reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ConcapBundleError(f"duplicate JSON object member: {key}")
        out[key] = value
    return out


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ConcapBundleError(f"refusing symlink JSON input: {path}")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_pairs,
        )
    except ConcapBundleError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConcapBundleError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConcapBundleError(f"{path} must contain a JSON object")
    return value


def require_keys(value: dict[str, Any], expected: set[str], where: str) -> None:
    found = set(value)
    if found != expected:
        raise ConcapBundleError(
            f"{where}: fields mismatch: expected {sorted(expected)!r}, found {sorted(found)!r}"
        )


def canonical_relative_path(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ConcapBundleError(f"{where} must be a canonical relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ConcapBundleError(f"{where} contains an absolute/dot/parent segment")
    if path.as_posix() != value:
        raise ConcapBundleError(f"{where} is not canonical POSIX form")
    return value


def resolve_under(root: Path, relative: str, where: str, *, require_file: bool = True) -> Path:
    canonical_relative_path(relative, where)
    root_resolved = root.resolve()
    candidate = root_resolved
    for part in PurePosixPath(relative).parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ConcapBundleError(f"{where} traverses a symlink: {relative}")
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ConcapBundleError(f"{where} escapes source root: {relative}") from exc
    if require_file and not candidate.is_file():
        raise ConcapBundleError(f"{where} is missing: {relative}")
    return candidate


def validate_export_spec(spec: dict[str, Any]) -> list[dict[str, str]]:
    require_keys(
        spec,
        {
            "protocol",
            "schema_version",
            "bundle_id",
            "export_class",
            "sensitive_export_acknowledged",
            "bindings",
            "boundaries",
        },
        "export spec",
    )
    if spec["protocol"] != EXPORT_SPEC_PROTOCOL:
        raise ConcapBundleError("export spec protocol mismatch")
    if spec["schema_version"] != SCHEMA_VERSION:
        raise ConcapBundleError("unsupported export spec schema version")
    if not isinstance(spec["bundle_id"], str) or TOKEN.fullmatch(spec["bundle_id"]) is None:
        raise ConcapBundleError("bundle_id must be a canonical token")
    export_class = spec["export_class"]
    if export_class not in PRIVACY_RANK:
        raise ConcapBundleError("export_class is invalid")
    acknowledged = spec["sensitive_export_acknowledged"]
    if type(acknowledged) is not bool:
        raise ConcapBundleError("sensitive_export_acknowledged must be boolean")
    if export_class == "RESTRICTED" and acknowledged is not True:
        raise ConcapBundleError("RESTRICTED portable export requires explicit acknowledgement")

    boundaries = spec["boundaries"]
    if not isinstance(boundaries, list) or any(not isinstance(x, str) or not x for x in boundaries):
        raise ConcapBundleError("export boundaries must be non-empty strings")
    if len(boundaries) != len(set(boundaries)):
        raise ConcapBundleError("export boundaries must be unique")
    for boundary in EXPORT_BOUNDARIES:
        if boundary not in boundaries:
            raise ConcapBundleError(f"export spec missing boundary: {boundary}")

    bindings = spec["bindings"]
    if not isinstance(bindings, list) or not bindings:
        raise ConcapBundleError("export bindings must be a non-empty array")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    previous: bytes | None = None
    for index, binding in enumerate(bindings):
        if not isinstance(binding, dict):
            raise ConcapBundleError(f"bindings[{index}] must be an object")
        require_keys(binding, {"role_id", "pack_spec"}, f"bindings[{index}]")
        role_id = binding["role_id"]
        if not isinstance(role_id, str) or CONCAP_ID.fullmatch(role_id) is None:
            raise ConcapBundleError(f"bindings[{index}].role_id is invalid")
        encoded = role_id.encode("utf-8")
        if previous is not None and previous >= encoded:
            raise ConcapBundleError("export bindings must be strictly UTF-8 sorted by role_id")
        previous = encoded
        if role_id in seen:
            raise ConcapBundleError(f"duplicate role binding: {role_id}")
        seen.add(role_id)
        pack_spec = canonical_relative_path(binding["pack_spec"], f"{role_id}.pack_spec")
        normalized.append({"role_id": role_id, "pack_spec": pack_spec})
    return normalized


def _validate_pack_spec(spec: dict[str, Any], label: str) -> list[dict[str, Any]]:
    require_keys(spec, {"protocol", "capsule", "recovery_class", "entries"}, label)
    if spec["protocol"] != PACK_SPEC_PROTOCOL:
        raise ConcapBundleError(f"{label}: restore pack-spec protocol mismatch")
    capsule = spec["capsule"]
    if (
        not isinstance(capsule, str)
        or not capsule.endswith(".dat")
        or "/" in capsule
        or "\\" in capsule
    ):
        raise ConcapBundleError(f"{label}: capsule must be a plain .dat filename")
    if not isinstance(spec["recovery_class"], str) or not spec["recovery_class"]:
        raise ConcapBundleError(f"{label}: recovery_class must be non-empty")
    entries = spec["entries"]
    if not isinstance(entries, list) or not entries:
        raise ConcapBundleError(f"{label}: entries must be non-empty")
    seen: set[str] = set()
    required = {
        "logical_path",
        "source_path",
        "kind",
        "privacy_class",
        "recovery_class",
        "source_ref",
    }
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ConcapBundleError(f"{label}: entries[{index}] must be object")
        require_keys(entry, required, f"{label}: entries[{index}]")
        logical_path = canonical_relative_path(
            entry["logical_path"], f"{label}: entries[{index}].logical_path"
        )
        canonical_relative_path(
            entry["source_path"], f"{label}: entries[{index}].source_path"
        )
        if logical_path in seen:
            raise ConcapBundleError(f"{label}: duplicate logical_path {logical_path}")
        seen.add(logical_path)
        if not isinstance(entry["kind"], str) or not entry["kind"]:
            raise ConcapBundleError(f"{label}: {logical_path}.kind is invalid")
        if entry["privacy_class"] not in PRIVACY_RANK:
            raise ConcapBundleError(f"{label}: {logical_path}.privacy_class is invalid")
        if entry["recovery_class"] != spec["recovery_class"]:
            raise ConcapBundleError(f"{label}: {logical_path}.recovery_class drift")
        if not isinstance(entry["source_ref"], str) or not entry["source_ref"]:
            raise ConcapBundleError(f"{label}: {logical_path}.source_ref is invalid")
    return entries


def object_path_for(object_id: str) -> str:
    if not isinstance(object_id, str) or SHA256.fullmatch(object_id) is None:
        raise ConcapBundleError("object_id must be sha256:<64-lower-hex>")
    digest_hex = object_id.split(":", 1)[1]
    return f"objects/sha256/{digest_hex[:2]}/{digest_hex}.dat"


def _portable_capsule_from_pack(
    *,
    source_root: Path,
    pack_spec_relative: str,
    export_class: str,
) -> bytes:
    pack_path = resolve_under(source_root, pack_spec_relative, "pack_spec")
    pack = load_json(pack_path)
    entries = _validate_pack_spec(pack, pack_spec_relative)
    prepared: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        privacy = entry["privacy_class"]
        if PRIVACY_RANK[privacy] > PRIVACY_RANK[export_class]:
            raise ConcapBundleError(
                f"{pack_spec_relative}: entry {index} privacy {privacy} exceeds export class {export_class}"
            )
        source = resolve_under(
            source_root,
            entry["source_path"],
            f"{pack_spec_relative}: source_path",
        )
        prepared.append(
            {
                "logical_path": entry["logical_path"],
                "data": source.read_bytes(),
                "kind": entry["kind"],
                "privacy_class": privacy,
                "recovery_class": entry["recovery_class"],
                # Deliberately omit private repository/path reference metadata.
                "source_ref": None,
            }
        )
    try:
        capsule = pack_capsule(prepared)
        verify_capsule(capsule)
        manifest, _ = parse_capsule(capsule)
    except RestoreCapsuleError as exc:
        raise ConcapBundleError(f"{pack_spec_relative}: portable capsule failure: {exc}") from exc
    for item in manifest["entries"]:
        if "source_ref" in item:
            raise ConcapBundleError("portable capsule leaked source_ref metadata")
    return capsule


def _index_body(
    *,
    spec: dict[str, Any],
    objects: list[dict[str, Any]],
    role_bindings: list[dict[str, str]],
) -> dict[str, Any]:
    projection = {"objects": objects, "role_bindings": role_bindings}
    return {
        "protocol": OBJECT_INDEX_PROTOCOL,
        "schema_version": SCHEMA_VERSION,
        "bundle_id": spec["bundle_id"],
        "bundle_class": spec["export_class"],
        "export_spec_sha256": digest(spec),
        "projection_sha256": digest(projection),
        "objects": objects,
        "role_bindings": role_bindings,
        "boundaries": list(INDEX_BOUNDARIES),
    }


def build_bundle(
    *,
    source_root: Path,
    export_spec_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if source_root.is_symlink():
        raise ConcapBundleError("source root must not be a symlink")
    source_root = source_root.resolve()
    if not source_root.is_dir():
        raise ConcapBundleError("source root must be a directory")
    if output_dir.is_symlink():
        raise ConcapBundleError("output directory must not be a symlink")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ConcapBundleError("output directory must be absent or empty")
    output_dir.mkdir(parents=True, exist_ok=True)

    export_spec_path = export_spec_path.resolve()
    try:
        export_spec_path.relative_to(source_root)
    except ValueError as exc:
        raise ConcapBundleError("export spec must be inside source root") from exc
    spec = load_json(export_spec_path)
    bindings = validate_export_spec(spec)

    capsule_cache: dict[str, tuple[str, bytes]] = {}
    role_bindings: list[dict[str, str]] = []
    object_bytes: dict[str, bytes] = {}

    for binding in bindings:
        pack_spec = binding["pack_spec"]
        cached = capsule_cache.get(pack_spec)
        if cached is None:
            capsule = _portable_capsule_from_pack(
                source_root=source_root,
                pack_spec_relative=pack_spec,
                export_class=spec["export_class"],
            )
            object_id = sha256_ref(capsule)
            cached = (object_id, capsule)
            capsule_cache[pack_spec] = cached
            object_bytes[object_id] = capsule
        object_id, _ = cached
        role_bindings.append({"role_id": binding["role_id"], "object_id": object_id})

    objects = []
    for object_id in sorted(object_bytes, key=lambda value: value.encode("utf-8")):
        capsule = object_bytes[object_id]
        relative = object_path_for(object_id)
        target = output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(capsule)
        objects.append(
            {
                "object_id": object_id,
                "size_bytes": len(capsule),
                "media_type": MEDIA_TYPE,
                "container": CONTAINER,
                "path": relative,
            }
        )

    role_bindings.sort(key=lambda item: item["role_id"].encode("utf-8"))
    index_body = _index_body(spec=spec, objects=objects, role_bindings=role_bindings)
    index = {**index_body, "index_id": digest(index_body)}
    index_bytes = canonical_json_bytes(index) + b"\n"
    (output_dir / "OBJECTS.json").write_bytes(index_bytes)

    bootstrap = {
        "protocol": BOOTSTRAP_PROTOCOL,
        "schema_version": SCHEMA_VERSION,
        "bundle_id": spec["bundle_id"],
        "bundle_class": spec["export_class"],
        "object_index_path": "OBJECTS.json",
        "object_index_id": index["index_id"],
        "object_index_sha256": sha256_ref(index_bytes),
        "object_count": len(objects),
        "role_count": len(role_bindings),
        "boundaries": list(BOOTSTRAP_BOUNDARIES),
    }
    (output_dir / "BOOTSTRAP.json").write_bytes(canonical_json_bytes(bootstrap) + b"\n")
    return verify_bundle(output_dir)


def _validate_index(index: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    require_keys(
        index,
        {
            "protocol",
            "schema_version",
            "index_id",
            "bundle_id",
            "bundle_class",
            "export_spec_sha256",
            "projection_sha256",
            "objects",
            "role_bindings",
            "boundaries",
        },
        "OBJECTS.json",
    )
    if index["protocol"] != OBJECT_INDEX_PROTOCOL or index["schema_version"] != SCHEMA_VERSION:
        raise ConcapBundleError("OBJECTS.json protocol/version mismatch")
    if not isinstance(index["bundle_id"], str) or TOKEN.fullmatch(index["bundle_id"]) is None:
        raise ConcapBundleError("OBJECTS.json bundle_id invalid")
    if index["bundle_class"] not in PRIVACY_RANK:
        raise ConcapBundleError("OBJECTS.json bundle_class invalid")
    for field in ("index_id", "export_spec_sha256", "projection_sha256"):
        if not isinstance(index[field], str) or SHA256.fullmatch(index[field]) is None:
            raise ConcapBundleError(f"OBJECTS.json {field} invalid")
    if index["boundaries"] != list(INDEX_BOUNDARIES):
        raise ConcapBundleError("OBJECTS.json boundaries drift")
    body = dict(index)
    claimed = body.pop("index_id")
    if claimed != digest(body):
        raise ConcapBundleError("OBJECTS.json index_id mismatch")

    objects = index["objects"]
    if not isinstance(objects, list) or not objects:
        raise ConcapBundleError("OBJECTS.json objects must be non-empty")
    seen_objects: set[str] = set()
    prior_object: bytes | None = None
    for item in objects:
        if not isinstance(item, dict):
            raise ConcapBundleError("OBJECTS.json object entry must be object")
        require_keys(item, {"object_id", "size_bytes", "media_type", "container", "path"}, "object entry")
        object_id = item["object_id"]
        if not isinstance(object_id, str) or SHA256.fullmatch(object_id) is None:
            raise ConcapBundleError("object_id invalid")
        encoded = object_id.encode("utf-8")
        if prior_object is not None and prior_object >= encoded:
            raise ConcapBundleError("objects must be strictly UTF-8 sorted")
        prior_object = encoded
        if object_id in seen_objects:
            raise ConcapBundleError(f"duplicate object {object_id}")
        seen_objects.add(object_id)
        if not isinstance(item["size_bytes"], int) or isinstance(item["size_bytes"], bool) or item["size_bytes"] < 0:
            raise ConcapBundleError(f"{object_id}: size_bytes invalid")
        if item["media_type"] != MEDIA_TYPE or item["container"] != CONTAINER:
            raise ConcapBundleError(f"{object_id}: media/container mismatch")
        if item["path"] != object_path_for(object_id):
            raise ConcapBundleError(f"{object_id}: path is not content-derived")

    role_bindings = index["role_bindings"]
    if not isinstance(role_bindings, list) or not role_bindings:
        raise ConcapBundleError("OBJECTS.json role_bindings must be non-empty")
    seen_roles: set[str] = set()
    prior_role: bytes | None = None
    for item in role_bindings:
        if not isinstance(item, dict):
            raise ConcapBundleError("role binding must be an object")
        require_keys(item, {"role_id", "object_id"}, "role binding")
        role_id = item["role_id"]
        object_id = item["object_id"]
        if not isinstance(role_id, str) or CONCAP_ID.fullmatch(role_id) is None:
            raise ConcapBundleError("role binding role_id invalid")
        encoded = role_id.encode("utf-8")
        if prior_role is not None and prior_role >= encoded:
            raise ConcapBundleError("role_bindings must be strictly UTF-8 sorted")
        prior_role = encoded
        if role_id in seen_roles:
            raise ConcapBundleError(f"duplicate role binding: {role_id}")
        seen_roles.add(role_id)
        if object_id not in seen_objects:
            raise ConcapBundleError(f"{role_id}: unknown object_id {object_id}")

    projection = {"objects": objects, "role_bindings": role_bindings}
    if index["projection_sha256"] != digest(projection):
        raise ConcapBundleError("OBJECTS.json projection_sha256 mismatch")
    return objects, role_bindings


def verify_bundle(bundle_dir: Path) -> dict[str, Any]:
    if bundle_dir.is_symlink():
        raise ConcapBundleError("bundle directory must not be a symlink")
    bundle_dir = bundle_dir.resolve()
    if not bundle_dir.is_dir():
        raise ConcapBundleError("bundle directory is missing")
    bootstrap_path = bundle_dir / "BOOTSTRAP.json"
    index_path = bundle_dir / "OBJECTS.json"
    bootstrap = load_json(bootstrap_path)
    index = load_json(index_path)

    require_keys(
        bootstrap,
        {
            "protocol",
            "schema_version",
            "bundle_id",
            "bundle_class",
            "object_index_path",
            "object_index_id",
            "object_index_sha256",
            "object_count",
            "role_count",
            "boundaries",
        },
        "BOOTSTRAP.json",
    )
    if bootstrap["protocol"] != BOOTSTRAP_PROTOCOL or bootstrap["schema_version"] != SCHEMA_VERSION:
        raise ConcapBundleError("BOOTSTRAP.json protocol/version mismatch")
    if bootstrap["object_index_path"] != "OBJECTS.json":
        raise ConcapBundleError("BOOTSTRAP.json object_index_path drift")
    if bootstrap["boundaries"] != list(BOOTSTRAP_BOUNDARIES):
        raise ConcapBundleError("BOOTSTRAP.json boundaries drift")
    if bootstrap["bundle_class"] not in PRIVACY_RANK:
        raise ConcapBundleError("BOOTSTRAP.json bundle_class invalid")
    if not isinstance(bootstrap["bundle_id"], str) or TOKEN.fullmatch(bootstrap["bundle_id"]) is None:
        raise ConcapBundleError("BOOTSTRAP.json bundle_id invalid")
    for field in ("object_index_id", "object_index_sha256"):
        if not isinstance(bootstrap[field], str) or SHA256.fullmatch(bootstrap[field]) is None:
            raise ConcapBundleError(f"BOOTSTRAP.json {field} invalid")
    if not isinstance(bootstrap["object_count"], int) or isinstance(bootstrap["object_count"], bool) or bootstrap["object_count"] < 1:
        raise ConcapBundleError("BOOTSTRAP.json object_count invalid")
    if not isinstance(bootstrap["role_count"], int) or isinstance(bootstrap["role_count"], bool) or bootstrap["role_count"] < 1:
        raise ConcapBundleError("BOOTSTRAP.json role_count invalid")

    index_bytes = index_path.read_bytes()
    if bootstrap["object_index_sha256"] != sha256_ref(index_bytes):
        raise ConcapBundleError("BOOTSTRAP.json object-index byte hash mismatch")
    objects, role_bindings = _validate_index(index)
    if bootstrap["object_index_id"] != index["index_id"]:
        raise ConcapBundleError("BOOTSTRAP.json object-index identity mismatch")
    if bootstrap["bundle_id"] != index["bundle_id"] or bootstrap["bundle_class"] != index["bundle_class"]:
        raise ConcapBundleError("BOOTSTRAP.json bundle metadata mismatch")
    if bootstrap["object_count"] != len(objects) or bootstrap["role_count"] != len(role_bindings):
        raise ConcapBundleError("BOOTSTRAP.json counts mismatch")

    declared_files = {"BOOTSTRAP.json", "OBJECTS.json"}
    privacy_max = 0
    for item in objects:
        relative = item["path"]
        declared_files.add(relative)
        target = resolve_under(bundle_dir, relative, "portable object")
        raw = target.read_bytes()
        if len(raw) != item["size_bytes"]:
            raise ConcapBundleError(f"{relative}: size mismatch")
        if sha256_ref(raw) != item["object_id"]:
            raise ConcapBundleError(f"{relative}: object hash mismatch")
        try:
            verify_capsule(raw)
            manifest, _ = parse_capsule(raw)
        except RestoreCapsuleError as exc:
            raise ConcapBundleError(f"{relative}: restore object invalid: {exc}") from exc
        for entry in manifest["entries"]:
            if "source_ref" in entry:
                raise ConcapBundleError(f"{relative}: portable object contains source_ref")
            privacy_max = max(privacy_max, PRIVACY_RANK[entry["privacy_class"]])

    if privacy_max > PRIVACY_RANK[index["bundle_class"]]:
        raise ConcapBundleError("bundle_class is weaker than contained object privacy")

    present_files = set()
    for path in bundle_dir.rglob("*"):
        if path.is_symlink():
            raise ConcapBundleError(f"bundle contains symlink: {path.relative_to(bundle_dir)}")
        if path.is_file():
            present_files.add(path.relative_to(bundle_dir).as_posix())
    if present_files != declared_files:
        extra = sorted(present_files - declared_files)
        missing = sorted(declared_files - present_files)
        raise ConcapBundleError(f"bundle file set mismatch: extra={extra}, missing={missing}")

    return {
        "protocol": "QSOL-CONCAP/BUNDLE-VERIFICATION/1",
        "status": "verified",
        "bundle_id": index["bundle_id"],
        "bundle_class": index["bundle_class"],
        "object_index_id": index["index_id"],
        "object_count": len(objects),
        "role_count": len(role_bindings),
    }


def write_deterministic_zip(bundle_dir: Path, output: Path) -> str:
    if output.is_symlink():
        raise ConcapBundleError("ZIP output must not be a symlink")
    if output.exists():
        raise ConcapBundleError("ZIP output already exists")
    verify_bundle(bundle_dir)
    bundle_dir = bundle_dir.resolve()
    files = sorted(
        (path for path in bundle_dir.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(bundle_dir).as_posix().encode("utf-8"),
    )
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        archive.comment = b""
        for path in files:
            relative = path.relative_to(bundle_dir).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.extra = b""
            info.comment = b""
            archive.writestr(info, path.read_bytes())
    return sha256_ref(output.read_bytes())
