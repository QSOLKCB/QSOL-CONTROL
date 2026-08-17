#!/usr/bin/env python3
"""Dependency-free persistent storage substrate for QSOL-CONTROL.

Canonical file bytes and collection snapshots are durable state. Search indexes are
explicitly derived, rebuildable state and never acquire evidence or truth authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SHA256_REF_RE = re.compile(r"^sha256:([0-9a-f]{64})$")
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
PRIVACY_CLASSES = {"PUBLIC", "INTERNAL", "RESTRICTED"}
RETENTION_CLASSES = {"TRANSIENT", "SESSION", "ARCHIVE"}


class StorageError(ValueError):
    """Raised when persistent-store invariants are violated."""


def canonical_json_bytes(value: Any) -> bytes:
    """Return canonical UTF-8 JSON bytes used for content identity."""
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_timestamp(value: str) -> str:
    if not isinstance(value, str):
        raise StorageError("timestamp must be an ISO-8601 string")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise StorageError("timestamp must be valid ISO-8601") from exc
    if parsed.tzinfo is None:
        raise StorageError("timestamp must include an explicit UTC offset")
    return value


def _digest_from_ref(reference: str) -> str:
    match = SHA256_REF_RE.fullmatch(reference)
    if match is None:
        raise StorageError(f"invalid content reference: {reference!r}")
    return match.group(1)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temp_path = Path(handle.name)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StorageError(f"cannot read canonical JSON record: {path}") from exc
    if not isinstance(value, dict):
        raise StorageError(f"canonical record must be an object: {path}")
    return value


def _token_counts(text: str) -> dict[str, int]:
    return dict(sorted(Counter(token.lower() for token in TOKEN_RE.findall(text)).items()))


def _sparse_cosine(left: dict[str, int], right: dict[str, int]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(count * right.get(term, 0) for term, count in left.items())
    if dot == 0:
        return 0.0
    left_norm = math.sqrt(sum(count * count for count in left.values()))
    right_norm = math.sqrt(sum(count * count for count in right.values()))
    return dot / (left_norm * right_norm)


def _dense_cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise StorageError("vector dimensions must match and be non-zero")
    if any(not math.isfinite(value) for value in left + right):
        raise StorageError("vectors must contain only finite numbers")
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


class ControlStore:
    """Content-addressed Files plus persistent, snapshot-based Collections."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.objects = self.root / "objects" / "sha256"
        self.file_records = self.root / "records" / "files"
        self.collections = self.root / "records" / "collections"
        self.indexes = self.root / "records" / "indexes"
        for path in (self.objects, self.file_records, self.collections, self.indexes):
            path.mkdir(parents=True, exist_ok=True)

    def _object_path(self, object_id: str) -> Path:
        digest = _digest_from_ref(object_id)
        return self.objects / digest[:2] / digest

    def _file_record_path(self, file_id: str) -> Path:
        return self.file_records / f"{_digest_from_ref(file_id)}.json"

    def _collection_dir(self, collection_id: str) -> Path:
        return self.collections / _digest_from_ref(collection_id)

    def _index_path(self, index_id: str) -> Path:
        return self.indexes / f"{_digest_from_ref(index_id)}.json"

    @staticmethod
    def _identity(payload: dict[str, Any]) -> str:
        return sha256_ref(canonical_json_bytes(payload))

    @staticmethod
    def _validate_classes(privacy_class: str, retention_class: str) -> None:
        if privacy_class == "FORBIDDEN" or privacy_class not in PRIVACY_CLASSES:
            raise StorageError("FORBIDDEN or unknown privacy class cannot enter durable storage")
        if retention_class not in RETENTION_CLASSES:
            raise StorageError("unknown retention class")

    def put_file(
        self,
        content: bytes | str,
        *,
        filename: str,
        media_type: str = "text/plain",
        created_at: str | None = None,
        privacy_class: str = "INTERNAL",
        retention_class: str = "ARCHIVE",
        source: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist bytes once and create an immutable metadata record referencing them."""
        if not isinstance(filename, str) or not filename or len(filename) > 512:
            raise StorageError("filename must be 1..512 characters")
        if not isinstance(media_type, str) or not media_type or len(media_type) > 256:
            raise StorageError("media_type must be 1..256 characters")
        self._validate_classes(privacy_class, retention_class)
        timestamp = _validate_timestamp(created_at or _utc_now())
        payload_bytes = content.encode("utf-8") if isinstance(content, str) else bytes(content)
        object_id = sha256_ref(payload_bytes)
        object_path = self._object_path(object_id)
        if object_path.exists():
            existing = object_path.read_bytes()
            if sha256_ref(existing) != object_id or existing != payload_bytes:
                raise StorageError("content-addressed object collision or corruption detected")
        else:
            _atomic_write(object_path, payload_bytes)

        identity_payload = {
            "protocol": "qsol-control-file/1",
            "object_id": object_id,
            "content_sha256": sha256_hex(payload_bytes),
            "size_bytes": len(payload_bytes),
            "filename": filename,
            "media_type": media_type,
            "created_at": timestamp,
            "privacy_class": privacy_class,
            "retention_class": retention_class,
            "source": source or {"kind": "operator", "locator": "local"},
            "metadata": metadata or {},
        }
        file_id = self._identity(identity_payload)
        record = {"file_id": file_id, **identity_payload}
        record_path = self._file_record_path(file_id)
        encoded = canonical_json_bytes(record)
        if record_path.exists() and record_path.read_bytes() != encoded:
            raise StorageError("file record identity collision detected")
        if not record_path.exists():
            _atomic_write(record_path, encoded)
        return record

    def get_file_record(self, file_id: str) -> dict[str, Any]:
        path = self._file_record_path(file_id)
        if not path.is_file():
            raise StorageError(f"unknown file_id: {file_id}")
        record = _read_json(path)
        identity_payload = {key: value for key, value in record.items() if key != "file_id"}
        if self._identity(identity_payload) != file_id:
            raise StorageError("file record content identity mismatch")
        return record

    def read_file(self, file_id: str) -> bytes:
        record = self.get_file_record(file_id)
        path = self._object_path(record["object_id"])
        if not path.is_file():
            raise StorageError("file record references a missing object")
        data = path.read_bytes()
        if sha256_hex(data) != record["content_sha256"] or len(data) != record["size_bytes"]:
            raise StorageError("stored object failed size/hash verification")
        return data

    def create_collection(
        self,
        *,
        name: str,
        created_at: str | None = None,
        privacy_class: str = "INTERNAL",
        retention_class: str = "ARCHIVE",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a persistent Collection with an immutable empty revision 0 snapshot."""
        if not isinstance(name, str) or not name or len(name) > 256:
            raise StorageError("collection name must be 1..256 characters")
        self._validate_classes(privacy_class, retention_class)
        timestamp = _validate_timestamp(created_at or _utc_now())
        descriptor_payload = {
            "protocol": "qsol-control-collection/1",
            "name": name,
            "created_at": timestamp,
            "privacy_class": privacy_class,
            "retention_class": retention_class,
            "metadata": metadata or {},
        }
        collection_id = self._identity(descriptor_payload)
        descriptor = {"collection_id": collection_id, **descriptor_payload}
        collection_dir = self._collection_dir(collection_id)
        descriptor_path = collection_dir / "collection.json"
        if descriptor_path.exists():
            existing = _read_json(descriptor_path)
            if existing != descriptor:
                raise StorageError("collection identity collision detected")
            return {**descriptor, "head_snapshot_id": self._read_head(collection_id)}

        _atomic_write(descriptor_path, canonical_json_bytes(descriptor))
        snapshot = self._write_snapshot(
            collection_id,
            revision=0,
            previous_snapshot_id=None,
            members=[],
            created_at=timestamp,
        )
        self._write_head(collection_id, snapshot["snapshot_id"])
        return {**descriptor, "head_snapshot_id": snapshot["snapshot_id"]}

    def get_collection(self, collection_id: str) -> dict[str, Any]:
        path = self._collection_dir(collection_id) / "collection.json"
        if not path.is_file():
            raise StorageError(f"unknown collection_id: {collection_id}")
        descriptor = _read_json(path)
        identity_payload = {key: value for key, value in descriptor.items() if key != "collection_id"}
        if self._identity(identity_payload) != collection_id:
            raise StorageError("collection descriptor identity mismatch")
        return {**descriptor, "head_snapshot_id": self._read_head(collection_id)}

    def _head_path(self, collection_id: str) -> Path:
        return self._collection_dir(collection_id) / "HEAD.json"

    def _read_head(self, collection_id: str) -> str:
        head = _read_json(self._head_path(collection_id))
        snapshot_id = head.get("snapshot_id")
        _digest_from_ref(snapshot_id)
        return snapshot_id

    def _write_head(self, collection_id: str, snapshot_id: str) -> None:
        _digest_from_ref(snapshot_id)
        _atomic_write(self._head_path(collection_id), canonical_json_bytes({"snapshot_id": snapshot_id}))

    def _snapshot_path(self, collection_id: str, snapshot_id: str) -> Path:
        digest = _digest_from_ref(snapshot_id)
        return self._collection_dir(collection_id) / "snapshots" / f"{digest}.json"

    def _write_snapshot(
        self,
        collection_id: str,
        *,
        revision: int,
        previous_snapshot_id: str | None,
        members: list[str],
        created_at: str,
    ) -> dict[str, Any]:
        payload = {
            "protocol": "qsol-control-collection-snapshot/1",
            "collection_id": collection_id,
            "revision": revision,
            "previous_snapshot_id": previous_snapshot_id,
            "created_at": _validate_timestamp(created_at),
            "members": sorted(members),
        }
        snapshot_id = self._identity(payload)
        record = {"snapshot_id": snapshot_id, **payload}
        path = self._snapshot_path(collection_id, snapshot_id)
        encoded = canonical_json_bytes(record)
        if path.exists() and path.read_bytes() != encoded:
            raise StorageError("collection snapshot identity collision detected")
        if not path.exists():
            _atomic_write(path, encoded)
        return record

    def get_collection_snapshot(
        self, collection_id: str, snapshot_id: str | None = None
    ) -> dict[str, Any]:
        self.get_collection(collection_id)
        selected = snapshot_id or self._read_head(collection_id)
        path = self._snapshot_path(collection_id, selected)
        if not path.is_file():
            raise StorageError("collection snapshot does not exist")
        record = _read_json(path)
        identity_payload = {key: value for key, value in record.items() if key != "snapshot_id"}
        if self._identity(identity_payload) != selected:
            raise StorageError("collection snapshot identity mismatch")
        if record.get("collection_id") != collection_id:
            raise StorageError("snapshot belongs to a different collection")
        return record

    def update_collection(
        self,
        collection_id: str,
        *,
        add: Iterable[str] = (),
        remove: Iterable[str] = (),
        created_at: str | None = None,
    ) -> dict[str, Any]:
        """Create a new immutable collection membership snapshot and atomically move HEAD."""
        current = self.get_collection_snapshot(collection_id)
        members = set(current["members"])
        additions = set(add)
        removals = set(remove)
        if additions & removals:
            raise StorageError("the same file cannot be added and removed in one update")
        for file_id in additions:
            self.get_file_record(file_id)
        missing_removals = removals - members
        if missing_removals:
            raise StorageError(f"cannot remove non-member files: {sorted(missing_removals)}")
        members |= additions
        members -= removals
        ordered = sorted(members)
        if ordered == current["members"]:
            return current
        snapshot = self._write_snapshot(
            collection_id,
            revision=current["revision"] + 1,
            previous_snapshot_id=current["snapshot_id"],
            members=ordered,
            created_at=created_at or _utc_now(),
        )
        self._write_head(collection_id, snapshot["snapshot_id"])
        return snapshot

    def list_collection_files(self, collection_id: str) -> list[dict[str, Any]]:
        snapshot = self.get_collection_snapshot(collection_id)
        return [self.get_file_record(file_id) for file_id in snapshot["members"]]

    def _index_head_path(self, collection_id: str, kind: str) -> Path:
        safe_kind = kind.replace("-", "_")
        return self._collection_dir(collection_id) / "index-heads" / f"{safe_kind}.json"

    def _write_index(self, collection_id: str, kind: str, record: dict[str, Any]) -> dict[str, Any]:
        index_id = record["index_id"]
        path = self._index_path(index_id)
        encoded = canonical_json_bytes(record)
        if path.exists():
            existing = _read_json(path)
            if existing != record:
                # Built-at timestamps are not part of index identity; preserve first durable build.
                comparable_existing = {k: v for k, v in existing.items() if k != "built_at"}
                comparable_record = {k: v for k, v in record.items() if k != "built_at"}
                if comparable_existing != comparable_record:
                    raise StorageError("search-index identity collision detected")
                record = existing
        else:
            _atomic_write(path, encoded)
        _atomic_write(
            self._index_head_path(collection_id, kind),
            canonical_json_bytes({"index_id": index_id, "snapshot_id": record["snapshot_id"]}),
        )
        return record

    def _read_index_head(self, collection_id: str, kind: str) -> dict[str, Any] | None:
        path = self._index_head_path(collection_id, kind)
        if not path.is_file():
            return None
        return _read_json(path)

    def get_index(self, index_id: str) -> dict[str, Any]:
        path = self._index_path(index_id)
        if not path.is_file():
            raise StorageError(f"unknown index_id: {index_id}")
        return _read_json(path)

    def build_lexical_index(
        self, collection_id: str, *, built_at: str | None = None
    ) -> dict[str, Any]:
        """Build a deterministic offline retrieval baseline for the current snapshot."""
        snapshot = self.get_collection_snapshot(collection_id)
        documents: dict[str, dict[str, int]] = {}
        skipped: list[str] = []
        for file_id in snapshot["members"]:
            record = self.get_file_record(file_id)
            try:
                text = self.read_file(file_id).decode("utf-8")
            except UnicodeDecodeError:
                skipped.append(file_id)
                continue
            documents[file_id] = _token_counts(text)
        basis = {
            "protocol": "qsol-control-search-index/1",
            "kind": "deterministic-lexical-baseline",
            "engine": "qsol.term-frequency-cosine/1",
            "collection_id": collection_id,
            "snapshot_id": snapshot["snapshot_id"],
            "documents": documents,
            "skipped_file_ids": sorted(skipped),
            "derived": True,
            "rebuildable": True,
            "authority": "none",
        }
        index_id = self._identity(basis)
        record = {
            "index_id": index_id,
            **basis,
            "built_at": _validate_timestamp(built_at or _utc_now()),
        }
        return self._write_index(collection_id, "deterministic-lexical-baseline", record)

    def search_lexical(
        self, collection_id: str, query: str, *, limit: int = 10
    ) -> list[dict[str, Any]]:
        if not isinstance(query, str) or not query.strip():
            raise StorageError("search query must be non-empty")
        if not isinstance(limit, int) or not (1 <= limit <= 100):
            raise StorageError("search limit must be 1..100")
        snapshot = self.get_collection_snapshot(collection_id)
        head = self._read_index_head(collection_id, "deterministic-lexical-baseline")
        if head is None or head.get("snapshot_id") != snapshot["snapshot_id"]:
            index = self.build_lexical_index(collection_id)
        else:
            index = self.get_index(head["index_id"])
        query_terms = _token_counts(query)
        scored: list[tuple[float, str]] = []
        for file_id, terms in index["documents"].items():
            score = _sparse_cosine(query_terms, terms)
            if score > 0.0:
                scored.append((score, file_id))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [
            {
                "rank": rank,
                "file_id": file_id,
                "score": score,
                "score_meaning": "retrieval_similarity_not_truth_or_evidence_strength",
                "index_id": index["index_id"],
                "snapshot_id": index["snapshot_id"],
            }
            for rank, (score, file_id) in enumerate(scored[:limit], 1)
        ]

    def register_semantic_index(
        self,
        collection_id: str,
        *,
        vectors: dict[str, list[float]],
        embedding: dict[str, Any],
        built_at: str | None = None,
    ) -> dict[str, Any]:
        """Persist externally produced embedding vectors for semantic retrieval.

        CONTROL does not generate embeddings here. The caller must identify the embedding
        provider/model/revision so future systems can rebuild or reinterpret the index.
        """
        snapshot = self.get_collection_snapshot(collection_id)
        members = set(snapshot["members"])
        if set(vectors) != members:
            raise StorageError("semantic index vectors must cover exactly the current collection snapshot")
        if not members:
            raise StorageError("cannot build a semantic index for an empty collection")
        if not isinstance(embedding, dict):
            raise StorageError("embedding descriptor must be an object")
        for field in ("provider", "model_id", "revision", "dimensions"):
            if field not in embedding:
                raise StorageError(f"embedding descriptor missing {field}")
        dimensions = embedding["dimensions"]
        if not isinstance(dimensions, int) or dimensions < 1:
            raise StorageError("embedding dimensions must be a positive integer")
        normalized_vectors: dict[str, list[float]] = {}
        for file_id in sorted(vectors):
            vector = vectors[file_id]
            if len(vector) != dimensions:
                raise StorageError("semantic vector dimension mismatch")
            normalized = [float(value) for value in vector]
            if any(not math.isfinite(value) for value in normalized):
                raise StorageError("semantic vectors must contain finite numbers")
            normalized_vectors[file_id] = normalized
        basis = {
            "protocol": "qsol-control-search-index/1",
            "kind": "semantic-vector",
            "engine": "qsol.cosine-vector-search/1",
            "collection_id": collection_id,
            "snapshot_id": snapshot["snapshot_id"],
            "embedding": embedding,
            "vectors": normalized_vectors,
            "derived": True,
            "rebuildable": True,
            "authority": "none",
        }
        index_id = self._identity(basis)
        record = {
            "index_id": index_id,
            **basis,
            "built_at": _validate_timestamp(built_at or _utc_now()),
        }
        return self._write_index(collection_id, "semantic-vector", record)

    def search_semantic(
        self,
        collection_id: str,
        query_vector: Iterable[float],
        *,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        if not isinstance(limit, int) or not (1 <= limit <= 100):
            raise StorageError("search limit must be 1..100")
        snapshot = self.get_collection_snapshot(collection_id)
        head = self._read_index_head(collection_id, "semantic-vector")
        if head is None:
            raise StorageError("collection has no semantic index")
        if head.get("snapshot_id") != snapshot["snapshot_id"]:
            raise StorageError("semantic index is stale for the current collection snapshot")
        index = self.get_index(head["index_id"])
        vector = [float(value) for value in query_vector]
        dimensions = index["embedding"]["dimensions"]
        if len(vector) != dimensions:
            raise StorageError("query vector dimension mismatch")
        scored = [
            (_dense_cosine(vector, document_vector), file_id)
            for file_id, document_vector in index["vectors"].items()
        ]
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [
            {
                "rank": rank,
                "file_id": file_id,
                "score": score,
                "score_meaning": "semantic_similarity_not_truth_or_evidence_strength",
                "index_id": index["index_id"],
                "snapshot_id": index["snapshot_id"],
                "embedding": index["embedding"],
            }
            for rank, (score, file_id) in enumerate(scored[:limit], 1)
        ]

    def fingerprint(self) -> dict[str, Any]:
        """Return a deterministic inventory fingerprint for durable canonical state."""
        file_ids = sorted(f"sha256:{path.stem}" for path in self.file_records.glob("*.json"))
        collection_rows = []
        for directory in sorted(path for path in self.collections.iterdir() if path.is_dir()):
            collection_id = f"sha256:{directory.name}"
            collection_rows.append(
                {"collection_id": collection_id, "head_snapshot_id": self._read_head(collection_id)}
            )
        object_ids = []
        for prefix in sorted(path for path in self.objects.iterdir() if path.is_dir()):
            for path in sorted(item for item in prefix.iterdir() if item.is_file()):
                object_ids.append(f"sha256:{path.name}")
        inventory = {
            "protocol": "qsol-control-storage-fingerprint/1",
            "file_ids": file_ids,
            "collection_heads": collection_rows,
            "object_ids": object_ids,
        }
        return {**inventory, "fingerprint": self._identity(inventory)}

    def verify(self) -> dict[str, Any]:
        """Verify canonical file objects, collection snapshot chains, and current memberships."""
        verified_files = 0
        for path in sorted(self.file_records.glob("*.json")):
            file_id = f"sha256:{path.stem}"
            self.read_file(file_id)
            verified_files += 1

        verified_collections = 0
        verified_snapshots = 0
        for directory in sorted(path for path in self.collections.iterdir() if path.is_dir()):
            collection_id = f"sha256:{directory.name}"
            self.get_collection(collection_id)
            head = self.get_collection_snapshot(collection_id)
            cursor = head
            expected_revision = head["revision"]
            seen: set[str] = set()
            while True:
                snapshot_id = cursor["snapshot_id"]
                if snapshot_id in seen:
                    raise StorageError("collection snapshot lineage loop detected")
                seen.add(snapshot_id)
                if cursor["revision"] != expected_revision:
                    raise StorageError("collection snapshot revision chain is discontinuous")
                for file_id in cursor["members"]:
                    self.get_file_record(file_id)
                verified_snapshots += 1
                previous = cursor["previous_snapshot_id"]
                if previous is None:
                    if cursor["revision"] != 0:
                        raise StorageError("collection lineage terminated before revision 0")
                    break
                expected_revision -= 1
                cursor = self.get_collection_snapshot(collection_id, previous)
            verified_collections += 1

        return {
            "protocol": "qsol-control-storage-verification/1",
            "status": "valid",
            "files": verified_files,
            "collections": verified_collections,
            "snapshots": verified_snapshots,
            "fingerprint": self.fingerprint()["fingerprint"],
        }
