from __future__ import annotations

import base64
from typing import Any

from webui.common import LATTICE_RE, MAX_UPLOAD_BYTES, WebUIConfig, _require_sha_ref
from webui.runtime import ControlWebUIRuntime

from .common import (
    AGENT_API_PROTOCOL,
    MAX_LATTICE_RECORDS,
    MAX_LATTICE_RUNS,
    MAX_MODEL_STATES,
    MAX_MUTATIONS_PER_CALLER,
    MAX_REQUESTS_PER_CALLER,
    OPERATIONS,
    Caller,
    AgentAPIError,
    require_int,
)


class ControlAgentAPIRuntime:
    """Thin Phase 6 machine facade over the same runtime used by the Human WebUI."""

    def __init__(self, config: WebUIConfig):
        self.config = config
        self.control = ControlWebUIRuntime(config)

    def capabilities(self) -> dict[str, Any]:
        session = self.control.session_contract()
        return {
            "protocol": "qsol-control-agent-capabilities/1",
            "agent_api_protocol": AGENT_API_PROTOCOL,
            "transport": "jsonl-stdio",
            "operations": list(OPERATIONS),
            "question_modes": ["evidence_only", "council"],
            "limits": {
                "max_requests_per_caller_per_process": MAX_REQUESTS_PER_CALLER,
                "max_mutations_per_caller_per_process": MAX_MUTATIONS_PER_CALLER,
                "max_upload_bytes": MAX_UPLOAD_BYTES,
                "max_model_states_per_response": MAX_MODEL_STATES,
                "max_lattice_records_per_response": MAX_LATTICE_RECORDS,
                "max_lattice_runs_per_trace": MAX_LATTICE_RUNS,
            },
            "parent_capabilities": session["capabilities"],
            "human_ai_epistemic_authority_equal": True,
            "oracle_write_operations": [],
            "nexus_arbitrary_operation_passthrough": False,
            "nexus_governance_overrides": False,
            "hidden_chain_of_thought_available": False,
            "truth_percentage_available": False,
            "phase7_replay_execution_implemented": False,
            "authority": "capability-discovery-only",
        }

    def health(self) -> dict[str, Any]:
        return {
            "protocol": "qsol-control-agent-health/1",
            "agent_api_protocol": AGENT_API_PROTOCOL,
            "transport": "jsonl-stdio",
            "services": self.control.health()["services"],
            "authority": "status-only",
        }

    def ask(self, caller: Caller, params: dict[str, Any]) -> dict[str, Any]:
        request = dict(params)
        request["requester_id"] = caller.caller_id
        return self.control.ask(request, requester_kind=caller.kind)

    def file_put(self, caller: Caller, params: dict[str, Any]) -> dict[str, Any]:
        return self.control.upload_file(
            params,
            requester_kind=caller.kind,
            source_locator=caller.caller_id,
        )

    def file_get(self, params: dict[str, Any]) -> dict[str, Any]:
        file_id = _require_sha_ref(params.get("file_id"), "file_id")
        allowed = {"file_id", "include_content"}
        if set(params) - allowed:
            raise AgentAPIError("INVALID_REQUEST", "control.file.get contains unknown fields")
        record = self.control.store.get_file_record(file_id)
        result: dict[str, Any] = {
            "protocol": "qsol-control-agent-file/1",
            "file": record,
            "raw_bytes_canonical": True,
            "authority": "storage-reference-only",
        }
        include_content = params.get("include_content", False)
        if type(include_content) is not bool:
            raise AgentAPIError("INVALID_REQUEST", "include_content must be boolean")
        if include_content:
            raw = self.control.store.read_file(file_id)
            if len(raw) > MAX_UPLOAD_BYTES:
                raise AgentAPIError("RESOURCE_LIMIT", "file content exceeds agent response limit")
            result["content_base64"] = base64.b64encode(raw).decode("ascii")
        return result

    def collection_create(self, caller: Caller, params: dict[str, Any]) -> dict[str, Any]:
        return self.control.create_collection(
            params,
            created_via=AGENT_API_PROTOCOL,
            requester_kind=caller.kind,
            requester_id=caller.caller_id,
        )

    def collection_snapshot(self, params: dict[str, Any]) -> dict[str, Any]:
        allowed = {"collection_id", "snapshot_id", "include_files"}
        if set(params) - allowed:
            raise AgentAPIError(
                "INVALID_REQUEST", "control.collection.snapshot contains unknown fields"
            )
        collection_id = _require_sha_ref(params.get("collection_id"), "collection_id")
        snapshot_id = params.get("snapshot_id")
        if snapshot_id is not None:
            snapshot_id = _require_sha_ref(snapshot_id, "snapshot_id")
        include_files = params.get("include_files", True)
        if type(include_files) is not bool:
            raise AgentAPIError("INVALID_REQUEST", "include_files must be boolean")
        collection = self.control.store.get_collection(collection_id)
        snapshot = self.control.store.get_collection_snapshot(collection_id, snapshot_id)
        result: dict[str, Any] = {
            "protocol": "qsol-control-agent-collection-snapshot/1",
            "collection": collection,
            "snapshot": snapshot,
            "membership_is_endorsement": False,
            "authority": "storage-only",
        }
        if include_files:
            result["files"] = [
                self.control.store.get_file_record(file_id) for file_id in snapshot["members"]
            ]
        return result

    def collection_search(self, params: dict[str, Any]) -> dict[str, Any]:
        allowed = {"collection_id", "query", "limit"}
        if set(params) - allowed:
            raise AgentAPIError(
                "INVALID_REQUEST", "control.collection.search contains unknown fields"
            )
        limit = params.get("limit", 20)
        if type(limit) is not int:
            raise AgentAPIError("INVALID_REQUEST", "limit must be an integer")
        return self.control.search_collection(
            params.get("collection_id"), params.get("query"), limit=limit
        )

    def run_get(self, params: dict[str, Any]) -> dict[str, Any]:
        if set(params) != {"run_id"}:
            raise AgentAPIError("INVALID_REQUEST", "control.run.get requires only run_id")
        return self.control.run_detail(params.get("run_id"))

    def run_compare(self, params: dict[str, Any]) -> dict[str, Any]:
        if set(params) != {"left_run_id", "right_run_id"}:
            raise AgentAPIError(
                "INVALID_REQUEST",
                "control.run.compare requires left_run_id and right_run_id",
            )
        return self.control.compare_runs(
            params.get("left_run_id"), params.get("right_run_id")
        )

    def evidence_get(self, params: dict[str, Any]) -> dict[str, Any]:
        if set(params) != {"run_id"}:
            raise AgentAPIError("INVALID_REQUEST", "control.evidence.get requires only run_id")
        view = self.control.run_detail(params.get("run_id"))
        return {
            "protocol": "qsol-control-agent-evidence-view/1",
            "run_id": view["run"]["run_id"],
            "evidence_state": view["run"]["evidence_state"],
            "oracle_refs": view["run"]["oracle_refs"],
            "evidence_events": view["evidence_events"],
            "sources": view["sources"],
            "vote_is_evidence": False,
            "suggested_search_is_evidence": False,
            "authority": "evidence-reference-view-only",
        }

    def council_get(self, params: dict[str, Any]) -> dict[str, Any]:
        if set(params) != {"run_id"}:
            raise AgentAPIError("INVALID_REQUEST", "control.council.get requires only run_id")
        view = self.control.run_detail(params.get("run_id"))
        events = view["events"]
        return {
            "protocol": "qsol-control-agent-council-view/1",
            "run_id": view["run"]["run_id"],
            "mode": view["run"]["mode"],
            "response_events": view["response_events"],
            "receipt_events": view["receipt_events"],
            "nexus_refs": self.control._nexus_refs_from_events(events),
            "consensus_is_truth": False,
            "vote_is_evidence": False,
            "hidden_chain_of_thought_available": False,
            "authority": "render-and-reference-only",
        }

    def models_get(self, params: dict[str, Any]) -> dict[str, Any]:
        allowed = {"run_id", "state_id", "limit"}
        if set(params) - allowed:
            raise AgentAPIError("INVALID_REQUEST", "control.models.get contains unknown fields")
        run_id = params.get("run_id")
        state_id = params.get("state_id")
        if run_id is not None and state_id is not None:
            raise AgentAPIError("INVALID_REQUEST", "run_id and state_id are mutually exclusive")
        if state_id is not None:
            return {
                "protocol": "qsol-control-agent-model-state-view/1",
                "state": self.control.model_state(state_id),
                "model_state_is_model_mind": False,
                "authority": "reproducibility-metadata-only",
            }
        limit = require_int(
            params.get("limit", 50), "limit", minimum=1, maximum=MAX_MODEL_STATES
        )
        states = self.control.list_model_states(run_id=run_id)
        return {
            "protocol": "qsol-control-agent-model-states/1",
            "states": states[:limit],
            "returned": min(len(states), limit),
            "total_observed": len(states),
            "truncated": len(states) > limit,
            "model_state_is_model_mind": False,
            "authority": "reproducibility-metadata-only",
        }

    def memory_get(self, params: dict[str, Any]) -> dict[str, Any]:
        allowed = {"run_id", "max_records"}
        if set(params) - allowed:
            raise AgentAPIError("INVALID_REQUEST", "control.memory.get contains unknown fields")
        run_id = params.get("run_id")
        max_records = require_int(
            params.get("max_records", 200),
            "max_records",
            minimum=1,
            maximum=MAX_LATTICE_RECORDS,
        )
        view = self.control.lattice_view(run_id=run_id)
        remaining = max_records
        cells = []
        total_records = 0
        for cell in view["cells"]:
            total_records += cell["count"]
            records = cell["records"][:remaining]
            remaining -= len(records)
            cells.append({**cell, "records": records, "count": len(records)})
        return {
            "protocol": "qsol-control-agent-lattice-view/1",
            "profile": view["profile"],
            "cells": cells,
            "total_records": total_records,
            "returned_records": max_records - remaining,
            "truncated": total_records > max_records,
            "geometry_is_truth": False,
            "authority": "navigation-and-storage-addressing-only",
        }

    def memory_trace(self, params: dict[str, Any]) -> dict[str, Any]:
        allowed = {"address_prefix", "run_id", "max_runs", "max_records"}
        if set(params) - allowed:
            raise AgentAPIError("INVALID_REQUEST", "control.memory.trace contains unknown fields")
        prefix = params.get("address_prefix")
        if not isinstance(prefix, str) or LATTICE_RE.fullmatch(prefix) is None:
            raise AgentAPIError("INVALID_REQUEST", "address_prefix is not a valid lattice address")
        run_id = params.get("run_id")
        max_runs = require_int(
            params.get("max_runs", 25), "max_runs", minimum=1, maximum=MAX_LATTICE_RUNS
        )
        max_records = require_int(
            params.get("max_records", 200),
            "max_records",
            minimum=1,
            maximum=MAX_LATTICE_RECORDS,
        )
        run_ids = [run_id] if run_id is not None else self.control._list_run_ids()
        if run_id is not None:
            _require_sha_ref(run_id, "run_id")
        selected_runs = run_ids[:max_runs]
        records: list[dict[str, Any]] = []
        matched_total = 0
        for current_run_id in selected_runs:
            run = self.control.interactions.get_run(current_run_id)
            question_address = run["question"]["lattice_address"]
            if question_address == prefix or question_address.startswith(prefix + "/"):
                matched_total += 1
                if len(records) < max_records:
                    records.append(
                        {
                            "kind": "run-question",
                            "run_id": current_run_id,
                            "address": question_address,
                            "question_sha256": run["question_sha256"],
                        }
                    )
            for event in self.control.interactions.list_events(current_run_id):
                address = event.get("lattice_address")
                if not isinstance(address, str):
                    continue
                if address == prefix or address.startswith(prefix + "/"):
                    matched_total += 1
                    if len(records) < max_records:
                        records.append(
                            {
                                "kind": event["kind"],
                                "run_id": current_run_id,
                                "event_id": event["event_id"],
                                "address": address,
                                "epistemic_role": event["epistemic_role"],
                                "temporal_role": event["temporal_role"],
                            }
                        )
        return {
            "protocol": "qsol-control-agent-lattice-trace/1",
            "profile": "qsol-3x3x3-sierpinski-derived-memory/1",
            "address_prefix": prefix,
            "runs_considered": len(selected_runs),
            "runs_truncated": len(run_ids) > len(selected_runs),
            "matched_records": matched_total,
            "records": records,
            "records_truncated": matched_total > len(records),
            "lattice_address_is_truth": False,
            "authority": "navigation-and-storage-addressing-only",
        }
