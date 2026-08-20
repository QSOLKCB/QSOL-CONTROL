from __future__ import annotations

from typing import Any

from adapters.nexus import NexusAdapterError, NexusCouncilAdapter
from adapters.oracle import OracleAdapter, OracleAdapterError
from storage.control_store import StorageError

from .common import (
    OBJECT_REF_RE,
    WebUIError,
    _canonical_strings,
    _require_sha_ref,
    _require_string,
    _reject_truth_fields,
    _utc_now,
)

COUNCIL_STATUS_PROTOCOL = "qsol-control-webui-council-status/1"
MAX_QUESTION_CHARACTERS = 2048


class QueryRuntimeMixin:
    def ask(
        self,
        request: dict[str, Any],
        *,
        requester_kind: str = "human",
    ) -> dict[str, Any]:
        _reject_truth_fields(request)
        if requester_kind not in {"human", "ai", "system"}:
            raise WebUIError("requester_kind must be human, ai, or system")
        question = _require_string(
            request.get("question"), "question", maximum=MAX_QUESTION_CHARACTERS
        )
        mode = request.get("mode")
        if mode not in {"evidence_only", "council"}:
            raise WebUIError("mode must be evidence_only or council")
        file_ids = _canonical_strings(request.get("file_ids", []), "file_ids")
        for file_id in file_ids:
            self.store.get_file_record(_require_sha_ref(file_id, "file_id"))

        collection_id = request.get("collection_id")
        snapshot_id = request.get("snapshot_id")
        if collection_id is not None:
            collection_id = _require_sha_ref(collection_id, "collection_id")
            if snapshot_id is None:
                snapshot_id = self.store.get_collection_snapshot(collection_id)["snapshot_id"]
            else:
                snapshot_id = _require_sha_ref(snapshot_id, "snapshot_id")
                self.store.get_collection_snapshot(collection_id, snapshot_id)
        elif snapshot_id is not None:
            raise WebUIError("snapshot_id requires collection_id")

        oracle_response = self._query_oracle(question, request)
        evidence_state = "unknown"
        oracle_refs: list[str] = []
        if oracle_response.get("availability") == "available":
            evidence_state = oracle_response.get("state", "unknown")
            evidence_refs = oracle_response.get("evidence_refs", [])
            oracle_refs = sorted(
                {
                    str(item.get("event_id"))
                    for item in evidence_refs
                    if isinstance(item, dict) and item.get("event_id")
                },
                key=lambda value: value.encode("utf-8"),
            )
            if evidence_state != "unknown" and not oracle_refs:
                evidence_state = "unknown"

        run = self.interactions.create_run(
            question=question,
            mode=mode,
            requester_kind=requester_kind,
            created_at=_utc_now(),
            evidence_state=evidence_state,
            file_ids=file_ids,
            collection_id=collection_id,
            snapshot_id=snapshot_id,
            oracle_refs=oracle_refs,
            replayability="R3",
        )
        self._record_replay_basis(run, request, requester_kind=requester_kind)

        epistemic_role = (
            "observed"
            if oracle_response.get("availability") == "available"
            and oracle_response.get("state") in {"known", "conflict"}
            else "unresolved"
        )
        record_refs = sorted(
            {
                str(item.get("event_id"))
                for item in oracle_response.get("evidence_refs", [])
                if isinstance(item, dict) and item.get("event_id")
            },
            key=lambda value: value.encode("utf-8"),
        )
        evidence_event = self.interactions.append_event(
            run["run_id"],
            kind="evidence",
            payload=oracle_response,
            occurred_at=_utc_now(),
            epistemic_role=epistemic_role,
            temporal_role="current",
            record_refs=record_refs,
        )

        council_response = None
        if mode == "council":
            council_response = self._run_council(
                question=question,
                request=request,
                run=run,
                oracle_response=oracle_response,
            )
            if council_response.get("availability") != "available":
                self.interactions.append_event(
                    run["run_id"],
                    kind="response",
                    payload=council_response,
                    occurred_at=_utc_now(),
                    epistemic_role="unresolved",
                    temporal_role="current",
                    parent_event_ids=[evidence_event["event_id"]],
                )

        return {
            "protocol": "qsol-control-webui-ask-response/1",
            "run_id": run["run_id"],
            "mode": mode,
            "oracle": oracle_response,
            "council": council_response,
            "run_view": self.run_detail(run["run_id"]),
            "truth_percentage_available": False,
            "authority": "orchestration-and-render-only",
        }

    def _query_oracle(self, question: str, request: dict[str, Any]) -> dict[str, Any]:
        if self.config.oracle_root is None:
            return {
                "availability": "unconfigured",
                "state": "unknown",
                "evidence_refs": [],
                "missing_evidence": ["ORACLE is not configured for this WebUI process."],
                "suggested_searches": [],
                "search_suggestions_are_evidence": False,
                "authority": "none",
            }
        max_age = request.get("oracle_max_age_seconds", 86400)
        if not isinstance(max_age, int) or not 0 <= max_age <= 31_536_000:
            raise WebUIError("oracle_max_age_seconds must be 0..31536000")
        suggestions = _canonical_strings(
            request.get("suggested_searches", []), "suggested_searches", maximum=32
        )
        try:
            return OracleAdapter(self.config.oracle_root).query_evidence(
                question,
                evaluated_at=_utc_now(),
                max_age_seconds=max_age,
                suggested_searches=suggestions,
            )
        except (OracleAdapterError, StorageError, OSError, ValueError) as exc:
            return {
                "availability": "unavailable",
                "state": "unknown",
                "evidence_refs": [],
                "missing_evidence": [str(exc)],
                "suggested_searches": suggestions,
                "search_suggestions_are_evidence": False,
                "authority": "none",
            }

    def _nexus_adapter(self) -> NexusCouncilAdapter:
        if self.config.nexus_command is None:
            raise WebUIError("NEXUS is not configured")
        return NexusCouncilAdapter.from_command(
            list(self.config.nexus_command),
            cwd=str(self.config.nexus_cwd) if self.config.nexus_cwd else None,
            timeout_seconds=self.config.nexus_timeout_seconds,
        )

    def _run_council(
        self,
        *,
        question: str,
        request: dict[str, Any],
        run: dict[str, Any],
        oracle_response: dict[str, Any],
    ) -> dict[str, Any]:
        if self.config.nexus_command is None:
            return {
                "protocol": COUNCIL_STATUS_PROTOCOL,
                "availability": "unconfigured",
                "authority": "none",
                "hidden_chain_of_thought_captured": False,
            }
        members = request.get("members")
        if members is None:
            members = [dict(item) for item in self.config.default_council_members]
        if not isinstance(members, list) or not members:
            raise WebUIError(
                "Ask Council requires member descriptors or --nexus-members"
            )
        if len(members) > 64 or any(not isinstance(item, dict) for item in members):
            raise WebUIError("Council members must be a bounded object array")
        evidence_refs = request.get("nexus_evidence_refs", [])
        if not isinstance(evidence_refs, list) or len(evidence_refs) > 10_000:
            raise WebUIError("nexus_evidence_refs must be a bounded array")
        if len(evidence_refs) != len(set(evidence_refs)):
            raise WebUIError("nexus_evidence_refs must not contain duplicates")
        for ref in evidence_refs:
            if not isinstance(ref, str) or OBJECT_REF_RE.fullmatch(ref) is None:
                raise WebUIError("NEXUS admitted evidence refs must be object:<sha256>")
        nexus_mode = _require_string(
            request.get("nexus_mode", "analytical"), "nexus_mode", maximum=256
        )
        evidence_state = (
            oracle_response.get("state")
            if oracle_response.get("availability") == "available"
            else "unknown"
        )
        try:
            with self._nexus_adapter() as adapter:
                return adapter.run_council(
                    question=question,
                    members=members,
                    evidence_refs=evidence_refs,
                    evidence_state=evidence_state,
                    mode=nexus_mode,
                    control_root=self.control_root,
                    control_run_id=run["run_id"],
                    created_at=_utc_now(),
                    privacy_class=request.get("privacy_class", "INTERNAL"),
                )
        except (NexusAdapterError, StorageError, OSError, ValueError) as exc:
            return {
                "protocol": COUNCIL_STATUS_PROTOCOL,
                "availability": "unavailable",
                "error": str(exc),
                "authority": "none",
                "hidden_chain_of_thought_captured": False,
            }
