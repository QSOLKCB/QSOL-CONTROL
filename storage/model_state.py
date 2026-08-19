#!/usr/bin/env python3
"""Canonical Phase-4 model-state runtime facade.

The full Phase-4 registry record is richer than the compact model_state event
projection introduced with Phase 1B. This facade keeps the finalized registry as
the canonical source while linking each state into its containing run through a
backward-compatible event projection that references the canonical state_id.

REGISTRY_RECORD = CANONICAL_MODEL_STATE
RUN_EVENT_PAYLOAD = BACKWARD_COMPATIBLE_PROJECTION
"""

from __future__ import annotations

from typing import Any

from .model_state_registry import (
    ARCHAEOLOGY_PROTOCOL,
    EPISTEMIC_BOUNDARY,
    MODEL_STATE_PROTOCOL,
    ModelStateError,
    ModelStateRegistry as _Registry,
    PROVENANCE_KINDS,
    hash_local_artifact,
)


class ModelStateRegistry(_Registry):
    """Public registry with Phase-1B-compatible run-event linkage."""

    @staticmethod
    def _event_projection(record: dict[str, Any]) -> dict[str, Any]:
        model = record["model"]
        execution = record["execution"]
        system = record["system"]
        return {
            "protocol": MODEL_STATE_PROTOCOL,
            "state_id": record["state_id"],
            "captured_at": record["captured_at"],
            "model": {
                "provider": model["provider"],
                "runtime": model["runtime"],
                "runtime_version": model["runtime_version"],
                "model_id": model["model_id"],
                "revision": model["revision"],
                "weight_hash": model["weight_hash"],
                "tokenizer_identity": model["tokenizer_identity"],
                "quantization": model["quantization"],
                # The registry has field-level provenance. The older event
                # schema has only one coarse slot, so do not collapse nuanced
                # provenance into a stronger claim.
                "metadata_provenance": "unknown",
            },
            "execution": {
                "council_seat": execution["council_seat"],
                "mode": execution["mode"],
                "stochastic": execution["stochastic"],
                "seed": execution["seed"],
                "context_limit": execution["context_limit"],
                "sampling": execution["sampling"],
                "tool_permissions": execution["tool_permissions"],
            },
            "system": {
                "control_run_id": system["control_run_id"],
                "nexus_identity": system["nexus_identity"],
                "oracle_refs": system["oracle_refs"],
                "substrate_identity": system["substrate_identity"],
                "hardware_runtime_metadata": system["hardware_runtime_metadata"],
            },
            "hidden_chain_of_thought_captured": False,
        }

    def _ensure_run_event(self, record: dict[str, Any]) -> dict[str, Any]:
        run_id = record["system"]["control_run_id"]
        state_id = record["state_id"]
        for event in self.interactions.list_events(run_id):
            if (
                event.get("kind") == "model_state"
                and event.get("payload", {}).get("state_id") == state_id
            ):
                return event
        return self.interactions.append_event(
            run_id,
            kind="model_state",
            payload=self._event_projection(record),
            occurred_at=record["captured_at"],
            record_refs=[state_id],
        )


__all__ = [
    "ARCHAEOLOGY_PROTOCOL",
    "EPISTEMIC_BOUNDARY",
    "MODEL_STATE_PROTOCOL",
    "ModelStateError",
    "ModelStateRegistry",
    "PROVENANCE_KINDS",
    "hash_local_artifact",
]
