from __future__ import annotations

import base64
import binascii
import re
from pathlib import Path
from typing import Any

from adapters.nexus import NexusAdapterError
from adapters.oracle import OracleAdapter, OracleAdapterError
from storage.control_store import ControlStore, StorageError
from storage.interaction_store import InteractionStore
from storage.model_state import ModelStateRegistry

from .common import (
    MAX_DNA_EXPORT_BYTES,
    MAX_LIST_ITEMS,
    MAX_UPLOAD_BYTES,
    MODEL_STATE_LABELS,
    UI_INVARIANTS,
    WEBUI_HEALTH_PROTOCOL,
    WEBUI_PROTOCOL,
    WEBUI_RUN_VIEW_PROTOCOL,
    WEBUI_SESSION_PROTOCOL,
    WebUIConfig,
    WebUIError,
    _canonical_strings,
    _require_sha_ref,
    _require_string,
    _utc_now,
)


class StorageRuntimeMixin:
    def __init__(self, config: WebUIConfig):
        self.config = config
        self.control_root = Path(config.control_root)
        self.store = ControlStore(self.control_root)
        self.interactions = InteractionStore(self.control_root)
        self.models = ModelStateRegistry(self.control_root)

    def session_contract(self) -> dict[str, Any]:
        return {
            "protocol": WEBUI_SESSION_PROTOCOL,
            "webui_protocol": WEBUI_PROTOCOL,
            "question_modes": ["evidence_only", "council"],
            "max_question_characters": 2048,
            "max_upload_bytes": MAX_UPLOAD_BYTES,
            "max_dna_export_bytes": MAX_DNA_EXPORT_BYTES,
            "model_state_labels": MODEL_STATE_LABELS,
            "ui_invariants": list(UI_INVARIANTS),
            "truth_percentage_available": False,
            "hidden_chain_of_thought_available": False,
            "model_mind_available": False,
            "phase7_replay_execution_implemented": False,
            "capabilities": {
                "files": True,
                "collections": True,
                "lexical_search": True,
                "oracle": self.config.oracle_root is not None,
                "nexus": self.config.nexus_command is not None,
                "model_state": True,
                "lattice": True,
                "dna_projection": True,
                "run_compare": True,
            },
        }

    def health(self) -> dict[str, Any]:
        services: dict[str, Any] = {}
        try:
            storage = self.store.verify()
            services["control_storage"] = {
                "configured": True,
                "available": True,
                "status": storage,
            }
        except (StorageError, OSError, ValueError) as exc:
            services["control_storage"] = {
                "configured": True,
                "available": False,
                "error": str(exc),
            }

        if self.config.oracle_root is None:
            services["oracle"] = {"configured": False, "available": False}
        else:
            try:
                availability = OracleAdapter(self.config.oracle_root).availability()
                services["oracle"] = {
                    "configured": True,
                    "available": availability.get("availability") == "available",
                    "status": availability,
                }
            except (OracleAdapterError, StorageError, OSError, ValueError) as exc:
                services["oracle"] = {
                    "configured": True,
                    "available": False,
                    "error": str(exc),
                }

        if self.config.nexus_command is None:
            services["nexus"] = {"configured": False, "available": False}
        else:
            try:
                with self._nexus_adapter() as adapter:
                    discovery = adapter.discover()
                services["nexus"] = {
                    "configured": True,
                    "available": discovery.get("availability") == "available",
                    "status": discovery,
                }
            except (NexusAdapterError, StorageError, OSError, ValueError) as exc:
                services["nexus"] = {
                    "configured": True,
                    "available": False,
                    "error": str(exc),
                }

        return {
            "protocol": WEBUI_HEALTH_PROTOCOL,
            "services": services,
            "ui_invariants": list(UI_INVARIANTS),
            "authority": "status-display-only",
        }

    def oracle_timelock(self) -> dict[str, Any]:
        if self.config.oracle_root is None:
            return {
                "availability": "unconfigured",
                "authority": "none",
                "eligible_is_executed": False,
            }
        return OracleAdapter(self.config.oracle_root).timelock_status()

    def upload_file(self, request: dict[str, Any]) -> dict[str, Any]:
        filename = _require_string(request.get("filename"), "filename", maximum=512)
        media_type = _require_string(
            request.get("media_type", "application/octet-stream"),
            "media_type",
            maximum=256,
        )
        encoded = _require_string(
            request.get("content_base64"), "content_base64", maximum=MAX_UPLOAD_BYTES * 2
        )
        try:
            content = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise WebUIError("content_base64 is not valid base64") from exc
        if len(content) > MAX_UPLOAD_BYTES:
            raise WebUIError(f"file upload exceeds {MAX_UPLOAD_BYTES} bytes")
        record = self.store.put_file(
            content,
            filename=filename,
            media_type=media_type,
            created_at=_utc_now(),
            privacy_class=request.get("privacy_class", "INTERNAL"),
            retention_class=request.get("retention_class", "SESSION"),
            source={"kind": "webui-upload", "locator": "browser-session"},
            metadata={"immediate_context": True},
        )
        return {"protocol": "qsol-control-webui-file-upload/1", "file": record}

    def list_collections(self) -> list[dict[str, Any]]:
        root = self.control_root / "records" / "collections"
        if not root.exists():
            return []
        directories = sorted(
            (item for item in root.iterdir() if item.is_dir()),
            key=lambda item: item.name.encode("ascii"),
        )
        if len(directories) > MAX_LIST_ITEMS:
            raise WebUIError("collection listing exceeds UI limit")
        output = []
        for directory in directories:
            if re.fullmatch(r"[0-9a-f]{64}", directory.name) is None:
                continue
            output.append(self.store.get_collection(f"sha256:{directory.name}"))
        return output

    def collection_detail(self, collection_id: str) -> dict[str, Any]:
        collection_id = _require_sha_ref(collection_id, "collection_id")
        collection = self.store.get_collection(collection_id)
        snapshot = self.store.get_collection_snapshot(collection_id)
        files = [self.store.get_file_record(file_id) for file_id in snapshot["members"]]
        return {"collection": collection, "snapshot": snapshot, "files": files}

    def create_collection(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.store.create_collection(
            name=_require_string(request.get("name"), "name", maximum=256),
            created_at=_utc_now(),
            privacy_class=request.get("privacy_class", "INTERNAL"),
            retention_class=request.get("retention_class", "ARCHIVE"),
            metadata={"created_via": WEBUI_PROTOCOL},
        )

    def update_collection(self, collection_id: str, request: dict[str, Any]) -> dict[str, Any]:
        collection_id = _require_sha_ref(collection_id, "collection_id")
        add = _canonical_strings(request.get("add", []), "add")
        remove = _canonical_strings(request.get("remove", []), "remove")
        for file_id in add + remove:
            _require_sha_ref(file_id, "file_id")
        expected = request.get("expected_head_snapshot_id")
        if expected is None:
            raise WebUIError(
                "expected_head_snapshot_id is required for WebUI Collection updates"
            )
        expected = _require_sha_ref(expected, "expected_head_snapshot_id")
        return self.store.update_collection(
            collection_id,
            add=add,
            remove=remove,
            created_at=_utc_now(),
            expected_head_snapshot_id=expected,
        )

    def search_collection(self, collection_id: str, query: str, limit: int = 20) -> dict[str, Any]:
        collection_id = _require_sha_ref(collection_id, "collection_id")
        query = _require_string(query, "query", maximum=32768)
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise WebUIError("limit must be 1..100")

        # Serialize the WebUI's exact-snapshot search against the same Collection
        # HEAD lock used by membership updates. Contention fails closed rather than
        # allowing results from one snapshot to be labelled as another.
        with self.store._exclusive_lock(f"collection-head:{collection_id}"):
            snapshot = self.store.get_collection_snapshot(collection_id)
            results = self.store.search_lexical(collection_id, query, limit=limit)
            result_snapshots = {row.get("snapshot_id") for row in results}
            if result_snapshots and result_snapshots != {snapshot["snapshot_id"]}:
                raise WebUIError("lexical search result snapshot does not match locked Collection HEAD")
            enriched = []
            for result in results:
                row = dict(result)
                row["file"] = self.store.get_file_record(result["file_id"])
                enriched.append(row)

        return {
            "collection_id": collection_id,
            "snapshot_id": snapshot["snapshot_id"],
            "results": enriched,
            "score_meaning": "retrieval_similarity_not_truth_or_evidence_strength",
        }

    def _list_run_ids(self) -> list[str]:
        root = self.control_root / "records" / "runs"
        if not root.exists():
            return []
        paths = sorted(root.glob("*.json"), key=lambda item: item.name.encode("ascii"))
        if len(paths) > MAX_LIST_ITEMS:
            raise WebUIError("run listing exceeds UI limit")
        return [
            f"sha256:{path.stem}"
            for path in paths
            if re.fullmatch(r"[0-9a-f]{64}", path.stem)
        ]

    def list_runs(self) -> list[dict[str, Any]]:
        output = []
        for run_id in self._list_run_ids():
            run = self.interactions.get_run(run_id)
            events = self.interactions.list_events(run_id)
            output.append(
                {
                    "run_id": run_id,
                    "created_at": run["created_at"],
                    "mode": run["mode"],
                    "question": run["question"]["text"],
                    "evidence_state": run["evidence_state"],
                    "collection_ref": run["collection_ref"],
                    "event_count": len(events),
                    "model_state_count": len(self.models.list_states(run_id=run_id)),
                    "replayability": run["replayability"],
                }
            )
        output.sort(key=lambda row: (row["created_at"], row["run_id"]), reverse=True)
        return output

    def run_detail(self, run_id: str) -> dict[str, Any]:
        run_id = _require_sha_ref(run_id, "run_id")
        run = self.interactions.get_run(run_id)
        events = self.interactions.list_events(run_id)
        model_states = self.models.list_states(run_id=run_id)
        collection = None
        collection_snapshot = None
        collection_files: list[dict[str, Any]] = []
        if run["collection_ref"] is not None:
            cref = run["collection_ref"]
            collection = self.store.get_collection(cref["collection_id"])
            collection_snapshot = self.store.get_collection_snapshot(
                cref["collection_id"], cref["snapshot_id"]
            )
            collection_files = [
                self.store.get_file_record(file_id)
                for file_id in collection_snapshot["members"]
            ]
        attached_files = [self.store.get_file_record(file_id) for file_id in run["file_ids"]]
        evidence_events = [event for event in events if event["kind"] == "evidence"]
        receipt_events = [event for event in events if event["kind"] == "receipt"]
        response_events = [event for event in events if event["kind"] == "response"]
        model_events = [event for event in events if event["kind"] == "model_state"]
        sources = self._sources_for_run(attached_files, collection_files, evidence_events)
        return {
            "protocol": WEBUI_RUN_VIEW_PROTOCOL,
            "run": run,
            "events": events,
            "evidence_events": evidence_events,
            "receipt_events": receipt_events,
            "response_events": response_events,
            "model_events": model_events,
            "model_states": model_states,
            "collection": collection,
            "collection_snapshot": collection_snapshot,
            "collection_files": collection_files,
            "attached_files": attached_files,
            "sources": sources,
            "lattice": self.lattice_view(run_id),
            "authority": "render-only",
        }

    @staticmethod
    def _sources_for_run(
        attached_files: list[dict[str, Any]],
        collection_files: list[dict[str, Any]],
        evidence_events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for record in attached_files + collection_files:
            key = "file:" + record["file_id"]
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "kind": "control-file",
                    "ref": record["file_id"],
                    "filename": record["filename"],
                    "source": record["source"],
                    "privacy_class": record["privacy_class"],
                    "authority": "stored-source-reference",
                }
            )
        for event in evidence_events:
            payload = event.get("payload", {})
            for ref in payload.get("evidence_refs", []) if isinstance(payload, dict) else []:
                if not isinstance(ref, dict):
                    continue
                ref_id = str(ref.get("event_id") or ref.get("event_hash") or "")
                if not ref_id:
                    continue
                key = "oracle:" + ref_id
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "kind": "oracle-observation",
                        "ref": ref_id,
                        "source": ref.get("source"),
                        "observed_at": ref.get("observed_at"),
                        "provenance_kind": ref.get("provenance_kind"),
                        "authority": ref.get("authority", "oracle-observation-reference"),
                    }
                )
        return rows
