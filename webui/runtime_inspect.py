from __future__ import annotations

from typing import Any

from storage.dna_lattice import (
    LEXICOGRAPHIC_TRAVERSAL,
    PHI_GATED_TRAVERSAL,
    encode_projection,
    lexicographic_cells,
)

from .common import (
    LATTICE_RE,
    MAX_DNA_EXPORT_BYTES,
    OBJECT_REF_RE,
    WEBUI_LATTICE_PROTOCOL,
    WEBUI_RUN_COMPARISON_PROTOCOL,
    WebUIError,
    _require_sha_ref,
    _require_string,
)


class InspectRuntimeMixin:
    def list_model_states(self, run_id: str | None = None) -> list[dict[str, Any]]:
        if run_id is not None:
            run_id = _require_sha_ref(run_id, "run_id")
        return self.models.list_states(run_id=run_id)

    def model_state(self, state_id: str) -> dict[str, Any]:
        return self.models.get_state(_require_sha_ref(state_id, "state_id"))

    def compare_model_states(self, left: str, right: str) -> dict[str, Any]:
        return self.models.compare_states(
            _require_sha_ref(left, "left_state_id"),
            _require_sha_ref(right, "right_state_id"),
        )

    def lattice_view(self, run_id: str | None = None) -> dict[str, Any]:
        cells = {
            cell: {"address": cell, "records": [], "count": 0}
            for cell in lexicographic_cells()
        }
        run_ids = [run_id] if run_id else self._list_run_ids()
        for current_run_id in run_ids:
            current_run_id = _require_sha_ref(current_run_id, "run_id")
            run = self.interactions.get_run(current_run_id)
            for address in run.get("lattice_refs", []):
                if address in cells:
                    cells[address]["records"].append(
                        {
                            "kind": "run-question",
                            "run_id": current_run_id,
                            "question": run["question"]["text"],
                        }
                    )
            for event in self.interactions.list_events(current_run_id):
                address = event.get("lattice_address")
                if isinstance(address, str) and LATTICE_RE.fullmatch(address):
                    top = address.split("/", 1)[0]
                    if top in cells:
                        cells[top]["records"].append(
                            {
                                "kind": event["kind"],
                                "run_id": current_run_id,
                                "event_id": event["event_id"],
                                "address": address,
                                "epistemic_role": event["epistemic_role"],
                                "temporal_role": event["temporal_role"],
                            }
                        )
        for cell in cells.values():
            cell["count"] = len(cell["records"])
        return {
            "protocol": WEBUI_LATTICE_PROTOCOL,
            "profile": "qsol-3x3x3-sierpinski-derived-memory/1",
            "cells": [cells[cell] for cell in lexicographic_cells()],
            "geometry_is_truth": False,
            "authority": "navigation-and-storage-addressing-only",
        }

    def dna_inspect(self, request: dict[str, Any]) -> dict[str, Any]:
        file_id = _require_sha_ref(request.get("file_id"), "file_id")
        traversal = request.get("traversal_id", PHI_GATED_TRAVERSAL)
        if traversal not in {LEXICOGRAPHIC_TRAVERSAL, PHI_GATED_TRAVERSAL}:
            raise WebUIError("unknown DNA traversal")
        record = self.store.get_file_record(file_id)
        raw = self.store.read_file(file_id)
        if len(raw) > MAX_DNA_EXPORT_BYTES:
            raise WebUIError(f"DNA projection exceeds {MAX_DNA_EXPORT_BYTES} input bytes")
        projection = encode_projection(raw, traversal_id=traversal)
        cell_summary = [
            {
                "address": address,
                "base_count": len(projection["cells"][address]),
                "codon_count": len(projection["cells"][address]) // 3,
            }
            for address in lexicographic_cells()
        ]
        return {
            "protocol": "qsol-control-webui-dna-inspection/1",
            "file_id": file_id,
            "privacy_class": record["privacy_class"],
            "projection_id": projection["projection_id"],
            "content_sha256": projection["content_sha256"],
            "byte_length": projection["byte_length"],
            "codon_count": projection["codon_count"],
            "traversal_id": projection["traversal_id"],
            "traversal_parameters": projection["traversal_parameters"],
            "cells": cell_summary,
            "codon_histogram": projection["codon_histogram"],
            "derived": True,
            "rebuildable": True,
            "authority": "none",
            "codon_frequency_is_evidence": False,
        }

    def dna_export(self, request: dict[str, Any]) -> dict[str, Any]:
        file_id = _require_sha_ref(request.get("file_id"), "file_id")
        traversal = request.get("traversal_id", PHI_GATED_TRAVERSAL)
        if traversal not in {LEXICOGRAPHIC_TRAVERSAL, PHI_GATED_TRAVERSAL}:
            raise WebUIError("unknown DNA traversal")
        record = self.store.get_file_record(file_id)
        restricted = record["privacy_class"] == "RESTRICTED"
        actor_value = request.get("actor")
        actor = (
            _require_string(actor_value, "actor", maximum=256)
            if actor_value is not None
            else None
        )
        if restricted and request.get("allow_restricted") is not True:
            raise WebUIError("RESTRICTED DNA export requires explicit allow_restricted")
        if restricted and request.get("acknowledge_reversible_sensitive_export") is not True:
            raise WebUIError(
                "RESTRICTED DNA export requires reversible-sensitive-export acknowledgement"
            )
        if restricted and actor is None:
            raise WebUIError("RESTRICTED DNA export requires explicit actor attribution")
        raw = self.store.read_file(file_id)
        if len(raw) > MAX_DNA_EXPORT_BYTES:
            raise WebUIError(f"DNA projection exceeds {MAX_DNA_EXPORT_BYTES} input bytes")
        projection = encode_projection(raw, traversal_id=traversal)
        self.store.record_audit_event(
            "webui-dna-export",
            actor=actor or "webui-local-operator",
            details={
                "file_id": file_id,
                "privacy_class": record["privacy_class"],
                "projection_id": projection["projection_id"],
                "traversal_id": traversal,
                "restricted_authorized": restricted,
                "reversible_sensitive_export_acknowledged": bool(
                    request.get("acknowledge_reversible_sensitive_export")
                ),
            },
        )
        return projection

    @staticmethod
    def _nexus_refs_from_events(events: list[dict[str, Any]]) -> list[str]:
        refs: set[str] = set()
        keys = (
            "session_ref",
            "receipt_ref",
            "epoch_admission_receipt_ref",
            "nexus_session_ref",
            "nexus_receipt_ref",
        )
        for event in events:
            if event.get("kind") not in {"receipt", "response"}:
                continue
            payload = event.get("payload")
            if isinstance(payload, dict):
                for key in keys:
                    value = payload.get(key)
                    if isinstance(value, str) and OBJECT_REF_RE.fullmatch(value):
                        refs.add(value)
            for value in event.get("record_refs", []):
                if isinstance(value, str) and OBJECT_REF_RE.fullmatch(value):
                    refs.add(value)
        return sorted(refs, key=lambda value: value.encode("ascii"))

    def compare_runs(self, left_run_id: str, right_run_id: str) -> dict[str, Any]:
        left_run_id = _require_sha_ref(left_run_id, "left_run_id")
        right_run_id = _require_sha_ref(right_run_id, "right_run_id")
        left = self.interactions.get_run(left_run_id)
        right = self.interactions.get_run(right_run_id)
        left_events = self.interactions.list_events(left_run_id)
        right_events = self.interactions.list_events(right_run_id)
        model_comparison = self.models.compare_runs(left_run_id, right_run_id)

        fields = (
            "question_sha256",
            "mode",
            "evidence_state",
            "oracle_refs",
            "file_ids",
            "collection_ref",
            "replayability",
        )
        changed = [
            {"field": field, "left": left.get(field), "right": right.get(field)}
            for field in fields
            if left.get(field) != right.get(field)
        ]
        left_nexus_refs = self._nexus_refs_from_events(left_events)
        right_nexus_refs = self._nexus_refs_from_events(right_events)
        if left_nexus_refs != right_nexus_refs:
            changed.append(
                {
                    "field": "nexus_event_refs",
                    "left": left_nexus_refs,
                    "right": right_nexus_refs,
                }
            )
        return {
            "protocol": WEBUI_RUN_COMPARISON_PROTOCOL,
            "left_run_id": left_run_id,
            "right_run_id": right_run_id,
            "changed_run_fields": changed,
            "left_nexus_refs": left_nexus_refs,
            "right_nexus_refs": right_nexus_refs,
            "left_event_ids": [event["event_id"] for event in left_events],
            "right_event_ids": [event["event_id"] for event in right_events],
            "model_state_comparison": model_comparison,
            "phase7_replay_execution_implemented": True,
            "comparison_is_replay_execution": False,
            "authority": "comparison-only",
        }
