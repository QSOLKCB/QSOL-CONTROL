from __future__ import annotations

from typing import Any

from adapters.nexus import (
    NexusAdapterError,
    NexusCouncilAdapter,
    _reject_obvious_secrets,
)
from adapters.oracle import OracleAdapterError
from storage.control_store import StorageError
from storage.dna_lattice import DnaLatticeError
from storage.model_state import ModelStateError
from storage.replay_store import ReplayError
from webui.common import (
    WebUIConfig,
    WebUIError,
    _canonical_strings,
    _require_sha_ref,
)

from .common import (
    MAX_MUTATIONS_PER_CALLER,
    MAX_MUTATIONS_PER_PROCESS,
    MAX_REQUESTS_PER_CALLER,
    MAX_REQUESTS_PER_PROCESS,
    MUTATION_OPERATIONS,
    REQUEST_ID_RE,
    AgentAPIError,
    Caller,
    QuotaState,
    error_envelope,
    success_envelope,
    validate_request_envelope,
)
from .runtime import ControlAgentAPIRuntime

ASK_BASE_PARAMS = {
    "question",
    "mode",
    "file_ids",
    "collection_id",
    "snapshot_id",
    "oracle_max_age_seconds",
    "suggested_searches",
}
ASK_COUNCIL_PARAMS = {
    "members",
    "nexus_evidence_refs",
    "nexus_mode",
    "privacy_class",
}
PRIVACY_CLASSES = {"PUBLIC", "INTERNAL", "RESTRICTED"}


class AgentAPIDispatcher:
    def __init__(self, config: WebUIConfig):
        self.runtime = ControlAgentAPIRuntime(config)
        self._quota: dict[str, QuotaState] = {}
        self._process_quota = QuotaState()

    def _charge(self, caller: Caller, operation: str) -> None:
        state = self._quota.setdefault(caller.quota_key, QuotaState())
        is_mutation = operation in MUTATION_OPERATIONS

        if self._process_quota.requests >= MAX_REQUESTS_PER_PROCESS:
            raise AgentAPIError(
                "QUOTA_EXCEEDED",
                "agent API process request quota exceeded",
                details={"limit": MAX_REQUESTS_PER_PROCESS, "kind": "process_requests"},
            )
        if is_mutation and self._process_quota.mutations >= MAX_MUTATIONS_PER_PROCESS:
            raise AgentAPIError(
                "QUOTA_EXCEEDED",
                "agent API process mutation quota exceeded",
                details={"limit": MAX_MUTATIONS_PER_PROCESS, "kind": "process_mutations"},
            )
        if state.requests >= MAX_REQUESTS_PER_CALLER:
            raise AgentAPIError(
                "QUOTA_EXCEEDED",
                "caller request quota exceeded for this agent API process",
                details={"limit": MAX_REQUESTS_PER_CALLER, "kind": "caller_requests"},
            )
        if is_mutation and state.mutations >= MAX_MUTATIONS_PER_CALLER:
            raise AgentAPIError(
                "QUOTA_EXCEEDED",
                "caller mutation quota exceeded for this agent API process",
                details={"limit": MAX_MUTATIONS_PER_CALLER, "kind": "caller_mutations"},
            )

        self._process_quota.requests += 1
        state.requests += 1
        if is_mutation:
            self._process_quota.mutations += 1
            state.mutations += 1

    @staticmethod
    def _require_empty_params(operation: str, params: dict[str, Any]) -> None:
        if params:
            raise AgentAPIError(
                "INVALID_REQUEST", f"{operation} does not accept parameters"
            )

    @staticmethod
    def _require_api_sha_ref(value: Any, field: str) -> str:
        try:
            return _require_sha_ref(value, field)
        except WebUIError as exc:
            raise AgentAPIError("INVALID_REQUEST", str(exc)) from exc

    def _preflight_ask(self, params: dict[str, Any]) -> None:
        mode = params.get("mode")
        allowed = ASK_BASE_PARAMS | (ASK_COUNCIL_PARAMS if mode == "council" else set())
        unknown = sorted(set(params) - allowed)
        if unknown:
            raise AgentAPIError(
                "INVALID_REQUEST",
                "control.ask contains fields that are unsupported for the selected mode",
                details={"fields": unknown},
            )

        if mode != "council":
            return

        privacy_class = params.get("privacy_class", "INTERNAL")
        if privacy_class not in PRIVACY_CLASSES:
            raise AgentAPIError(
                "INVALID_REQUEST",
                "privacy_class must be PUBLIC, INTERNAL, or RESTRICTED",
            )

        configured = self.runtime.config.nexus_command is not None
        supplied_members = params.get("members")
        if supplied_members is not None and not isinstance(supplied_members, list):
            raise AgentAPIError("INVALID_REQUEST", "members must be an array")
        if supplied_members is None:
            members = list(self.runtime.config.default_council_members)
        else:
            members = supplied_members

        evidence_refs = params.get("nexus_evidence_refs", [])
        if not isinstance(evidence_refs, list):
            raise AgentAPIError(
                "INVALID_REQUEST", "nexus_evidence_refs must be an array"
            )
        nexus_mode = params.get("nexus_mode", "analytical")

        try:
            NexusCouncilAdapter._validate_question(params.get("question"))
            if configured or supplied_members is not None:
                validated_members = NexusCouncilAdapter._validate_members(members)
            else:
                validated_members = []
            validated_evidence = NexusCouncilAdapter._validate_evidence_refs(evidence_refs)
            if not isinstance(nexus_mode, str) or not nexus_mode or len(nexus_mode) > 128:
                raise NexusAdapterError("mode must be bounded non-empty text")
            _reject_obvious_secrets(
                {
                    "question": params.get("question"),
                    "members": validated_members,
                    "evidence_refs": validated_evidence,
                    "mode": nexus_mode,
                },
                "NEXUS Council request",
            )
        except NexusAdapterError as exc:
            raise AgentAPIError("INVALID_REQUEST", str(exc)) from exc

    def _preflight_replay(self, operation: str, params: dict[str, Any]) -> None:
        if operation == "control.replay.classify":
            if set(params) != {"run_id"}:
                raise AgentAPIError(
                    "INVALID_REQUEST", "control.replay.classify requires only run_id"
                )
            self._require_api_sha_ref(params.get("run_id"), "run_id")
        elif operation == "control.replay.execute":
            allowed = {"run_id", "allow_changed_configuration"}
            if set(params) - allowed or "run_id" not in params:
                raise AgentAPIError(
                    "INVALID_REQUEST",
                    "control.replay.execute requires run_id and optional allow_changed_configuration",
                )
            self._require_api_sha_ref(params.get("run_id"), "run_id")
            flag = params.get("allow_changed_configuration", False)
            if type(flag) is not bool:
                raise AgentAPIError(
                    "INVALID_REQUEST", "allow_changed_configuration must be boolean"
                )
        elif operation == "control.replay.get":
            if set(params) != {"replay_id"}:
                raise AgentAPIError(
                    "INVALID_REQUEST", "control.replay.get requires only replay_id"
                )
            self._require_api_sha_ref(params.get("replay_id"), "replay_id")
        elif operation == "control.research.timeline":
            allowed = {"run_id", "limit"}
            if set(params) - allowed or "run_id" not in params:
                raise AgentAPIError(
                    "INVALID_REQUEST",
                    "control.research.timeline requires run_id and optional limit",
                )
            self._require_api_sha_ref(params.get("run_id"), "run_id")
            limit = params.get("limit", 100)
            if type(limit) is not int or not 1 <= limit <= 500:
                raise AgentAPIError("INVALID_REQUEST", "timeline limit must be 1..500")

    def _preflight_operation(self, operation: str, params: dict[str, Any]) -> None:
        if operation in {"control.health", "control.capabilities"}:
            self._require_empty_params(operation, params)
        if operation == "control.ask":
            self._preflight_ask(params)
        if operation in {"control.memory.get", "control.memory.trace"}:
            run_id = params.get("run_id")
            if run_id is not None:
                self._require_api_sha_ref(run_id, "run_id")
        if operation.startswith("control.replay.") or operation == "control.research.timeline":
            self._preflight_replay(operation, params)

    def _create_collection(
        self, caller: Caller, params: dict[str, Any]
    ) -> dict[str, Any]:
        request = dict(params)
        file_ids = _canonical_strings(request.pop("file_ids", []), "file_ids")
        for file_id in file_ids:
            canonical = _require_sha_ref(file_id, "file_id")
            self.runtime.control.store.get_file_record(canonical)

        collection = self.runtime.collection_create(caller, request)
        collection_id = collection["collection_id"]
        current = self.runtime.control.store.get_collection_snapshot(collection_id)
        if file_ids:
            snapshot = self.runtime.control.update_collection(
                collection_id,
                {
                    "add": file_ids,
                    "remove": [],
                    "expected_head_snapshot_id": current["snapshot_id"],
                },
            )
        else:
            snapshot = current
        return {
            "protocol": "qsol-control-agent-collection-create/1",
            "collection": collection,
            "snapshot": snapshot,
            "membership_is_endorsement": False,
            "authority": "storage-only",
        }

    def _capabilities(self) -> dict[str, Any]:
        result = self.runtime.capabilities()
        limits = dict(result["limits"])
        limits.update(
            {
                "max_requests_per_process": MAX_REQUESTS_PER_PROCESS,
                "max_mutations_per_process": MAX_MUTATIONS_PER_PROCESS,
                "caller_id_is_trusted_quota_identity": False,
                "max_research_timeline_runs": 500,
            }
        )
        return {
            **result,
            "limits": limits,
            "phase7_replay_execution_implemented": True,
            "replay_exactness_policy": "classify_before_execute_never_claim_exact_without_basis",
        }

    def _dispatch(
        self, caller: Caller, operation: str, params: dict[str, Any]
    ) -> Any:
        self._preflight_operation(operation, params)
        handlers = {
            "control.health": lambda: self.runtime.health(),
            "control.capabilities": self._capabilities,
            "control.ask": lambda: self.runtime.ask(caller, params),
            "control.file.put": lambda: self.runtime.file_put(caller, params),
            "control.file.get": lambda: self.runtime.file_get(params),
            "control.collection.create": lambda: self._create_collection(caller, params),
            "control.collection.snapshot": lambda: self.runtime.collection_snapshot(params),
            "control.collection.search": lambda: self.runtime.collection_search(params),
            "control.run.get": lambda: self.runtime.run_get(params),
            "control.run.compare": lambda: self.runtime.run_compare(params),
            "control.replay.classify": lambda: self.runtime.control.replay_classify(params["run_id"]),
            "control.replay.execute": lambda: self.runtime.control.replay_execute(
                params["run_id"],
                requester_kind=caller.kind,
                allow_changed_configuration=params.get("allow_changed_configuration", False),
            ),
            "control.replay.get": lambda: self.runtime.control.replay_get(params["replay_id"]),
            "control.research.timeline": lambda: self.runtime.control.research_timeline(
                params["run_id"], limit=params.get("limit", 100)
            ),
            "control.evidence.get": lambda: self.runtime.evidence_get(params),
            "control.council.get": lambda: self.runtime.council_get(params),
            "control.models.get": lambda: self.runtime.models_get(params),
            "control.memory.get": lambda: self.runtime.memory_get(params),
            "control.memory.trace": lambda: self.runtime.memory_trace(params),
        }
        return handlers[operation]()

    def handle(self, value: Any) -> dict[str, Any]:
        request_id = "unknown"
        operation: str | None = None
        if isinstance(value, dict):
            candidate_id = value.get("request_id")
            if isinstance(candidate_id, str) and REQUEST_ID_RE.fullmatch(candidate_id):
                request_id = candidate_id
            candidate_operation = value.get("operation")
            if isinstance(candidate_operation, str) and candidate_operation:
                operation = candidate_operation[:256]
        try:
            request_id, caller, operation, params = validate_request_envelope(value)
            self._charge(caller, operation)
            return success_envelope(
                request_id,
                operation,
                self._dispatch(caller, operation, params),
            )
        except AgentAPIError as exc:
            return error_envelope(request_id, operation, exc)
        except (
            WebUIError,
            ReplayError,
            StorageError,
            OracleAdapterError,
            NexusAdapterError,
            ModelStateError,
            DnaLatticeError,
            OSError,
            ValueError,
        ) as exc:
            return error_envelope(
                request_id,
                operation,
                AgentAPIError("OPERATION_FAILED", str(exc), retryable=False),
            )
