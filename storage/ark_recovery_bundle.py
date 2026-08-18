#!/usr/bin/env python3
"""Minimum offline QSOL-CONTROL storage bundle for ARK recovery.

The bundle is a deterministic QSOL-RESTORE-DAT/1 capsule containing exactly the
canonical storage records needed to reconstruct and verify one interaction run
without access to the original CONTROL store, WebUI, search indexes, ORACLE, or
NEXUS.

Recovery is a transport/reconstruction operation only. It does not promote any
stored claim, lattice position, receipt, or hash into semantic authority.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable

from storage.control_store import (
    PRIVACY_RANK,
    ControlStore,
    StorageError,
    canonical_json_bytes,
    sha256_hex,
)
from storage.interaction_store import InteractionStore, LATTICE_PROFILE
from storage.restore_capsule import (
    RestoreCapsuleError,
    pack_capsule,
    parse_capsule,
    verify_capsule,
)

PROTOCOL = "qsol-control-ark-minimum-bundle/1"
BOOTSTRAP_PATH = "CONTROL-RECOVERY.json"
LATTICE_PATH = "lattice/profile.json"
AUTHORITY = "none"
MIN_PRIVACY_CLASS = "INTERNAL"
BOUNDARIES = (
    "RECOVERY_BUNDLE != SEMANTIC_AUTHORITY",
    "RECOVERY_HEAD != SOURCE_CURRENT_HEAD",
    "LATTICE_ADDRESS != TRUTH",
    "HASH_INTEGRITY != EVIDENCE_AUTHORITY",
    "RESTORED_CONTEXT != ORIGINAL_ASSISTANT_INSTANCE",
)
MAX_RECOVERY_FILES = 100_000

LATTICE_DESCRIPTOR = {
    "protocol": LATTICE_PROFILE,
    "authority": "storage-only",
    "top_level_cell_count": 27,
    "axes": {
        "x_information_role": ["question", "response", "evidence"],
        "y_epistemic_role": ["observed", "derived", "unresolved"],
        "z_temporal_role": ["current", "historical", "recovery"],
    },
    "address_shape": "L[x,y,z]",
    "geometry_confers_truth": False,
    "address_replaces_content_identity": False,
}


class ArkBundleError(ValueError):
    """Raised when the minimum ARK recovery contract is violated."""


def _digest(ref: str, field: str) -> str:
    if not isinstance(ref, str) or not ref.startswith("sha256:") or len(ref) != 71:
        raise ArkBundleError(f"{field} must be a sha256: reference")
    digest = ref[7:]
    if any(ch not in "0123456789abcdef" for ch in digest):
        raise ArkBundleError(f"{field} must be a lowercase SHA-256 reference")
    return digest


def _json(data: bytes, field: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArkBundleError(f"{field} must be canonical UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ArkBundleError(f"{field} must be a JSON object")
    return value


def _privacy_max(classes: Iterable[str]) -> str:
    values = list(classes)
    if not values:
        return MIN_PRIVACY_CLASS
    for value in values:
        if value not in PRIVACY_RANK:
            raise ArkBundleError(f"unknown privacy class: {value!r}")
    strongest = max(values, key=lambda value: PRIVACY_RANK[value])
    if PRIVACY_RANK[strongest] < PRIVACY_RANK[MIN_PRIVACY_CLASS]:
        return MIN_PRIVACY_CLASS
    return strongest


def _collection_snapshot_chain(
    storage: ControlStore, collection_id: str, snapshot_id: str
) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    seen: set[str] = set()
    cursor = snapshot_id
    expected_revision: int | None = None
    while True:
        if cursor in seen:
            raise ArkBundleError("collection snapshot lineage loop detected")
        seen.add(cursor)
        snapshot = storage.get_collection_snapshot(collection_id, cursor)
        revision = snapshot["revision"]
        if expected_revision is None:
            expected_revision = revision
        elif revision != expected_revision:
            raise ArkBundleError("collection snapshot revision chain is discontinuous")
        chain.append(snapshot)
        previous = snapshot["previous_snapshot_id"]
        if previous is None:
            if revision != 0:
                raise ArkBundleError("collection snapshot lineage terminated before revision 0")
            break
        expected_revision -= 1
        cursor = previous
    chain.reverse()
    return chain


def _file_record_bytes(storage: ControlStore, file_id: str) -> tuple[dict[str, Any], bytes, bytes]:
    record = storage.get_file_record(file_id)
    payload = storage.read_file(file_id)
    return record, canonical_json_bytes(record), payload


def build_ark_bundle(store: InteractionStore, run_id: str) -> bytes:
    """Build deterministic minimum recovery bytes for one verified run."""
    verification = store.verify_run(run_id)
    run = store.get_run(run_id)
    events = store.list_events(run_id)

    file_ids: set[str] = set(run["file_ids"])
    for event in events:
        file_ids.update(event["file_ids"])

    collection_descriptor: dict[str, Any] | None = None
    collection_chain: list[dict[str, Any]] = []
    collection_ref = run["collection_ref"]
    if collection_ref is not None:
        collection_id = collection_ref["collection_id"]
        snapshot_id = collection_ref["snapshot_id"]
        collection = store.storage.get_collection(collection_id)
        collection_descriptor = {
            key: value for key, value in collection.items() if key != "head_snapshot_id"
        }
        collection_chain = _collection_snapshot_chain(
            store.storage, collection_id, snapshot_id
        )
        exact_snapshot = collection_chain[-1]
        file_ids.update(exact_snapshot["members"])

    if len(file_ids) > MAX_RECOVERY_FILES:
        raise ArkBundleError("minimum recovery bundle exceeds file-count limit")

    file_rows: list[tuple[dict[str, Any], bytes, bytes]] = []
    privacy_classes: list[str] = []
    for file_id in sorted(file_ids, key=lambda value: value.encode("ascii")):
        row = _file_record_bytes(store.storage, file_id)
        file_rows.append(row)
        privacy_classes.append(row[0]["privacy_class"])
    if collection_descriptor is not None:
        privacy_classes.append(collection_descriptor["privacy_class"])
    privacy_class = _privacy_max(privacy_classes)

    entries: list[dict[str, Any]] = []

    run_digest = _digest(run_id, "run_id")
    run_path = f"runs/{run_digest}.json"
    entries.append(
        {
            "logical_path": run_path,
            "data": canonical_json_bytes(run),
            "kind": "control-interaction-run",
            "privacy_class": privacy_class,
            "recovery_class": "NEAR_SHELL",
        }
    )

    event_paths: list[str] = []
    for event in events:
        digest = _digest(event["event_id"], "event_id")
        path = f"events/{event['sequence']:08d}-{digest}.json"
        event_paths.append(path)
        entries.append(
            {
                "logical_path": path,
                "data": canonical_json_bytes(event),
                "kind": "control-run-event",
                "privacy_class": privacy_class,
                "recovery_class": "MID_SHELL",
            }
        )

    file_paths: list[str] = []
    object_paths: list[str] = []
    for record, record_bytes, payload in file_rows:
        file_digest = _digest(record["file_id"], "file_id")
        object_digest = _digest(record["object_id"], "object_id")
        file_path = f"files/{file_digest}.json"
        object_path = f"objects/sha256/{object_digest[:2]}/{object_digest}"
        file_paths.append(file_path)
        object_paths.append(object_path)
        entries.append(
            {
                "logical_path": file_path,
                "data": record_bytes,
                "kind": "control-file-record",
                "privacy_class": record["privacy_class"],
                "recovery_class": "MID_SHELL",
            }
        )
        entries.append(
            {
                "logical_path": object_path,
                "data": payload,
                "kind": "control-raw-object",
                "privacy_class": record["privacy_class"],
                "recovery_class": "OUTER_SHELL",
            }
        )

    collection_paths: list[str] = []
    if collection_descriptor is not None:
        collection_digest = _digest(
            collection_descriptor["collection_id"], "collection_id"
        )
        descriptor_path = f"collections/{collection_digest}/collection.json"
        collection_paths.append(descriptor_path)
        entries.append(
            {
                "logical_path": descriptor_path,
                "data": canonical_json_bytes(collection_descriptor),
                "kind": "control-collection-record",
                "privacy_class": collection_descriptor["privacy_class"],
                "recovery_class": "NEAR_SHELL",
            }
        )
        for snapshot in collection_chain:
            snapshot_digest = _digest(snapshot["snapshot_id"], "snapshot_id")
            path = (
                f"collections/{collection_digest}/snapshots/"
                f"{snapshot_digest}.json"
            )
            collection_paths.append(path)
            entries.append(
                {
                    "logical_path": path,
                    "data": canonical_json_bytes(snapshot),
                    "kind": "control-collection-snapshot",
                    "privacy_class": collection_descriptor["privacy_class"],
                    "recovery_class": "MID_SHELL",
                }
            )

    entries.append(
        {
            "logical_path": LATTICE_PATH,
            "data": canonical_json_bytes(LATTICE_DESCRIPTOR),
            "kind": "control-lattice-profile",
            "privacy_class": "INTERNAL",
            "recovery_class": "NEAR_SHELL",
        }
    )

    required_paths = sorted(
        [entry["logical_path"] for entry in entries],
        key=lambda value: value.encode("utf-8"),
    )
    bootstrap = {
        "protocol": PROTOCOL,
        "run_id": run_id,
        "run_fingerprint": verification["fingerprint"],
        "privacy_class": privacy_class,
        "collection_ref": collection_ref,
        "lattice_profile": LATTICE_PROFILE,
        "required_entry_paths": required_paths,
        "event_paths": sorted(event_paths, key=lambda value: value.encode("utf-8")),
        "file_paths": sorted(file_paths, key=lambda value: value.encode("utf-8")),
        "object_paths": sorted(object_paths, key=lambda value: value.encode("utf-8")),
        "collection_paths": sorted(
            collection_paths, key=lambda value: value.encode("utf-8")
        ),
        "recovery_head_semantics": "exact-run-snapshot-projection-not-source-current-head",
        "authority": AUTHORITY,
        "boundaries": list(BOUNDARIES),
    }
    entries.append(
        {
            "logical_path": BOOTSTRAP_PATH,
            "data": canonical_json_bytes(bootstrap),
            "kind": "control-ark-recovery-bootstrap",
            "privacy_class": privacy_class,
            "recovery_class": "NEAR_SHELL",
        }
    )
    try:
        return pack_capsule(entries)
    except (RestoreCapsuleError, StorageError) as exc:
        raise ArkBundleError(str(exc)) from exc


def _entry_map(capsule: bytes) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    try:
        _, entries = parse_capsule(capsule)
    except RestoreCapsuleError as exc:
        raise ArkBundleError(str(exc)) from exc
    by_path = {entry["logical_path"]: entry for entry in entries}
    if len(by_path) != len(entries):
        raise ArkBundleError("duplicate logical path in recovery bundle")
    bootstrap_entry = by_path.get(BOOTSTRAP_PATH)
    if bootstrap_entry is None:
        raise ArkBundleError("recovery bundle is missing CONTROL-RECOVERY.json")
    bootstrap = _json(bootstrap_entry["data"], BOOTSTRAP_PATH)
    if bootstrap.get("protocol") != PROTOCOL:
        raise ArkBundleError("unknown minimum ARK recovery bundle protocol")
    if bootstrap.get("authority") != AUTHORITY:
        raise ArkBundleError("recovery bundle must not claim authority")
    if bootstrap.get("boundaries") != list(BOUNDARIES):
        raise ArkBundleError("recovery boundary contract mismatch")
    if bootstrap.get("lattice_profile") != LATTICE_PROFILE:
        raise ArkBundleError("recovery lattice profile mismatch")
    required = bootstrap.get("required_entry_paths")
    if not isinstance(required, list) or len(required) != len(set(required)):
        raise ArkBundleError("required_entry_paths must be a unique array")
    actual = sorted(
        (path for path in by_path if path != BOOTSTRAP_PATH),
        key=lambda value: value.encode("utf-8"),
    )
    if required != actual:
        raise ArkBundleError("recovery bundle entry set does not match bootstrap")
    lattice = by_path.get(LATTICE_PATH)
    if lattice is None or _json(lattice["data"], LATTICE_PATH) != LATTICE_DESCRIPTOR:
        raise ArkBundleError("recovery lattice descriptor mismatch")
    return bootstrap, by_path


def _safe_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise ArkBundleError(f"recovery target path already exists: {path}")
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _reconstruct(
    capsule: bytes, target_root: Path, *, require_absent: bool = True
) -> dict[str, Any]:
    bootstrap, by_path = _entry_map(capsule)
    if require_absent and target_root.exists():
        raise ArkBundleError("recovery target must not already exist")
    target_root.mkdir(parents=True, exist_ok=not require_absent)

    for logical in bootstrap["object_paths"]:
        entry = by_path[logical]
        parts = Path(logical).parts
        if len(parts) != 4 or parts[:2] != ("objects", "sha256"):
            raise ArkBundleError("invalid raw-object logical path")
        prefix, digest = parts[2], parts[3]
        if len(prefix) != 2 or digest[:2] != prefix:
            raise ArkBundleError("raw-object path prefix mismatch")
        if sha256_hex(entry["data"]) != digest:
            raise ArkBundleError("raw-object path/content identity mismatch")
        _safe_write(target_root / logical, entry["data"])

    for logical in bootstrap["file_paths"]:
        entry = by_path[logical]
        record = _json(entry["data"], logical)
        file_id = record.get("file_id")
        file_digest = _digest(file_id, "file_id")
        if Path(logical).name != f"{file_digest}.json":
            raise ArkBundleError("file record logical path does not match file_id")
        _safe_write(target_root / "records" / "files" / f"{file_digest}.json", entry["data"])

    collection_ref = bootstrap["collection_ref"]
    if collection_ref is not None:
        collection_id = collection_ref["collection_id"]
        collection_digest = _digest(collection_id, "collection_id")
        descriptor_logical = f"collections/{collection_digest}/collection.json"
        descriptor_entry = by_path.get(descriptor_logical)
        if descriptor_entry is None:
            raise ArkBundleError("collection descriptor is missing")
        descriptor = _json(descriptor_entry["data"], descriptor_logical)
        if descriptor.get("collection_id") != collection_id:
            raise ArkBundleError("collection descriptor identity mismatch")
        collection_dir = target_root / "records" / "collections" / collection_digest
        _safe_write(collection_dir / "collection.json", descriptor_entry["data"])

        snapshot_entries = [
            by_path[path]
            for path in bootstrap["collection_paths"]
            if "/snapshots/" in path
        ]
        snapshots: dict[str, dict[str, Any]] = {}
        for entry in snapshot_entries:
            snapshot = _json(entry["data"], entry["logical_path"])
            snapshot_id = snapshot.get("snapshot_id")
            snapshot_digest = _digest(snapshot_id, "snapshot_id")
            snapshots[snapshot_id] = snapshot
            _safe_write(
                collection_dir / "snapshots" / f"{snapshot_digest}.json",
                entry["data"],
            )

        exact_snapshot_id = collection_ref["snapshot_id"]
        if exact_snapshot_id not in snapshots:
            raise ArkBundleError("exact collection snapshot is missing")
        _safe_write(
            collection_dir / "HEAD.json",
            canonical_json_bytes({"snapshot_id": exact_snapshot_id}),
        )

    run_id = bootstrap["run_id"]
    run_digest = _digest(run_id, "run_id")
    run_logical = f"runs/{run_digest}.json"
    run_entry = by_path.get(run_logical)
    if run_entry is None:
        raise ArkBundleError("run record is missing")
    run = _json(run_entry["data"], run_logical)
    if run.get("run_id") != run_id:
        raise ArkBundleError("run record identity mismatch")
    _safe_write(target_root / "records" / "runs" / f"{run_digest}.json", run_entry["data"])

    events: list[dict[str, Any]] = []
    for logical in bootstrap["event_paths"]:
        entry = by_path[logical]
        event = _json(entry["data"], logical)
        event_id = event.get("event_id")
        event_digest = _digest(event_id, "event_id")
        events.append(event)
        _safe_write(
            target_root / "records" / "run-events" / f"{event_digest}.json",
            entry["data"],
        )
    events.sort(key=lambda event: event["sequence"])
    expected_sequences = list(range(len(events)))
    if [event["sequence"] for event in events] != expected_sequences:
        raise ArkBundleError("recovered event sequence is not contiguous")
    head = {
        "run_id": run_id,
        "event_id": events[-1]["event_id"] if events else None,
        "sequence": events[-1]["sequence"] if events else -1,
    }
    _safe_write(
        target_root / "records" / "run-heads" / f"{run_digest}.json",
        canonical_json_bytes(head),
    )

    restored = InteractionStore(target_root)
    report = restored.verify_run(run_id)

    if collection_ref is not None:
        collection_id = collection_ref["collection_id"]
        cursor = restored.storage.get_collection_snapshot(
            collection_id, collection_ref["snapshot_id"]
        )
        expected_revision = cursor["revision"]
        seen: set[str] = set()
        while True:
            snapshot_id = cursor["snapshot_id"]
            if snapshot_id in seen:
                raise ArkBundleError("recovered collection lineage loop")
            seen.add(snapshot_id)
            if cursor["revision"] != expected_revision:
                raise ArkBundleError("recovered collection revision chain is discontinuous")
            previous = cursor["previous_snapshot_id"]
            if previous is None:
                if cursor["revision"] != 0:
                    raise ArkBundleError("recovered collection lineage did not reach revision 0")
                break
            expected_revision -= 1
            cursor = restored.storage.get_collection_snapshot(collection_id, previous)

    if report["fingerprint"] != bootstrap["run_fingerprint"]:
        raise ArkBundleError("recovered run fingerprint does not match bundle bootstrap")
    return report


def verify_ark_bundle(capsule: bytes) -> dict[str, Any]:
    """Verify container fixed point and a full offline reconstruction."""
    try:
        container_report = verify_capsule(capsule)
    except RestoreCapsuleError as exc:
        raise ArkBundleError(str(exc)) from exc
    bootstrap, _ = _entry_map(capsule)
    with tempfile.TemporaryDirectory() as temp:
        report = _reconstruct(capsule, Path(temp) / "store")
    return {
        "protocol": PROTOCOL,
        "status": "verified",
        "run_id": bootstrap["run_id"],
        "run_fingerprint": report["fingerprint"],
        "privacy_class": bootstrap["privacy_class"],
        "collection_snapshot_id": (
            bootstrap["collection_ref"]["snapshot_id"]
            if bootstrap["collection_ref"] is not None
            else None
        ),
        "entry_count": container_report["entry_count"],
        "capsule_sha256": container_report["capsule_sha256"],
        "fixed_point": True,
        "offline_round_trip": True,
        "authority": AUTHORITY,
    }


def restore_ark_bundle(capsule: bytes, target_root: str | Path) -> dict[str, Any]:
    """Restore into a new local CONTROL store and verify it before returning."""
    target = Path(target_root)
    if target.exists():
        raise ArkBundleError("recovery target must not already exist")
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.restore-", dir=parent)
    )
    try:
        report = _reconstruct(capsule, staging, require_absent=False)
        os.replace(staging, target)
        return {
            "protocol": PROTOCOL,
            "status": "restored",
            "target": str(target),
            "run_id": report["run_id"],
            "fingerprint": report["fingerprint"],
            "authority": AUTHORITY,
        }
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def bundle_privacy_class(capsule: bytes) -> str:
    bootstrap, _ = _entry_map(capsule)
    value = bootstrap.get("privacy_class")
    if value not in PRIVACY_RANK:
        raise ArkBundleError("bundle privacy class is invalid")
    return value
