#!/usr/bin/env python3
"""Phase 8 repository-level QSOL-CONTROL recovery package.

The package is a deterministic directory containing bounded QSOL-RESTORE-DAT/1
capsules, a canonical bootstrap, and a plain-text recovery map. Canonical CONTROL
state is fingerprinted independently of transport chunking. Search-index
summaries and DNA projections remain optional derived recovery aids.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator

from storage.ark_recovery_bundle import LATTICE_DESCRIPTOR
from storage.control_store import PRIVACY_RANK, ControlStore, StorageError, canonical_json_bytes, sha256_hex
from storage.dna_lattice import PHI_GATED_TRAVERSAL, encode_projection
from storage.interaction_store import InteractionStore
from storage.model_state_registry import ModelStateRegistry
from storage.replay_store import ReplayStore
from storage.restore_capsule import CONTAINER, RestoreCapsuleError, pack_capsule, parse_capsule, verify_capsule

PROTOCOL = "qsol-control-ark-repository-recovery/1"
BOOTSTRAP_NAME = "CONTROL-REPOSITORY-RECOVERY.json"
RECOVERY_MAP_NAME = "RECOVERY-MAP.txt"
AUTHORITY = "none"
MIN_PRIVACY_CLASS = "INTERNAL"
MAX_PACKAGE_FILES = 250_000
MAX_CAPSULE_ENTRIES = 1000
MAX_CAPSULE_PAYLOAD_BYTES = 64 * 1024 * 1024
MAX_CAPSULE_FILE_BYTES = 72 * 1024 * 1024
MAX_CAPSULE_COUNT = 10_000
MAX_BOOTSTRAP_BYTES = 4 * 1024 * 1024
MAX_RECOVERY_MAP_BYTES = 4 * 1024 * 1024
LARGE_OBJECT_CHUNK_BYTES = 32 * 1024 * 1024
MAX_LARGE_OBJECT_CHUNKS = 100_000
DEFAULT_DNA_MAX_FILE_BYTES = 1024 * 1024
JSON_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"

BOUNDARIES = (
    "RECOVERY_PACKAGE != SEMANTIC_AUTHORITY",
    "RAW_OBJECT_BYTES = CANONICAL",
    "SEARCH_INDEX_DESCRIPTOR != CANONICAL_MEMORY",
    "DNA_PROJECTION != CANONICAL_SOURCE",
    "LATTICE_ADDRESS != TRUTH",
    "HASH_INTEGRITY != EVIDENCE_AUTHORITY",
    "RESTORED_CONTEXT != ORIGINAL_ASSISTANT_INSTANCE",
)

CANONICAL_RECORD_DIRS = (
    ("records/files", "control-file-record"),
    ("records/runs", "control-interaction-run"),
    ("records/run-events", "control-run-event"),
    ("records/run-heads", "control-run-head"),
    ("records/model-states", "control-model-state"),
    ("records/replays", "control-replay-record"),
    ("records/replay-reports", "control-replay-report"),
)


class ArkRepositoryBundleError(ValueError):
    """Raised when the Phase 8 repository recovery contract is violated."""


@dataclass(frozen=True)
class SourceFile:
    path: Path
    sha256: str
    size_bytes: int


SourceData = bytes | SourceFile
SourceEntry = tuple[str, SourceData, str, str]


def _sha_ref(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _safe_relative(value: Any) -> str:
    if not isinstance(value, str):
        raise ArkRepositoryBundleError("recovery logical path must be text")
    path = PurePosixPath(value)
    if (
        not value or path.is_absolute() or value.startswith("/") or "\\" in value
        or path.as_posix() != value or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ArkRepositoryBundleError("recovery logical path is unsafe")
    return value


def _require_store_root(root: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise ArkRepositoryBundleError("CONTROL recovery source root must already exist as a non-symlink directory")


def _regular_size(path: Path, label: str, *, maximum: int | None = None) -> int:
    if path.is_symlink() or not path.is_file():
        raise ArkRepositoryBundleError(f"{label} must be a regular non-symlink file")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ArkRepositoryBundleError(f"cannot stat {label}") from exc
    if maximum is not None and size > maximum:
        raise ArkRepositoryBundleError(f"{label} exceeds bounded input size")
    return size


def _read_regular(path: Path, label: str, *, maximum: int | None = None) -> bytes:
    _regular_size(path, label, maximum=maximum)
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ArkRepositoryBundleError(f"cannot read {label}") from exc


def _read_json_bytes(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ArkRepositoryBundleError(f"{label} must be valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ArkRepositoryBundleError(f"{label} must contain a JSON object")
    return value


def _canonical_json_file(path: Path, label: str, *, maximum: int | None = None) -> tuple[dict[str, Any], bytes]:
    data = _read_regular(path, label, maximum=maximum)
    value = _read_json_bytes(data, label)
    if canonical_json_bytes(value) != data:
        raise ArkRepositoryBundleError(f"{label} is not canonical JSON")
    return value, data


def _privacy_max(values: Iterable[str]) -> str:
    classes = list(values)
    if not classes:
        return MIN_PRIVACY_CLASS
    for value in classes:
        if value not in PRIVACY_RANK:
            raise ArkRepositoryBundleError(f"unknown privacy class: {value!r}")
    strongest = max(classes, key=lambda item: PRIVACY_RANK[item])
    return strongest if PRIVACY_RANK[strongest] >= PRIVACY_RANK[MIN_PRIVACY_CLASS] else MIN_PRIVACY_CLASS


def _record_privacy(data: bytes) -> str | None:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        return None
    if isinstance(value, dict) and value.get("privacy_class") in PRIVACY_RANK:
        return value["privacy_class"]
    return None


def _stream_digest(path: Path, label: str) -> tuple[str, int]:
    size = _regular_size(path, label)
    digest = hashlib.sha256()
    seen = 0
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                seen += len(chunk)
    except OSError as exc:
        raise ArkRepositoryBundleError(f"cannot read {label}") from exc
    if seen != size:
        raise ArkRepositoryBundleError(f"{label} changed while being hashed")
    return digest.hexdigest(), size


def _canonical_row(path: str, data: SourceData, kind: str, privacy: str) -> dict[str, Any]:
    if isinstance(data, SourceFile):
        digest, size = data.sha256, data.size_bytes
    else:
        digest, size = sha256_hex(data), len(data)
    return {
        "logical_path": _safe_relative(path), "sha256": digest,
        "size_bytes": size, "kind": kind, "privacy_class": privacy,
    }


def _source_fingerprint(rows: list[dict[str, Any]]) -> str:
    inventory = {
        "protocol": "qsol-control-ark-repository-inventory/1",
        "canonical_entries": sorted(rows, key=lambda row: row["logical_path"].encode("utf-8")),
        "derived_indexes_excluded": True, "dna_projections_excluded": True,
        "audit_events_excluded": True, "authority": "integrity-only",
    }
    return _sha_ref(canonical_json_bytes(inventory))


def _validate_canonical_store(root: Path) -> tuple[str, dict[str, list[str]]]:
    """Validate every canonical registry entry, including reachability/lineage."""
    _require_store_root(root)
    store = ControlStore(root)
    explicit_privacy: list[str] = []
    object_privacy: dict[str, list[str]] = {}

    file_root = root / "records" / "files"
    file_paths = sorted(file_root.glob("*.json"), key=lambda p: p.name.encode("ascii")) if file_root.exists() else []
    for path in file_paths:
        if path.is_symlink() or re.fullmatch(r"[0-9a-f]{64}\.json", path.name) is None:
            raise ArkRepositoryBundleError("file registry contains malformed entry")
        record = store.get_file_record("sha256:" + path.stem)
        store.read_file(record["file_id"])
        privacy = record.get("privacy_class")
        if privacy not in PRIVACY_RANK:
            raise ArkRepositoryBundleError("file record privacy class is invalid")
        explicit_privacy.append(privacy)
        object_privacy.setdefault(record["object_id"], []).append(privacy)

    collection_root = root / "records" / "collections"
    if collection_root.exists():
        for directory in sorted((p for p in collection_root.iterdir() if p.is_dir()), key=lambda p: p.name.encode("ascii")):
            if directory.is_symlink() or re.fullmatch(r"[0-9a-f]{64}", directory.name) is None:
                raise ArkRepositoryBundleError("collection registry contains malformed directory")
            collection_id = "sha256:" + directory.name
            collection = store.get_collection(collection_id)
            privacy = collection.get("privacy_class")
            if privacy not in PRIVACY_RANK:
                raise ArkRepositoryBundleError("collection privacy class is invalid")
            explicit_privacy.append(privacy)
            cursor = store.get_collection_snapshot(collection_id)
            expected_revision = cursor["revision"]
            seen: set[str] = set()
            while True:
                snapshot_id = cursor["snapshot_id"]
                if snapshot_id in seen:
                    raise ArkRepositoryBundleError("collection snapshot lineage loop detected")
                seen.add(snapshot_id)
                if cursor["revision"] != expected_revision:
                    raise ArkRepositoryBundleError("collection snapshot revision chain is discontinuous")
                for file_id in cursor["members"]:
                    record = store.get_file_record(file_id)
                    if PRIVACY_RANK[record["privacy_class"]] > PRIVACY_RANK[privacy]:
                        raise ArkRepositoryBundleError("collection membership reduces File privacy classification")
                previous = cursor["previous_snapshot_id"]
                if previous is None:
                    if cursor["revision"] != 0:
                        raise ArkRepositoryBundleError("collection snapshot lineage terminated before revision 0")
                    break
                expected_revision -= 1
                cursor = store.get_collection_snapshot(collection_id, previous)
            snapshots = directory / "snapshots"
            actual = {"sha256:" + path.stem for path in snapshots.glob("*.json")} if snapshots.exists() else set()
            if actual != seen:
                raise ArkRepositoryBundleError("collection registry contains unreachable or missing snapshots")

    interactions = InteractionStore(root)
    run_root = root / "records" / "runs"
    run_paths = sorted(run_root.glob("*.json"), key=lambda p: p.name.encode("ascii")) if run_root.exists() else []
    run_ids: list[str] = []
    expected_events: set[str] = set()
    for path in run_paths:
        if path.is_symlink() or re.fullmatch(r"[0-9a-f]{64}\.json", path.name) is None:
            raise ArkRepositoryBundleError("run registry contains malformed entry")
        run_id = "sha256:" + path.stem
        interactions.verify_run(run_id)
        run_ids.append(run_id)
        expected_events.update(event["event_id"] for event in interactions.list_events(run_id))
    event_root = root / "records" / "run-events"
    actual_events = {"sha256:" + path.stem for path in event_root.glob("*.json")} if event_root.exists() else set()
    if actual_events != expected_events:
        raise ArkRepositoryBundleError("run-event registry contains unreachable or missing events")
    head_root = root / "records" / "run-heads"
    actual_heads = {"sha256:" + path.stem for path in head_root.glob("*.json")} if head_root.exists() else set()
    if actual_heads != set(run_ids):
        raise ArkRepositoryBundleError("run-head registry does not exactly match run registry")

    models = ModelStateRegistry(root)
    model_states = models.list_states()
    for state in model_states:
        privacy = state.get("privacy_class")
        if privacy not in PRIVACY_RANK:
            raise ArkRepositoryBundleError("model-state privacy class is invalid")
        explicit_privacy.append(privacy)
        models.verify_state(state["state_id"])
    model_root = root / "records" / "model-states"
    actual_models = {"sha256:" + path.stem for path in model_root.glob("*.json")} if model_root.exists() else set()
    if actual_models != {state["state_id"] for state in model_states}:
        raise ArkRepositoryBundleError("model-state registry contains unvalidated records")

    replays = ReplayStore(root)
    replay_rows = replays.list_replays()
    expected_reports: set[str] = set()
    for replay in replay_rows:
        loaded = replays.get_replay(replay["replay_id"])
        expected_reports.add(loaded["report_id"])
    replay_root = root / "records" / "replays"
    report_root = root / "records" / "replay-reports"
    actual_replays = {"sha256:" + path.stem for path in replay_root.glob("*.json")} if replay_root.exists() else set()
    actual_reports = {"sha256:" + path.stem for path in report_root.glob("*.json")} if report_root.exists() else set()
    if actual_replays != {row["replay_id"] for row in replay_rows}:
        raise ArkRepositoryBundleError("replay registry contains unvalidated records")
    if actual_reports != expected_reports:
        raise ArkRepositoryBundleError("replay-report registry contains orphan or missing reports")

    return _privacy_max(explicit_privacy), object_privacy


def _collection_entries(root: Path, package_privacy: str) -> list[SourceEntry]:
    base = root / "records" / "collections"
    if not base.exists():
        return []
    output: list[SourceEntry] = []
    for directory in sorted((p for p in base.iterdir() if p.is_dir()), key=lambda p: p.name.encode("ascii")):
        descriptor, descriptor_bytes = _canonical_json_file(directory / "collection.json", "collection descriptor")
        privacy = descriptor.get("privacy_class", package_privacy)
        output.append((f"store/records/collections/{directory.name}/collection.json", descriptor_bytes, "control-collection-record", privacy))
        head, head_bytes = _canonical_json_file(directory / "HEAD.json", "collection HEAD")
        if set(head) != {"snapshot_id"}:
            raise ArkRepositoryBundleError("collection HEAD fields are invalid")
        output.append((f"store/records/collections/{directory.name}/HEAD.json", head_bytes, "control-collection-head", privacy))
        snapshots = directory / "snapshots"
        if snapshots.exists():
            for path in sorted(snapshots.glob("*.json"), key=lambda p: p.name.encode("ascii")):
                _, data = _canonical_json_file(path, "collection snapshot")
                output.append((f"store/records/collections/{directory.name}/snapshots/{path.name}", data, "control-collection-snapshot", privacy))
    return output


def _collect_source(root: Path) -> tuple[list[SourceEntry], str, list[dict[str, Any]]]:
    _require_store_root(root)
    package_privacy, object_privacy = _validate_canonical_store(root)
    entries: list[SourceEntry] = []
    rows: list[dict[str, Any]] = []

    objects = root / "objects" / "sha256"
    if objects.exists():
        for prefix in sorted((p for p in objects.iterdir() if p.is_dir()), key=lambda p: p.name.encode("ascii")):
            if prefix.is_symlink() or re.fullmatch(r"[0-9a-f]{2}", prefix.name) is None:
                raise ArkRepositoryBundleError("object store contains malformed prefix")
            for path in sorted((p for p in prefix.iterdir() if p.is_file()), key=lambda p: p.name.encode("ascii")):
                if path.is_symlink() or re.fullmatch(r"[0-9a-f]{64}", path.name) is None or not path.name.startswith(prefix.name):
                    raise ArkRepositoryBundleError("object store contains malformed object path")
                digest, size = _stream_digest(path, "raw object")
                if digest != path.name:
                    raise ArkRepositoryBundleError("raw object path/content hash mismatch")
                privacy = _privacy_max(object_privacy.get("sha256:" + path.name, [package_privacy]))
                logical = f"store/objects/sha256/{prefix.name}/{path.name}"
                source = SourceFile(path=path, sha256=digest, size_bytes=size)
                entries.append((logical, source, "control-raw-object", privacy))
                rows.append(_canonical_row(logical, source, "control-raw-object", privacy))

    for relative, kind in CANONICAL_RECORD_DIRS:
        directory = root / relative
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json"), key=lambda p: p.name.encode("ascii")):
            _, data = _canonical_json_file(path, relative)
            privacy = _record_privacy(data) or package_privacy
            logical = f"store/{relative}/{path.name}"
            entries.append((logical, data, kind, privacy))
            rows.append(_canonical_row(logical, data, kind, privacy))
    for logical, data, kind, privacy in _collection_entries(root, package_privacy):
        entries.append((logical, data, kind, privacy))
        rows.append(_canonical_row(logical, data, kind, privacy))
    if len(rows) > MAX_PACKAGE_FILES:
        raise ArkRepositoryBundleError("repository recovery inventory exceeds file-count limit")
    entries.sort(key=lambda row: row[0].encode("utf-8"))
    rows.sort(key=lambda row: row["logical_path"].encode("utf-8"))
    return entries, package_privacy, rows


def source_privacy_class(root: str | Path) -> str:
    _, privacy, _ = _collect_source(Path(root))
    return privacy


def _schema_entries(repository_root: Path) -> list[SourceEntry]:
    schema_root = repository_root / "schema"
    if schema_root.is_symlink() or not schema_root.is_dir():
        raise ArkRepositoryBundleError("repository schema directory is unavailable")
    output: list[SourceEntry] = []
    for path in sorted(schema_root.glob("*.json"), key=lambda p: p.name.encode("utf-8")):
        data = _read_regular(path, f"schema/{path.name}", maximum=MAX_BOOTSTRAP_BYTES)
        value = _read_json_bytes(data, f"schema/{path.name}")
        if value.get("$schema") != JSON_SCHEMA_DRAFT:
            raise ArkRepositoryBundleError(f"schema/{path.name} uses an unexpected JSON Schema draft")
        output.append((f"schemas/{path.name}", data, "control-json-schema", "PUBLIC"))
    if not output:
        raise ArkRepositoryBundleError("recovery package requires at least one schema")
    return output


def _index_descriptor(index: dict[str, Any]) -> dict[str, Any]:
    descriptor = {
        "protocol": "qsol-control-search-index-recovery-descriptor/1",
        "index_id": index["index_id"], "source_protocol": index["protocol"],
        "kind": index["kind"], "engine": index["engine"],
        "collection_id": index["collection_id"], "snapshot_id": index["snapshot_id"],
        "privacy_class": index["privacy_class"], "collation": index.get("collation"),
        "derived": True, "rebuildable": True, "descriptor_only": True, "authority": "none",
    }
    if index["kind"] == "deterministic-lexical-baseline":
        descriptor.update({"tokenizer": index.get("tokenizer"), "documents_sha256": index.get("documents_sha256"), "skipped_file_ids": index.get("skipped_file_ids", []), "omitted_payload": "documents"})
    elif index["kind"] == "semantic-vector":
        descriptor.update({"embedding": index.get("embedding"), "embedding_sha256": index.get("embedding_sha256"), "vectors_sha256": index.get("vectors_sha256"), "omitted_payload": "vectors"})
    else:
        raise ArkRepositoryBundleError("unknown search-index kind")
    return descriptor


def _optional_entries(root: Path, *, include_indexes: bool, include_dna: bool, dna_max_file_bytes: int) -> tuple[list[SourceEntry], dict[str, Any]]:
    output: list[SourceEntry] = []
    summary = {"index_descriptors_included": 0, "dna_projections_included": 0, "dna_files_skipped_size_limit": 0, "dna_max_file_bytes": dna_max_file_bytes}
    store = ControlStore(root)
    if include_indexes:
        index_root = root / "records" / "indexes"
        if index_root.exists():
            for path in sorted(index_root.glob("*.json"), key=lambda p: p.name.encode("ascii")):
                if path.is_symlink() or re.fullmatch(r"[0-9a-f]{64}\.json", path.name) is None:
                    raise ArkRepositoryBundleError("index registry contains malformed entry")
                index = store.get_index("sha256:" + path.stem)
                output.append((f"optional/index-descriptors/{path.name}", canonical_json_bytes(_index_descriptor(index)), "control-search-index-recovery-descriptor", index["privacy_class"]))
                summary["index_descriptors_included"] += 1
    if include_dna:
        if type(dna_max_file_bytes) is not int or dna_max_file_bytes < 0:
            raise ArkRepositoryBundleError("dna_max_file_bytes must be a non-negative integer")
        file_root = root / "records" / "files"
        if file_root.exists():
            for path in sorted(file_root.glob("*.json"), key=lambda p: p.name.encode("ascii")):
                record = store.get_file_record("sha256:" + path.stem)
                object_path = root / "objects" / "sha256" / record["object_id"][7:9] / record["object_id"][7:]
                size = _regular_size(object_path, "DNA projection source")
                if size > dna_max_file_bytes:
                    summary["dna_files_skipped_size_limit"] += 1
                    continue
                raw = _read_regular(object_path, "DNA projection source", maximum=dna_max_file_bytes)
                projection = encode_projection(raw, traversal_id=PHI_GATED_TRAVERSAL)
                output.append((f"optional/dna/{path.stem}.json", canonical_json_bytes(projection), "control-dna-lattice-projection", record["privacy_class"]))
                summary["dna_projections_included"] += 1
    output.sort(key=lambda row: row[0].encode("utf-8"))
    return output, summary


def _stream_object_entries(logical: str, source: SourceFile, privacy: str) -> Iterator[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    seen = 0
    index = 0
    try:
        with source.path.open("rb") as handle:
            while True:
                chunk = handle.read(LARGE_OBJECT_CHUNK_BYTES)
                if not chunk and index > 0:
                    break
                if not chunk and index == 0:
                    chunk = b""
                digest.update(chunk)
                seen += len(chunk)
                path = f"transport/large-objects/{source.sha256}/{index:08d}.bin"
                chunks.append({"path": path, "sha256": sha256_hex(chunk), "size_bytes": len(chunk)})
                yield {"logical_path": path, "data": chunk, "kind": "control-large-object-chunk", "privacy_class": privacy, "recovery_class": "OUTER_SHELL"}
                index += 1
                if index > MAX_LARGE_OBJECT_CHUNKS:
                    raise ArkRepositoryBundleError("large object exceeds transport chunk-count limit")
                if not chunk:
                    break
    except OSError as exc:
        raise ArkRepositoryBundleError("cannot stream raw object") from exc
    if digest.hexdigest() != source.sha256 or seen != source.size_bytes:
        raise ArkRepositoryBundleError("raw object changed during transport streaming")
    manifest = {"protocol": "qsol-control-large-object-transport/1", "target_logical_path": logical, "sha256": source.sha256, "size_bytes": source.size_bytes, "chunks": chunks, "transport_only": True, "authority": "none"}
    yield {"logical_path": f"transport/large-objects/{source.sha256}/manifest.json", "data": canonical_json_bytes(manifest), "kind": "control-large-object-transport-manifest", "privacy_class": privacy, "recovery_class": "MID_SHELL"}


def _iter_transport_entries(entries: list[SourceEntry]) -> Iterator[dict[str, Any]]:
    for logical, data, kind, privacy in entries:
        if isinstance(data, SourceFile):
            yield from _stream_object_entries(logical, data, privacy)
            continue
        if logical.startswith(("schemas/", "lattice/")):
            recovery_class = "NEAR_SHELL"
        elif logical.startswith("optional/"):
            recovery_class = "WIGGLE_ZONE"
        elif logical.startswith("store/records/"):
            recovery_class = "MID_SHELL"
        else:
            recovery_class = "OUTER_SHELL"
        yield {"logical_path": logical, "data": data, "kind": kind, "privacy_class": privacy, "recovery_class": recovery_class}


def _iter_capsule_groups(entries: Iterable[dict[str, Any]]) -> Iterator[list[dict[str, Any]]]:
    current: list[dict[str, Any]] = []
    current_bytes = 0
    for entry in entries:
        size = len(entry["data"])
        if size > MAX_CAPSULE_PAYLOAD_BYTES:
            raise ArkRepositoryBundleError("single transport entry exceeds Phase 8 capsule payload budget")
        if current and (len(current) >= MAX_CAPSULE_ENTRIES or current_bytes + size > MAX_CAPSULE_PAYLOAD_BYTES):
            yield current
            current, current_bytes = [], 0
        current.append(entry)
        current_bytes += size
    if current:
        yield current


def _recovery_map(source_rows: list[dict[str, Any]], optional: dict[str, Any]) -> bytes:
    counts: dict[str, int] = {}
    for row in source_rows:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1
    lines = [
        "QSOL-CONTROL PHASE 8 REPOSITORY RECOVERY MAP", "",
        "This package reconstructs canonical CONTROL storage without the WebUI or search engine.",
        "Raw objects remain canonical. Search-index descriptors and DNA projections are optional derived aids.", "",
        "RECOVERY ORDER",
        "1. Verify CONTROL-REPOSITORY-RECOVERY.json and every capsules/*.dat SHA-256.",
        "2. Verify each QSOL-RESTORE-DAT/1 capsule fixed point.",
        "3. Reassemble transport/large-objects chunks and verify original SHA-256.",
        "4. Restore store/ canonical paths, schemas/, and lattice/ support files.",
        "5. Verify every canonical registry and authority boundary.",
        "6. Compare reconstructed canonical inventory fingerprint with source_fingerprint.", "", "CANONICAL INVENTORY",
    ]
    for kind in sorted(counts, key=lambda value: value.encode("utf-8")):
        lines.append(f"- {kind}: {counts[kind]}")
    lines.extend(["", "OPTIONAL DERIVED MATERIAL", f"- search-index descriptors: {optional['index_descriptors_included']}", f"- DNA/lattice projections: {optional['dna_projections_included']}", f"- DNA files skipped by size limit: {optional['dna_files_skipped_size_limit']}", "", "BOUNDARIES", *[f"- {item}" for item in BOUNDARIES], ""])
    encoded = "\n".join(lines).encode("utf-8")
    if len(encoded) > MAX_RECOVERY_MAP_BYTES:
        raise ArkRepositoryBundleError("recovery map exceeds bounded size")
    return encoded


def _atomic_bytes(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise ArkRepositoryBundleError(f"output already exists: {path}")
    with path.open("xb") as handle:
        if os.name != "nt": os.fchmod(handle.fileno(), mode)
        handle.write(data); handle.flush(); os.fsync(handle.fileno())
    if os.name != "nt": os.chmod(path, mode, follow_symlinks=False)


def build_repository_recovery_package(root: str | Path, output: str | Path, *, repository_root: str | Path, include_indexes: bool = False, include_dna: bool = False, dna_max_file_bytes: int = DEFAULT_DNA_MAX_FILE_BYTES) -> dict[str, Any]:
    source_root, destination = Path(root), Path(output)
    _require_store_root(source_root)
    if destination.exists() or destination.is_symlink():
        raise ArkRepositoryBundleError("recovery package output must not already exist")
    canonical_entries, privacy_class, rows = _collect_source(source_root)
    schema_entries = _schema_entries(Path(repository_root))
    optional_entries, optional_summary = _optional_entries(source_root, include_indexes=include_indexes, include_dna=include_dna, dna_max_file_bytes=dna_max_file_bytes)
    support_entries: list[SourceEntry] = [("lattice/profile.json", canonical_json_bytes(LATTICE_DESCRIPTOR), "control-lattice-profile", "PUBLIC")]
    all_entries = sorted(canonical_entries + schema_entries + support_entries + optional_entries, key=lambda row: row[0].encode("utf-8"))
    source_fingerprint = _source_fingerprint(rows)
    map_bytes = _recovery_map(rows, optional_summary)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.build-", dir=destination.parent))
    try:
        capsule_rows: list[dict[str, Any]] = []
        for index, group in enumerate(_iter_capsule_groups(_iter_transport_entries(all_entries))):
            if index >= MAX_CAPSULE_COUNT:
                raise ArkRepositoryBundleError("repository recovery package exceeds capsule-count limit")
            try:
                capsule = pack_capsule(group); report = verify_capsule(capsule)
            except RestoreCapsuleError as exc:
                raise ArkRepositoryBundleError(str(exc)) from exc
            if len(capsule) > MAX_CAPSULE_FILE_BYTES:
                raise ArkRepositoryBundleError("generated capsule exceeds on-disk size limit")
            relative = f"capsules/{index:06d}.dat"
            _atomic_bytes(staging / relative, capsule)
            capsule_rows.append({"path": relative, "sha256": sha256_hex(capsule), "size_bytes": len(capsule), "entry_count": report["entry_count"], "fixed_point": True})
        if not capsule_rows:
            raise ArkRepositoryBundleError("recovery package produced no transport entries")
        basis = {
            "protocol": PROTOCOL, "container": CONTAINER, "version": 1,
            "source_fingerprint": source_fingerprint, "privacy_class": privacy_class,
            "canonical_entry_count": len(rows), "schema_count": len(schema_entries),
            "capsules": capsule_rows, "recovery_map_sha256": sha256_hex(map_bytes), "optional": optional_summary,
            "canonical_source": {"raw_objects": True, "file_records": True, "collection_descriptors_snapshots_and_heads": True, "run_records_events_and_heads": True, "model_states": True, "replay_records_and_reports": True, "schemas": "supporting-recovery-contracts", "lattice_profile": "supporting-recovery-contract"},
            "excluded_from_canonical_fingerprint": ["search-indexes", "dna-lattice-projections", "audit-events"],
            "requires_webui": False, "requires_original_search_engine": False, "standard_library_runtime": True,
            "authority": AUTHORITY, "boundaries": list(BOUNDARIES),
        }
        bootstrap = {"package_id": _sha_ref(canonical_json_bytes(basis)), **basis}
        bootstrap_bytes = canonical_json_bytes(bootstrap)
        if len(bootstrap_bytes) > MAX_BOOTSTRAP_BYTES:
            raise ArkRepositoryBundleError("recovery bootstrap exceeds bounded size")
        _atomic_bytes(staging / BOOTSTRAP_NAME, bootstrap_bytes)
        _atomic_bytes(staging / RECOVERY_MAP_NAME, map_bytes)
        if os.name != "nt": os.chmod(staging, 0o700); os.chmod(staging / "capsules", 0o700)
        os.replace(staging, destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True); raise
    return verify_repository_recovery_package(destination)


def _load_bootstrap(package: Path) -> tuple[dict[str, Any], bytes]:
    value, encoded = _canonical_json_file(package / BOOTSTRAP_NAME, BOOTSTRAP_NAME, maximum=MAX_BOOTSTRAP_BYTES)
    if value.get("protocol") != PROTOCOL or value.get("container") != CONTAINER:
        raise ArkRepositoryBundleError("repository recovery bootstrap protocol/container mismatch")
    if value.get("authority") != AUTHORITY or value.get("boundaries") != list(BOUNDARIES):
        raise ArkRepositoryBundleError("repository recovery authority boundary mismatch")
    if value.get("privacy_class") not in PRIVACY_RANK:
        raise ArkRepositoryBundleError("repository recovery privacy class is invalid")
    if value.get("requires_webui") is not False or value.get("requires_original_search_engine") is not False:
        raise ArkRepositoryBundleError("repository recovery must remain independent of WebUI/search engine")
    rows = value.get("capsules")
    if not isinstance(rows, list) or not rows or len(rows) > MAX_CAPSULE_COUNT:
        raise ArkRepositoryBundleError("repository recovery capsules list is invalid")
    package_id = value.get("package_id")
    basis = {key: item for key, item in value.items() if key != "package_id"}
    if package_id != _sha_ref(canonical_json_bytes(basis)):
        raise ArkRepositoryBundleError("repository recovery package_id mismatch")
    return value, encoded


def _capsule_entries(package: Path, bootstrap: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_path: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(bootstrap["capsules"]):
        expected = f"capsules/{index:06d}.dat"
        if not isinstance(row, dict) or row.get("path") != expected:
            raise ArkRepositoryBundleError("repository recovery capsule ordering is invalid")
        declared = row.get("size_bytes")
        if type(declared) is not int or not 0 <= declared <= MAX_CAPSULE_FILE_BYTES:
            raise ArkRepositoryBundleError("repository recovery capsule declared size is invalid")
        path = package / expected
        actual_size = _regular_size(path, expected, maximum=MAX_CAPSULE_FILE_BYTES)
        if actual_size != declared:
            raise ArkRepositoryBundleError("repository recovery capsule size mismatch")
        raw = _read_regular(path, expected, maximum=MAX_CAPSULE_FILE_BYTES)
        if sha256_hex(raw) != row.get("sha256"):
            raise ArkRepositoryBundleError("repository recovery capsule hash mismatch")
        try:
            report = verify_capsule(raw); _, entries = parse_capsule(raw)
        except RestoreCapsuleError as exc:
            raise ArkRepositoryBundleError(str(exc)) from exc
        if report["entry_count"] != row.get("entry_count"):
            raise ArkRepositoryBundleError("repository recovery capsule entry count mismatch")
        for entry in entries:
            logical = _safe_relative(entry["logical_path"])
            if logical in by_path:
                raise ArkRepositoryBundleError("duplicate logical path across recovery capsules")
            by_path[logical] = entry
    return by_path


def _validate_support_entries(entries: dict[str, dict[str, Any]], bootstrap: dict[str, Any]) -> None:
    schema_paths = sorted(path for path in entries if path.startswith("schemas/") and path.endswith(".json"))
    if len(schema_paths) != bootstrap.get("schema_count"):
        raise ArkRepositoryBundleError("recovery schema count mismatch")
    for path in schema_paths:
        value = _read_json_bytes(entries[path]["data"], path)
        if value.get("$schema") != JSON_SCHEMA_DRAFT:
            raise ArkRepositoryBundleError("recovery schema uses unsupported JSON Schema draft")
    lattice = entries.get("lattice/profile.json")
    if lattice is None or _read_json_bytes(lattice["data"], "lattice/profile.json") != LATTICE_DESCRIPTOR:
        raise ArkRepositoryBundleError("recovery lattice profile does not match supported descriptor")
    for path, entry in entries.items():
        if path.startswith("optional/index-descriptors/"):
            value = _read_json_bytes(entry["data"], path)
            if value.get("protocol") != "qsol-control-search-index-recovery-descriptor/1" or value.get("derived") is not True or value.get("rebuildable") is not True or value.get("descriptor_only") is not True or value.get("authority") != "none":
                raise ArkRepositoryBundleError("optional search-index descriptor violates derived-only contract")


def _write_recovered(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise ArkRepositoryBundleError(f"recovery target path already exists: {path}")
    with path.open("xb") as handle:
        handle.write(data); handle.flush(); os.fsync(handle.fileno())


def _reconstruct_large_objects(target: Path, entries: dict[str, dict[str, Any]]) -> None:
    manifests = sorted((path for path in entries if path.startswith("transport/large-objects/") and path.endswith("/manifest.json")), key=lambda value: value.encode("utf-8"))
    for manifest_path in manifests:
        manifest = _read_json_bytes(entries[manifest_path]["data"], manifest_path)
        if manifest.get("protocol") != "qsol-control-large-object-transport/1" or manifest.get("transport_only") is not True or manifest.get("authority") != "none":
            raise ArkRepositoryBundleError("large-object transport contract mismatch")
        target_logical = _safe_relative(manifest.get("target_logical_path"))
        if not target_logical.startswith("store/objects/sha256/"):
            raise ArkRepositoryBundleError("large-object target is outside canonical object store")
        chunks = manifest.get("chunks")
        if not isinstance(chunks, list) or not chunks or len(chunks) > MAX_LARGE_OBJECT_CHUNKS:
            raise ArkRepositoryBundleError("large-object transport chunk list is invalid")
        destination = target / target_logical
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() or destination.is_symlink():
            raise ArkRepositoryBundleError("large-object recovery target already exists")
        digest = hashlib.sha256(); size = 0
        with destination.open("xb") as handle:
            for index, row in enumerate(chunks):
                expected = f"transport/large-objects/{manifest['sha256']}/{index:08d}.bin"
                if not isinstance(row, dict) or row.get("path") != expected:
                    raise ArkRepositoryBundleError("large-object chunk ordering is invalid")
                entry = entries.get(expected)
                if entry is None:
                    raise ArkRepositoryBundleError("large-object chunk is missing")
                data = entry["data"]
                if sha256_hex(data) != row.get("sha256") or len(data) != row.get("size_bytes"):
                    raise ArkRepositoryBundleError("large-object chunk hash/size mismatch")
                handle.write(data); digest.update(data); size += len(data)
        if digest.hexdigest() != manifest.get("sha256") or size != manifest.get("size_bytes"):
            raise ArkRepositoryBundleError("reassembled large object failed source hash/size verification")


def _verify_restored_store(store_root: Path) -> dict[str, Any]:
    privacy, _ = _validate_canonical_store(store_root)
    storage = ControlStore(store_root)
    interactions = InteractionStore(store_root)
    run_root = store_root / "records" / "runs"
    run_ids = ["sha256:" + path.stem for path in sorted(run_root.glob("*.json"), key=lambda p: p.name.encode("ascii"))] if run_root.exists() else []
    models = ModelStateRegistry(store_root).list_states()
    replays = ReplayStore(store_root).list_replays()
    return {"storage": storage.verify(), "runs": len(run_ids), "model_states": len(models), "replays": len(replays), "privacy_class": privacy}


def _reconstructed_source(store_root: Path) -> tuple[list[dict[str, Any]], str]:
    _, privacy, rows = _collect_source(store_root)
    return rows, privacy


def _reconstruct(package: Path, target: Path, *, require_absent: bool = True) -> dict[str, Any]:
    bootstrap, bootstrap_bytes = _load_bootstrap(package)
    map_bytes = _read_regular(package / RECOVERY_MAP_NAME, RECOVERY_MAP_NAME, maximum=MAX_RECOVERY_MAP_BYTES)
    if sha256_hex(map_bytes) != bootstrap.get("recovery_map_sha256"):
        raise ArkRepositoryBundleError("recovery map hash mismatch")
    entries = _capsule_entries(package, bootstrap)
    _validate_support_entries(entries, bootstrap)
    if require_absent and (target.exists() or target.is_symlink()):
        raise ArkRepositoryBundleError("repository recovery target must not already exist")
    target.mkdir(parents=True, exist_ok=not require_absent)
    _write_recovered(target / BOOTSTRAP_NAME, bootstrap_bytes); _write_recovered(target / RECOVERY_MAP_NAME, map_bytes)
    for logical in sorted(entries, key=lambda value: value.encode("utf-8")):
        if logical.startswith("transport/large-objects/"):
            continue
        if not logical.startswith(("store/", "schemas/", "lattice/", "optional/")):
            raise ArkRepositoryBundleError("recovery capsule contains unsupported logical path")
        _write_recovered(target / logical, entries[logical]["data"])
    _reconstruct_large_objects(target, entries)
    report = _verify_restored_store(target / "store")
    rows, privacy = _reconstructed_source(target / "store")
    fingerprint = _source_fingerprint(rows)
    if fingerprint != bootstrap.get("source_fingerprint"):
        raise ArkRepositoryBundleError("reconstructed canonical source fingerprint mismatch")
    if len(rows) != bootstrap.get("canonical_entry_count"):
        raise ArkRepositoryBundleError("reconstructed canonical entry count mismatch")
    if privacy != bootstrap.get("privacy_class"):
        raise ArkRepositoryBundleError("reconstructed package privacy class differs from bootstrap")
    if (target / "store" / "records" / "indexes").exists() and any((target / "store" / "records" / "indexes").iterdir()):
        raise ArkRepositoryBundleError("derived indexes entered canonical reconstructed store")
    return {"protocol": PROTOCOL, "package_id": bootstrap["package_id"], "source_fingerprint": fingerprint, "canonical_entry_count": len(rows), "schema_count": bootstrap["schema_count"], "privacy_class": privacy, "store_verification": report, "webui_required": False, "search_engine_required": False, "authority": AUTHORITY}


def verify_repository_recovery_package(package: str | Path) -> dict[str, Any]:
    root = Path(package)
    if root.is_symlink() or not root.is_dir():
        raise ArkRepositoryBundleError("repository recovery package must be a non-symlink directory")
    bootstrap, _ = _load_bootstrap(root)
    expected_root = {BOOTSTRAP_NAME, RECOVERY_MAP_NAME, "capsules"}
    if {path.name for path in root.iterdir()} != expected_root:
        raise ArkRepositoryBundleError("repository recovery package contains unexpected top-level entries")
    capsule_root = root / "capsules"
    if capsule_root.is_symlink() or not capsule_root.is_dir():
        raise ArkRepositoryBundleError("repository recovery capsules must be a non-symlink directory")
    expected = {Path(row["path"]).name for row in bootstrap["capsules"]}
    actual = {path.name for path in capsule_root.iterdir()}
    if actual != expected:
        raise ArkRepositoryBundleError("repository recovery package capsule set differs from bootstrap")
    for name in actual:
        _regular_size(capsule_root / name, f"capsules/{name}", maximum=MAX_CAPSULE_FILE_BYTES)
    with tempfile.TemporaryDirectory() as temp:
        report = _reconstruct(root, Path(temp) / "restored")
    return {**report, "status": "verified", "capsule_count": len(bootstrap["capsules"]), "offline_round_trip": True, "standard_library_runtime": True}


def restore_repository_recovery_package(package: str | Path, target: str | Path) -> dict[str, Any]:
    package_root, target_root = Path(package), Path(target)
    if target_root.exists() or target_root.is_symlink():
        raise ArkRepositoryBundleError("repository recovery target must not already exist")
    parent = target_root.parent; parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target_root.name}.restore-", dir=parent))
    try:
        report = _reconstruct(package_root, staging, require_absent=False)
        os.replace(staging, target_root)
        return {**report, "status": "restored", "target": str(target_root)}
    except Exception:
        shutil.rmtree(staging, ignore_errors=True); raise


__all__ = [
    "ArkRepositoryBundleError", "BOOTSTRAP_NAME", "DEFAULT_DNA_MAX_FILE_BYTES",
    "LARGE_OBJECT_CHUNK_BYTES", "PROTOCOL", "RECOVERY_MAP_NAME",
    "build_repository_recovery_package", "restore_repository_recovery_package",
    "source_privacy_class", "verify_repository_recovery_package",
]
