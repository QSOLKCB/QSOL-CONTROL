import tempfile
import unittest
from pathlib import Path

from storage.interaction_store import InteractionStore
from storage.model_state import ModelStateRegistry

TIME = "2026-08-19T10:20:00+09:30"


class ModelStateRunLinkageTests(unittest.TestCase):
    def test_full_registry_record_links_by_compact_backward_compatible_projection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            interactions = InteractionStore(root)
            run = interactions.create_run(
                question="Which model state was externally recorded?",
                mode="council",
                requester_kind="human",
                created_at=TIME,
                evidence_state="unknown",
                replayability="R3",
            )
            registry = ModelStateRegistry(root)
            state = registry.capture(
                captured_at=TIME,
                model={
                    "provider": "local",
                    "runtime": "fixture",
                    "runtime_version": "1.0.0",
                    "model_id": "fixture-model",
                    "revision": "r1",
                    "model_hash": None,
                    "weight_hash": None,
                    "tokenizer_identity": None,
                    "tokenizer_hash": None,
                    "quantization": None,
                },
                execution={
                    "council_seat": "seat-A",
                    "mode": "analytical",
                    "stochastic": False,
                    "seed": 7,
                    "context_limit": 4096,
                    "sampling": {},
                    "tool_permissions": [],
                    "tool_permission_envelope": {
                        "filesystem": "none",
                        "network": "none",
                        "tools": [],
                        "mcp_plugins": [],
                        "external_execution": False,
                    },
                },
                system={
                    "control_run_id": run["run_id"],
                    "control_manifest_identity": None,
                    "nexus_identity": None,
                    "oracle_refs": [],
                    "substrate_identity": None,
                    "ark_identity": None,
                    "int_identity": None,
                    "collection_snapshot_id": None,
                    "evidence_snapshot_ref": None,
                    "hardware_runtime_metadata": {},
                },
                field_provenance={
                    "model.provider": "observed",
                    "model.runtime": "observed",
                    "model.model_id": "observed",
                },
            )

            report = registry.verify_state(state["state_id"])
            self.assertTrue(report["interaction_event_linked"])
            events = interactions.list_events(run["run_id"])
            self.assertEqual(len(events), 1)
            event = events[0]
            self.assertEqual(event["kind"], "model_state")
            self.assertEqual(event["record_refs"], [state["state_id"]])
            self.assertEqual(event["payload"]["state_id"], state["state_id"])
            self.assertEqual(event["payload"]["protocol"], "qsol-control-model-state/1")
            self.assertFalse(event["payload"]["hidden_chain_of_thought_captured"])
            self.assertEqual(event["payload"]["model"]["metadata_provenance"], "unknown")

            # The compact event is deliberately not the canonical full record.
            self.assertNotIn("field_provenance", event["payload"])
            self.assertIn("field_provenance", registry.get_state(state["state_id"]))

            # Re-capture is idempotent and does not append a duplicate link.
            duplicate = registry.capture(
                captured_at=TIME,
                model={
                    "provider": "local",
                    "runtime": "fixture",
                    "runtime_version": "1.0.0",
                    "model_id": "fixture-model",
                    "revision": "r1",
                    "model_hash": None,
                    "weight_hash": None,
                    "tokenizer_identity": None,
                    "tokenizer_hash": None,
                    "quantization": None,
                },
                execution={
                    "council_seat": "seat-A",
                    "mode": "analytical",
                    "stochastic": False,
                    "seed": 7,
                    "context_limit": 4096,
                    "sampling": {},
                    "tool_permissions": [],
                    "tool_permission_envelope": {
                        "filesystem": "none",
                        "network": "none",
                        "tools": [],
                        "mcp_plugins": [],
                        "external_execution": False,
                    },
                },
                system={
                    "control_run_id": run["run_id"],
                    "control_manifest_identity": None,
                    "nexus_identity": None,
                    "oracle_refs": [],
                    "substrate_identity": None,
                    "ark_identity": None,
                    "int_identity": None,
                    "collection_snapshot_id": None,
                    "evidence_snapshot_ref": None,
                    "hardware_runtime_metadata": {},
                },
                field_provenance={
                    "model.provider": "observed",
                    "model.runtime": "observed",
                    "model.model_id": "observed",
                },
            )
            self.assertEqual(duplicate["state_id"], state["state_id"])
            self.assertEqual(len(interactions.list_events(run["run_id"])), 1)


if __name__ == "__main__":
    unittest.main()
