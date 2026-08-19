import tempfile
import unittest
from pathlib import Path

from storage.interaction_store import InteractionStore
from storage.model_state import ModelStateError, ModelStateRegistry

TIME = "2026-08-19T10:25:00+09:30"


class ModelStateProvenanceGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run = InteractionStore(self.root).create_run(
            question="What provenance can CONTROL actually establish?",
            mode="council",
            requester_kind="human",
            created_at=TIME,
            evidence_state="unknown",
            replayability="R3",
        )
        self.registry = ModelStateRegistry(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def base(self):
        return {
            "captured_at": TIME,
            "model": {
                "provider": "local",
                "runtime": "fixture",
                "runtime_version": "1.0.0",
                "model_id": "fixture-model",
                "revision": None,
                "model_hash": None,
                "weight_hash": None,
                "tokenizer_identity": None,
                "tokenizer_hash": None,
                "quantization": None,
            },
            "execution": {
                "council_seat": "A",
                "mode": "analytical",
                "stochastic": False,
                "seed": 1,
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
            "system": {
                "control_run_id": self.run["run_id"],
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
        }

    def test_caller_cannot_self_award_locally_verified(self):
        descriptor = self.base()
        with self.assertRaisesRegex(ModelStateError, "reserved for CONTROL verification"):
            self.registry.capture(
                **descriptor,
                field_provenance={
                    "model.model_id": "locally_verified",
                },
            )
        self.assertEqual(
            list((self.root / "records" / "model-states").glob("*.json")), []
        )

    def test_runtime_assigns_locally_verified_to_facts_it_checks(self):
        weights = self.root / "weights.bin"
        weights.write_bytes(b"verified-weight-bytes")
        descriptor = self.base()
        record = self.registry.capture(
            **descriptor,
            field_provenance={
                "model.provider": "observed",
                "model.runtime": "observed",
                "model.model_id": "provider_reported",
            },
            local_artifacts={"weights": weights},
        )
        provenance = record["field_provenance"]
        self.assertEqual(provenance["system.control_run_id"], "locally_verified")
        self.assertEqual(provenance["model.weight_hash"], "locally_verified")
        self.assertEqual(provenance["model.artifacts.weights"], "locally_verified")
        self.assertEqual(provenance["model.model_id"], "provider_reported")


if __name__ == "__main__":
    unittest.main()
