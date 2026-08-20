from __future__ import annotations

from typing import Any

from adapters.nexus import NexusAdapterError
from adapters.oracle import OracleAdapterError
from storage.control_store import StorageError
from storage.dna_lattice import DnaLatticeError
from storage.model_state import ModelStateError
from webui.common import WebUIConfig, WebUIError

from .common import (
    MAX_MUTATIONS_PER_CALLER,
    MAX_REQUESTS_PER_CALLER,
    MUTATION_OPERATIONS,
    AgentAPIError,
    Caller,
    QuotaState,
    error_envelope,
    success_envelope,
    validate_request_envelope,
)
from .runtime import ControlAgentAPIRuntime


class AgentAPIDispatcher:
    def __init__(self, config: WebUIConfig):
        self.runtime = ControlAgentAPIRuntime(config)
        self._quota: dict[str, QuotaState] = {}

    def _charge(self, caller: Caller, operation: str) -> None:
        state = self._quota.setdefault(caller.quota_key, QuotaState())
        if state.requests >= MAX_REQUESTS_PER_CALLER:
            raise AgentAPIError(
                "QUOTA_EXCEEDED",
                "caller request quota exceeded for this agent API process",
                details={"limit": MAX_REQUESTS_PER_CALLER, "kind": "requests"},
            )
        is_mutation = operation in MUTATION_OPERATIONS
        if is_mutation and state.mutations >= MAX_MUTATIONS_PER_CALLER:
            raise AgentAPIError(
                "QUOTA_EXCEEDED",
                "caller mutation quota exceeded for this agent API process",
                details={"limit": MAX_MUTATIONS_PER_CALLER, "kind": "mutations"},
            )
        state.requests += 1
        if is_mutation:
            state.mutations += 1

    def _dispatch(
        self, caller: Caller, operation: str, params: dict[str, Any]
    ) -> Any:
        handlers = {
            "control.health": lambda: self.runtime.health(),
            "control.capabilities": lambda: self.runtime.capabilities(),
            "control.ask": lambda: self.runtime.ask(caller, params),
            "control.file.put": lambda: self.runtime.file_put(caller, params),
            "control.file.get": lambda: self.runtime.file_get(params),
            "control.collection.create": lambda: self.runtime.collection_create(caller, params),
            "control.collection.snapshot": lambda: self.runtime.collection_snapshot(params),
            "control.collection.search": lambda: self.runtime.collection_search(params),
            "control.run.get": lambda: self.runtime.run_get(params),
            "control.run.compare": lambda: self.runtime.run_compare(params),
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
