from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from adapters.nexus import NexusAdapterError, NexusCouncilAdapter
from storage.control_store import StorageError, canonical_json_bytes, sha256_ref
from storage.replay_store import (
    REPLAY_BASIS_PROTOCOL,
    REPLAY_LINK_PROTOCOL,
    REPLAY_RECORD_PROTOCOL,
    REPLAY_REPORT_PROTOCOL,
    RESEARCH_TIMELINE_PROTOCOL,
    ReplayError,
    ReplayStore,
)

from .common import (
    OBJECT_REF_RE,
    WebUIError,
    _canonical_strings,
    _require_sha_ref,
    _require_string,
    _utc_now,
)

REPLAY_CLASSIFICATION_PROTOCOL = "qsol-control-replay-classification/1"
MAX_TIMELINE_RUNS = 500
MAX_REPLAY_MODEL_STATES = 100
COUNCIL_PROTOCOL = "qsol-control-nexus-council-response/1"
COUNCIL_STATUS_PROTOCOL = "qsol-control-webui-council-status/1"
PRIVACY_CLASSES = {"PUBLIC", "INTERNAL", "RESTRICTED"}


class ReplayRuntimeMixin:
    @property
    def replays(self) -> ReplayStore:
        store = getattr(self, "_replay_store_instance", None)
        if store is None:
            store = ReplayStore(self.control_root)
            self._replay_store_instance = store
        return store

    @staticmethod
    def _roster_identity(rows: Any) -> list[dict[str, Any]]:
        """Render-only roster projection, not a complete execution-input identity."""
        if not isinstance(rows, (list, tuple)):
            return []
        output = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            member_id = row.get("member_id")
            model_id = row.get("model_id")
            if not isinstance(member_id, str) or not member_id:
                continue
            if member_id in seen:
                continue
            seen.add(member_id)
            output.append(
                {
                    "member_id": member_id,
                    "model_id": model_id if isinstance(model_id, str) else None,
                    "adapter_id": (
                        row.get("adapter_id")
                        if isinstance(row.get("adapter_id"), str)
                        else None
                    ),
                }
            )
        return output

    @staticmethod
    def _validated_member_descriptors(rows: Any) -> list[dict[str, Any]]:
        if not isinstance(rows, (list, tuple)):
            raise WebUIError("Council members must be a bounded object array")
        try:
            return NexusCouncilAdapter._validate_members(list(rows))
        except NexusAdapterError as exc:
            raise WebUIError(str(exc)) from exc

    def _preflight_replay_basis_request(
        self, request: dict[str, Any], *, mode: str
    ) -> None:
        """Validate every Phase-7 replay-basis input before any run is persisted."""
        max_age = request.get("oracle_max_age_seconds", 86400)
        if type(max_age) is not int or not 0 <= max_age <= 31_536_000:
            raise WebUIError("oracle_max_age_seconds must be 0..31536000")
        _canonical_strings(
            request.get("suggested_searches", []), "suggested_searches", maximum=32
        )
        if mode != "council":
            return

        supplied_members = request.get("members")
        if supplied_members is not None:
            self._validated_member_descriptors(supplied_members)
        elif self.config.default_council_members:
            self._validated_member_descriptors(self.config.default_council_members)

        refs = _canonical_strings(
            request.get("nexus_evidence_refs", []),
            "nexus_evidence_refs",
            maximum=10_000,
        )
        for ref in refs:
            if OBJECT_REF_RE.fullmatch(ref) is None:
                raise WebUIError("NEXUS admitted evidence refs must be object:<sha256>")
        _require_string(
            request.get("nexus_mode", "analytical"), "nexus_mode", maximum=128
        )
        privacy = request.get("privacy_class", "INTERNAL")
        if privacy not in PRIVACY_CLASSES:
            raise WebUIError("privacy_class must be PUBLIC, INTERNAL, or RESTRICTED")

    def _record_replay_basis(
        self,
        run: dict[str, Any],
        request: dict[str, Any],
        *,
        requester_kind: str,
    ) -> dict[str, Any]:
        collection_ref = copy.deepcopy(run.get("collection_ref"))
        current_head = None
        if isinstance(collection_ref, dict):
            current_head = self.store.get_collection(collection_ref["collection_id"])[
                "head_snapshot_id"
            ]

        member_descriptors: list[dict[str, Any]] = []
        roster_identity: list[dict[str, Any]] = []
        if run["mode"] == "council":
            requested = request.get("members")
            if requested is None:
                requested = [dict(item) for item in self.config.default_council_members]
            if requested:
                member_descriptors = self._validated_member_descriptors(requested)
                roster_identity = self._roster_identity(member_descriptors)

        suggestions = _canonical_strings(
            request.get("suggested_searches", []), "suggested_searches", maximum=32
        )
        nexus_refs = (
            _canonical_strings(
                request.get("nexus_evidence_refs", []),
                "nexus_evidence_refs",
                maximum=10_000,
            )
            if run["mode"] == "council"
            else []
        )

        payload = {
            "protocol": REPLAY_BASIS_PROTOCOL,
            "run_id": run["run_id"],
            "question_sha256": run["question_sha256"],
            "collection_ref": collection_ref,
            "collection_head_at_capture": current_head,
            "retrieval_index": {
                "status": "not_used",
                "index_id": None,
                "descriptor": None,
                "reason": "control.ask does not execute Collection search",
            },
            "request_configuration": {
                "mode": run["mode"],
                "oracle_max_age_seconds": request.get("oracle_max_age_seconds", 86400),
                "suggested_searches": suggestions,
                "nexus_mode": (
                    request.get("nexus_mode", "analytical")
                    if run["mode"] == "council"
                    else None
                ),
                "nexus_evidence_refs": nexus_refs,
                "council_roster_identity": roster_identity,
                "council_member_descriptors": member_descriptors,
                "council_member_descriptors_complete": run["mode"] != "council"
                or bool(member_descriptors)
                or self.config.nexus_command is None,
                "privacy_class": request.get("privacy_class", "INTERNAL"),
            },
            "requester_kind": requester_kind,
            "hidden_chain_of_thought_captured": False,
            "authority": "reproducibility-metadata-only",
        }
        refs: list[str] = []
        if isinstance(collection_ref, dict):
            refs = [collection_ref["collection_id"], collection_ref["snapshot_id"]]
        return self.interactions.append_event(
            run["run_id"],
            kind="receipt",
            payload=payload,
            occurred_at=_utc_now(),
            record_refs=refs,
        )

    def _basis_for_run(self, run_id: str) -> dict[str, Any]:
        events = self.interactions.list_events(run_id)
        matches = [
            event["payload"]
            for event in events
            if event.get("kind") == "receipt"
            and isinstance(event.get("payload"), dict)
            and event["payload"].get("protocol") == REPLAY_BASIS_PROTOCOL
        ]
        if len(matches) > 1:
            raise ReplayError("run contains multiple replay-basis receipts")
        if matches:
            basis = copy.deepcopy(matches[0])
            config = basis.setdefault("request_configuration", {})
            if "council_member_descriptors" not in config:
                config["council_member_descriptors"] = copy.deepcopy(
                    config.get("council_roster_identity", [])
                )
                config["council_member_descriptors_complete"] = False
            elif "council_member_descriptors_complete" not in config:
                config["council_member_descriptors_complete"] = False
            return basis
        run = self.interactions.get_run(run_id)
        return {
            "protocol": REPLAY_BASIS_PROTOCOL,
            "run_id": run_id,
            "question_sha256": run["question_sha256"],
            "collection_ref": copy.deepcopy(run.get("collection_ref")),
            "collection_head_at_capture": None,
            "retrieval_index": {
                "status": "not_recorded",
                "index_id": None,
                "descriptor": None,
                "reason": "legacy pre-Phase-7 run has no replay-basis receipt",
            },
            "request_configuration": {
                "mode": run["mode"],
                "oracle_max_age_seconds": None,
                "suggested_searches": [],
                "nexus_mode": None,
                "nexus_evidence_refs": [],
                "council_roster_identity": [],
                "council_member_descriptors": [],
                "council_member_descriptors_complete": False,
                "privacy_class": None,
            },
            "requester_kind": run["requester_kind"],
            "hidden_chain_of_thought_captured": False,
            "authority": "reproducibility-metadata-only",
            "legacy_inferred": True,
        }

    @staticmethod
    def _latest_payload(events: list[dict[str, Any]], kind: str) -> dict[str, Any] | None:
        for event in reversed(events):
            if event.get("kind") == kind and isinstance(event.get("payload"), dict):
                return event["payload"]
        return None

    @classmethod
    def _latest_council(cls, events: list[dict[str, Any]]) -> dict[str, Any] | None:
        for event in reversed(events):
            payload = event.get("payload")
            if event.get("kind") == "response" and isinstance(payload, dict):
                if payload.get("protocol") in {COUNCIL_PROTOCOL, COUNCIL_STATUS_PROTOCOL}:
                    return payload
        return None

    @staticmethod
    def _evidence_refs(payload: dict[str, Any] | None) -> list[str]:
        if not isinstance(payload, dict):
            return []
        refs: set[str] = set()
        for item in payload.get("evidence_refs", []):
            if isinstance(item, dict):
                value = item.get("event_id") or item.get("event_hash")
                if isinstance(value, str) and value:
                    refs.add(value)
        return sorted(refs, key=lambda value: value.encode("utf-8"))

    def _run_integrity(self, run_id: str) -> str:
        payload = {
            "run": self.interactions.get_run(run_id),
            "events": self.interactions.list_events(run_id),
            "model_states": self.models.list_states(run_id=run_id),
        }
        return sha256_ref(canonical_json_bytes(payload))

    @staticmethod
    def _model_row(state: dict[str, Any]) -> dict[str, Any]:
        model = state["model"]
        execution = state["execution"]
        return {
            "state_id": state["state_id"],
            "seat": execution.get("council_seat"),
            "provider": model.get("provider"),
            "runtime": model.get("runtime"),
            "runtime_version": model.get("runtime_version"),
            "model_id": model.get("model_id"),
            "revision": model.get("revision"),
            "quantization": model.get("quantization"),
            "stochastic": execution.get("stochastic"),
            "seed": execution.get("seed"),
            "sampling": copy.deepcopy(execution.get("sampling")),
        }

    @classmethod
    def _model_summary_from_states(cls, states: list[dict[str, Any]]) -> dict[str, Any]:
        rows = [cls._model_row(state) for state in states]
        rows.sort(
            key=lambda row: (
                str(row.get("seat") or "").encode("utf-8"),
                str(row.get("provider") or "").encode("utf-8"),
                str(row.get("model_id") or "").encode("utf-8"),
                str(row.get("revision") or "").encode("utf-8"),
                str(row.get("state_id") or "").encode("ascii"),
            )
        )
        normalized = [
            {key: copy.deepcopy(value) for key, value in row.items() if key != "state_id"}
            for row in rows
        ]
        return {
            "states": rows[:MAX_REPLAY_MODEL_STATES],
            "total": len(rows),
            "truncated": len(rows) > MAX_REPLAY_MODEL_STATES,
            "metadata_fingerprint": sha256_ref(canonical_json_bytes(normalized)),
            "stochastic_without_seed": any(
                row.get("stochastic") is True and row.get("seed") is None for row in rows
            ),
        }

    def _model_summary(self, run_id: str) -> dict[str, Any]:
        return self._model_summary_from_states(self.models.list_states(run_id=run_id))

    @staticmethod
    def _timestamp_instant(value: str) -> datetime:
        candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ReplayError("run created_at is not valid ISO-8601") from exc
        if parsed.tzinfo is None:
            raise ReplayError("run created_at must include an explicit UTC offset")
        return parsed.astimezone(timezone.utc)

    def replay_classify(self, run_id: str) -> dict[str, Any]:
        run_id = _require_sha_ref(run_id, "run_id")
        run = self.interactions.get_run(run_id)
        events = self.interactions.list_events(run_id)
        basis = self._basis_for_run(run_id)
        basis_config = basis.get("request_configuration", {})
        council = self._latest_council(events)
        original_roster = self._roster_identity(council.get("roster", [])) if council else []
        configured_descriptors = (
            self._validated_member_descriptors(self.config.default_council_members)
            if self.config.default_council_members
            else []
        )
        configured_roster = self._roster_identity(configured_descriptors)
        original_descriptors = basis_config.get("council_member_descriptors", [])
        descriptors_complete = bool(
            basis_config.get("council_member_descriptors_complete", False)
        )
        models = self._model_summary(run_id)

        collection_status = "not_applicable"
        current_head = None
        membership_drift = False
        snapshot_available = True
        if isinstance(run.get("collection_ref"), dict):
            ref = run["collection_ref"]
            try:
                original_snapshot = self.store.get_collection_snapshot(
                    ref["collection_id"], ref["snapshot_id"]
                )
                current = self.store.get_collection_snapshot(ref["collection_id"])
                current_head = current["snapshot_id"]
                membership_drift = current["members"] != original_snapshot["members"]
                collection_status = "available"
            except (StorageError, OSError):
                snapshot_available = False
                collection_status = "original_snapshot_unavailable"

        unavailable_file_ids: list[str] = []
        for file_id in run.get("file_ids", []):
            try:
                self.store.read_file(file_id)
            except (StorageError, OSError, ValueError):
                unavailable_file_ids.append(file_id)
        file_context_available = not unavailable_file_ids

        legacy_index_basis = basis.get("retrieval_index", {}).get("status") == "not_recorded"
        council_basis_incomplete = run["mode"] == "council" and not descriptors_complete
        basis_incomplete = legacy_index_basis or council_basis_incomplete
        nexus_configured = self.config.nexus_command is not None

        if run["mode"] == "council" and descriptors_complete:
            council_configuration_changed = original_descriptors != configured_descriptors
        elif run["mode"] == "council" and original_roster:
            # Historical Phase-7 records omitted accepted member fields. Treat
            # that uncertainty as changed configuration rather than assuming sameness.
            council_configuration_changed = True
        else:
            council_configuration_changed = False
        council_replayable = council.get("execution_replayable") if council else None

        if run["replayability"] == "R0":
            classification = "inspection_only"
            can_execute = False
        elif not snapshot_available or not file_context_available:
            classification = "unavailable_original_context"
            can_execute = False
        elif run["mode"] == "evidence_only":
            classification = (
                "legacy_current_evidence_rerun" if basis_incomplete else "current_evidence_rerun"
            )
            can_execute = True
        elif not nexus_configured:
            classification = "evidence_refresh_only"
            can_execute = False
        elif not configured_descriptors:
            classification = "council_configuration_unavailable"
            can_execute = False
        elif council_configuration_changed:
            classification = "changed_configuration_rerun"
            can_execute = True
        elif models["stochastic_without_seed"] or council_replayable is False:
            classification = "live_stochastic_rerun"
            can_execute = True
        elif basis_incomplete:
            classification = "legacy_declared_input_reexecution"
            can_execute = True
        else:
            classification = "declared_input_reexecution"
            can_execute = True

        payload = {
            "protocol": REPLAY_CLASSIFICATION_PROTOCOL,
            "original_run_id": run_id,
            "classification": classification,
            "can_execute": can_execute,
            "original_replayability": run["replayability"],
            "mode": run["mode"],
            "basis_status": "legacy_incomplete" if basis_incomplete else "recorded",
            "retrieval_index_status": basis.get("retrieval_index", {}).get("status"),
            "collection_status": collection_status,
            "original_collection_snapshot_id": (
                run.get("collection_ref", {}).get("snapshot_id")
                if isinstance(run.get("collection_ref"), dict)
                else None
            ),
            "current_collection_head_snapshot_id": current_head,
            "collection_membership_drift": membership_drift,
            "standalone_file_context_available": file_context_available,
            "unavailable_file_ids": unavailable_file_ids,
            "original_council_roster": original_roster,
            "configured_council_roster": configured_roster,
            "original_council_member_descriptors": copy.deepcopy(original_descriptors),
            "configured_council_member_descriptors": copy.deepcopy(configured_descriptors),
            "council_member_descriptors_complete": descriptors_complete,
            "council_roster_changed": council_configuration_changed,
            "council_execution_replayable": council_replayable,
            "model_states": models["states"],
            "model_state_total": models["total"],
            "model_states_truncated": models["truncated"],
            "model_state_metadata_fingerprint": models["metadata_fingerprint"],
            "stochastic_without_seed": models["stochastic_without_seed"],
            "current_evidence_is_original_evidence": False,
            "exact_replay_claimed": False,
            "hidden_chain_of_thought_required": False,
            "authority": "classification-only",
        }
        return {"classification_id": sha256_ref(canonical_json_bytes(payload)), **payload}

    @staticmethod
    def _mapping_diff(left: dict[str, Any], right: dict[str, Any]) -> list[dict[str, Any]]:
        changes = []
        for key in sorted(set(left) | set(right), key=lambda value: value.encode("utf-8")):
            if left.get(key) != right.get(key):
                changes.append(
                    {
                        "field": key,
                        "original": copy.deepcopy(left.get(key)),
                        "replay": copy.deepcopy(right.get(key)),
                    }
                )
        return changes

    @classmethod
    def _roster_diff(cls, left_rows: Any, right_rows: Any) -> dict[str, Any]:
        left = {row["member_id"]: row for row in cls._roster_identity(left_rows)}
        right = {row["member_id"]: row for row in cls._roster_identity(right_rows)}
        added = [right[key] for key in sorted(set(right) - set(left))]
        removed = [left[key] for key in sorted(set(left) - set(right))]
        changed = []
        for key in sorted(set(left) & set(right)):
            if left[key] != right[key]:
                changed.append(
                    {"member_id": key, "original": left[key], "replay": right[key]}
                )
        return {
            "added": added,
            "removed": removed,
            "changed": changed,
            "same": not (added or removed or changed),
        }

    def _collection_comparison(self, original_run: dict[str, Any]) -> dict[str, Any]:
        ref = original_run.get("collection_ref")
        if not isinstance(ref, dict):
            return {
                "applicable": False,
                "original_snapshot_id": None,
                "current_head_snapshot_id": None,
                "added_since_original": [],
                "removed_since_original": [],
                "replay_bound_to_original_snapshot": True,
            }
        original = self.store.get_collection_snapshot(ref["collection_id"], ref["snapshot_id"])
        current = self.store.get_collection_snapshot(ref["collection_id"])
        original_members = set(original["members"])
        current_members = set(current["members"])
        return {
            "applicable": True,
            "collection_id": ref["collection_id"],
            "original_snapshot_id": original["snapshot_id"],
            "current_head_snapshot_id": current["snapshot_id"],
            "added_since_original": sorted(current_members - original_members),
            "removed_since_original": sorted(original_members - current_members),
            "replay_bound_to_original_snapshot": True,
        }

    def _build_replay_report(
        self,
        *,
        original_run_id: str,
        replay_run_id: str,
        classification: dict[str, Any],
        original_fingerprint_before: str,
        original_fingerprint_after: str,
    ) -> dict[str, Any]:
        original_run = self.interactions.get_run(original_run_id)
        replay_run = self.interactions.get_run(replay_run_id)
        original_events = self.interactions.list_events(original_run_id)
        replay_events = self.interactions.list_events(replay_run_id)
        original_evidence = self._latest_payload(original_events, "evidence")
        replay_evidence = self._latest_payload(replay_events, "evidence")
        original_refs = set(self._evidence_refs(original_evidence))
        replay_refs = set(self._evidence_refs(replay_evidence))
        original_council = self._latest_council(original_events)
        replay_council = self._latest_council(replay_events)
        original_basis = self._basis_for_run(original_run_id)
        replay_basis = self._basis_for_run(replay_run_id)

        original_config = original_basis.get("request_configuration", {})
        replay_config = replay_basis.get("request_configuration", {})
        original_index = original_basis.get("retrieval_index", {})
        replay_index = replay_basis.get("retrieval_index", {})

        payload = {
            "protocol": REPLAY_REPORT_PROTOCOL,
            "original_run_id": original_run_id,
            "replay_run_id": replay_run_id,
            "classification_id": classification["classification_id"],
            "classification": classification["classification"],
            "original_result": {
                "immutable": original_fingerprint_before == original_fingerprint_after,
                "fingerprint_before": original_fingerprint_before,
                "fingerprint_after": original_fingerprint_after,
                "run_id_unchanged": original_run["run_id"] == original_run_id,
            },
            "evidence": {
                "original_state": original_run["evidence_state"],
                "current_replay_state": replay_run["evidence_state"],
                "added_refs": sorted(replay_refs - original_refs),
                "removed_refs": sorted(original_refs - replay_refs),
                "unchanged_refs": sorted(original_refs & replay_refs),
                "current_evidence_is_original_evidence": False,
            },
            "collection": self._collection_comparison(original_run),
            "retrieval_index": {
                "original": copy.deepcopy(original_index),
                "replay": copy.deepcopy(replay_index),
                "same_recorded_basis": original_index == replay_index,
                "legacy_original_basis_incomplete": original_index.get("status")
                == "not_recorded",
            },
            "council": {
                "roster": self._roster_diff(
                    original_council.get("roster", []) if original_council else [],
                    replay_council.get("roster", []) if replay_council else [],
                ),
                "request_member_descriptors": {
                    "original": copy.deepcopy(
                        original_config.get("council_member_descriptors", [])
                    ),
                    "replay": copy.deepcopy(
                        replay_config.get("council_member_descriptors", [])
                    ),
                    "original_complete": bool(
                        original_config.get("council_member_descriptors_complete", False)
                    ),
                    "replay_complete": bool(
                        replay_config.get("council_member_descriptors_complete", False)
                    ),
                },
                "original_runtime": {
                    "protocol": (
                        original_council.get("nexus_protocol") if original_council else None
                    ),
                    "version": (
                        original_council.get("nexus_runtime_version")
                        if original_council
                        else None
                    ),
                },
                "replay_runtime": {
                    "protocol": replay_council.get("nexus_protocol") if replay_council else None,
                    "version": (
                        replay_council.get("nexus_runtime_version")
                        if replay_council
                        else None
                    ),
                },
                "original_consensus": (
                    copy.deepcopy(original_council.get("consensus"))
                    if original_council
                    else None
                ),
                "replay_consensus": (
                    copy.deepcopy(replay_council.get("consensus"))
                    if replay_council
                    else None
                ),
                "consensus_is_truth": False,
            },
            "model_state": self.models.compare_runs(original_run_id, replay_run_id),
            "configuration": {
                "changes": self._mapping_diff(original_config, replay_config),
                "original": copy.deepcopy(original_config),
                "replay": copy.deepcopy(replay_config),
            },
            "run_fields": {
                "question_sha256_same": original_run["question_sha256"]
                == replay_run["question_sha256"],
                "mode_same": original_run["mode"] == replay_run["mode"],
                "file_ids_same": original_run["file_ids"] == replay_run["file_ids"],
                "collection_ref_same": original_run["collection_ref"]
                == replay_run["collection_ref"],
            },
            "comparison_is_truth": False,
            "model_state_comparison_is_mind_comparison": False,
            "authority": "comparison-only",
        }
        return payload

    def replay_execute(
        self,
        run_id: str,
        *,
        requester_kind: str = "human",
        allow_changed_configuration: bool = False,
    ) -> dict[str, Any]:
        run_id = _require_sha_ref(run_id, "run_id")
        if requester_kind not in {"human", "ai", "system"}:
            raise WebUIError("requester_kind must be human, ai, or system")
        classification = self.replay_classify(run_id)
        if not classification["can_execute"]:
            raise ReplayError(
                f"replay classification {classification['classification']} is not executable"
            )
        if classification["council_roster_changed"] and not allow_changed_configuration:
            raise ReplayError(
                "Council execution configuration changed or is incomplete; "
                "explicit allow_changed_configuration is required"
            )

        original = self.interactions.get_run(run_id)
        basis = self._basis_for_run(run_id)
        config = basis.get("request_configuration", {})
        request: dict[str, Any] = {
            "question": original["question"]["text"],
            "mode": original["mode"],
            "file_ids": list(original["file_ids"]),
        }
        if isinstance(original.get("collection_ref"), dict):
            request["collection_id"] = original["collection_ref"]["collection_id"]
            request["snapshot_id"] = original["collection_ref"]["snapshot_id"]
        max_age = config.get("oracle_max_age_seconds")
        if type(max_age) is int:
            request["oracle_max_age_seconds"] = max_age
        suggestions = config.get("suggested_searches")
        if isinstance(suggestions, list):
            request["suggested_searches"] = list(suggestions)

        if original["mode"] == "council":
            if self.config.nexus_command is None or not self.config.default_council_members:
                raise ReplayError("full Council replay requires configured NEXUS and Council members")
            request["members"] = [dict(item) for item in self.config.default_council_members]
            request["nexus_mode"] = config.get("nexus_mode") or "analytical"
            refs = config.get("nexus_evidence_refs")
            request["nexus_evidence_refs"] = list(refs) if isinstance(refs, list) else []
            privacy = config.get("privacy_class")
            if isinstance(privacy, str):
                request["privacy_class"] = privacy

        before = self._run_integrity(run_id)
        result = self.ask(request, requester_kind=requester_kind)
        replay_run_id = result["run_id"]
        after = self._run_integrity(run_id)
        if before != after:
            raise ReplayError("original run changed during replay execution")

        report_payload = self._build_replay_report(
            original_run_id=run_id,
            replay_run_id=replay_run_id,
            classification=classification,
            original_fingerprint_before=before,
            original_fingerprint_after=after,
        )
        report = self.replays.write_report(report_payload)
        replay_payload = {
            "protocol": REPLAY_RECORD_PROTOCOL,
            "original_run_id": run_id,
            "replay_run_id": replay_run_id,
            "report_id": report["report_id"],
            "executed_at": result["run_view"]["run"]["created_at"],
            "requested_by_kind": requester_kind,
            "classification": classification["classification"],
            "classification_id": classification["classification_id"],
            "changed_configuration_authorized": bool(allow_changed_configuration),
            "original_result_immutable": True,
            "exact_collection_snapshot_preserved": original["collection_ref"]
            == result["run_view"]["run"]["collection_ref"],
            "current_evidence_rerun": True,
            "exact_replay_claimed": False,
            "hidden_chain_of_thought_captured": False,
            "authority": "orchestration-and-comparison-only",
        }
        replay_record = self.replays.write_replay(replay_payload)
        self.interactions.append_event(
            replay_run_id,
            kind="receipt",
            payload={
                "protocol": REPLAY_LINK_PROTOCOL,
                "original_run_id": run_id,
                "report_id": report["report_id"],
                "classification": classification["classification"],
                "original_result_immutable": True,
                "authority": "lineage-reference-only",
            },
            occurred_at=_utc_now(),
            record_refs=[run_id, report["report_id"]],
        )
        return {
            "protocol": "qsol-control-replay-execution/1",
            "replay": replay_record,
            "report": report,
            "replay_run_view": self.run_detail(replay_run_id),
            "original_result_immutable": True,
            "authority": "orchestration-and-comparison-only",
        }

    def replay_get(self, replay_id: str) -> dict[str, Any]:
        replay_id = _require_sha_ref(replay_id, "replay_id")
        return self.replays.get_replay(replay_id)

    def research_timeline(self, run_id: str, *, limit: int = 100) -> dict[str, Any]:
        run_id = _require_sha_ref(run_id, "run_id")
        if type(limit) is not int or not 1 <= limit <= MAX_TIMELINE_RUNS:
            raise WebUIError(f"timeline limit must be 1..{MAX_TIMELINE_RUNS}")
        anchor = self.interactions.get_run(run_id)
        question_sha256 = anchor["question_sha256"]
        run_paths = sorted(
            (self.control_root / "records" / "runs").glob("*.json"),
            key=lambda path: path.name.encode("ascii"),
        )
        if len(run_paths) > 100_000:
            raise ReplayError("run registry exceeds longitudinal scan limit")

        matching: list[tuple[str, dict[str, Any]]] = []
        for path in run_paths:
            candidate_id = "sha256:" + path.stem
            run = self.interactions.get_run(candidate_id)
            if run["question_sha256"] == question_sha256:
                matching.append((candidate_id, run))
        matching.sort(
            key=lambda item: (self._timestamp_instant(item[1]["created_at"]), item[0])
        )
        total = len(matching)
        selected = matching[-limit:]
        selected_ids = {candidate_id for candidate_id, _ in selected}

        replay_records = self.replays.list_replays()
        replay_by_run = {row["replay_run_id"]: row for row in replay_records}
        children: dict[str, list[str]] = {}
        for row in replay_records:
            children.setdefault(row["original_run_id"], []).append(row["replay_run_id"])

        states_by_run: dict[str, list[dict[str, Any]]] = {value: [] for value in selected_ids}
        for state in self.models.list_states():
            state_run_id = state["system"]["control_run_id"]
            if state_run_id in states_by_run:
                states_by_run[state_run_id].append(state)

        rows = []
        for candidate_id, run in selected:
            events = self.interactions.list_events(candidate_id)
            evidence = self._latest_payload(events, "evidence") or {}
            council = self._latest_council(events)
            model_summary = self._model_summary_from_states(states_by_run[candidate_id])
            rows.append(
                {
                    "run_id": candidate_id,
                    "created_at": run["created_at"],
                    "mode": run["mode"],
                    "requester_kind": run["requester_kind"],
                    "evidence_state": run["evidence_state"],
                    "evidence_refs": self._evidence_refs(evidence),
                    "collection_ref": copy.deepcopy(run["collection_ref"]),
                    "council_roster": (
                        self._roster_identity(council.get("roster", [])) if council else []
                    ),
                    "council_disposition": (
                        council.get("consensus", {}).get("disposition") if council else None
                    ),
                    "nexus_runtime_version": (
                        council.get("nexus_runtime_version") if council else None
                    ),
                    "model_states": model_summary["states"],
                    "model_state_total": model_summary["total"],
                    "model_states_truncated": model_summary["truncated"],
                    "model_state_metadata_fingerprint": model_summary[
                        "metadata_fingerprint"
                    ],
                    "replay_of": replay_by_run.get(candidate_id, {}).get("original_run_id"),
                    "replay_children": sorted(children.get(candidate_id, [])),
                }
            )

        transitions = []
        for left, right in zip(rows, rows[1:]):
            left_refs = set(left["evidence_refs"])
            right_refs = set(right["evidence_refs"])
            transitions.append(
                {
                    "from_run_id": left["run_id"],
                    "to_run_id": right["run_id"],
                    "evidence_state_changed": left["evidence_state"]
                    != right["evidence_state"],
                    "evidence_refs_added": sorted(right_refs - left_refs),
                    "evidence_refs_removed": sorted(left_refs - right_refs),
                    "collection_snapshot_changed": left["collection_ref"]
                    != right["collection_ref"],
                    "council_roster": self._roster_diff(
                        left["council_roster"], right["council_roster"]
                    ),
                    "model_state_changed": left["model_state_metadata_fingerprint"]
                    != right["model_state_metadata_fingerprint"],
                    "runtime_changed": left["nexus_runtime_version"]
                    != right["nexus_runtime_version"],
                }
            )

        payload = {
            "protocol": RESEARCH_TIMELINE_PROTOCOL,
            "anchor_run_id": run_id,
            "question_sha256": question_sha256,
            "question": anchor["question"]["text"],
            "total_matching_runs": total,
            "returned_runs": len(rows),
            "truncated": total > len(rows),
            "runs": rows,
            "transitions": transitions,
            "timeline_is_truth": False,
            "authority": "longitudinal-comparison-only",
        }
        return {"timeline_id": sha256_ref(canonical_json_bytes(payload)), **payload}


__all__ = [
    "MAX_REPLAY_MODEL_STATES",
    "MAX_TIMELINE_RUNS",
    "REPLAY_CLASSIFICATION_PROTOCOL",
    "ReplayRuntimeMixin",
]
