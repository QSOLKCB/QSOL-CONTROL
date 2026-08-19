import hashlib
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from storage.control_store import canonical_json_bytes
from storage.interaction_store import InteractionStore
from storage.model_state_registry import (
    EPISTEMIC_BOUNDARY,
    ModelStateError,
    ModelStateRegistry,
)

TIME_A = "2026-08-19T10:10:00+09:30"
TIME_B = "2026-08-19T10:11:00+09:30"


class ModelStateRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.interactions = InteractionStore(self.root)
        self.run_a = self.interactions.create_run(
            question="Which model configuration produced this visible output?",
            mode="council",
            requester_kind="human",
            created_at=TIME_A,
            evidence_state="unknown",
            replayability="R3",
        )
        self.run_b = self.interactions.create_run(
            question="Which model configuration produced this visible output on rerun?",
            mode="council",
            requester_kind="human",
            created_at=TIME_B,
            evidence_state="unknown",
            replayability="R3",
        )
        self.registry = ModelStateRegistry(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def descriptor(self, run_id, *, revision="r1", temperature=0.2, privacy="INTERNAL"):
        return {
            "captured_at": TIME_A if run_id == self.run_a["run_id"] else TIME_B,
            "model": {
                "provider": "local",
                "runtime": "ollama",
                "runtime_version": "0.12.0",
                "model_id": "fixture-model",
                "revision": revision,
                "model_hash": None,
                "weight_hash": None,
                "tokenizer_identity": "fixture-tokenizer",
                "tokenizer_hash": None,
                "quantization": "Q4_K_M",
            },
            "execution": {
                "council_seat": "seat-A",
                "mode": "analytical",
                "stochastic": True,
                "seed": 42,
                "context_limit": 8192,
                "sampling": {"temperature": temperature, "top_p": 0.95},
                "tool_permissions": ["search.read"],
                "tool_permission_envelope": {
                    "filesystem": "read-only",
                    "network": "restricted",
                    "tools": ["search.read"],
                    "mcp_plugins": [],
                    "external_execution": False,
                },
            },
            "system": {
                "control_run_id": run_id,
                "control_manifest_identity": "manifest:fixture",
                "nexus_identity": "nexus/0.14@fixture",
                "oracle_refs": [],
                "substrate_identity": "substrate:fixture",
                "ark_identity": "ark:fixture",
                "int_identity": "int:fixture",
                "collection_snapshot_id": None,
                "evidence_snapshot_ref": "object:" + "a" * 64,
                "hardware_runtime_metadata": {
                    "os": "linux",
                    "accelerator_class": "fixture-gpu",
                    "precision": "int4",
                },
            },
            "field_provenance": {
                "model.provider": "observed",
                "model.runtime": "observed",
                "model.runtime_version": "observed",
                "model.model_id": "provider_reported",
                "model.revision": "provider_reported",
                "model.quantization": "observed",
                "execution.council_seat": "locally_verified",
                "execution.mode": "locally_verified",
                "execution.sampling": "observed",
                "execution.context_limit": "provider_reported",
                "system.nexus_identity": "locally_verified",
                "system.hardware_runtime_metadata": "observed",
            },
            "privacy_class": privacy,
        }

    def capture(self, descriptor, *, local_artifacts=None):
        return self.registry.capture(
            captured_at=descriptor["captured_at"],
            model=descriptor["model"],
            execution=descriptor["execution"],
            system=descriptor["system"],
            field_provenance=descriptor["field_provenance"],
            privacy_class=descriptor["privacy_class"],
            local_artifacts=local_artifacts,
            link_run_event=False,
        )

    def test_capture_is_content_addressed_persistent_and_boundary_explicit(self):
        descriptor = self.descriptor(self.run_a["run_id"])
        first = self.capture(descriptor)
        second = self.capture(descriptor)
        self.assertEqual(first, second)
        self.assertRegex(first["state_id"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(first["epistemic_boundary"], EPISTEMIC_BOUNDARY)
        self.assertFalse(first["hidden_chain_of_thought_captured"])
        self.assertFalse(first["model_mind_captured"])
        self.assertEqual(first["authority"], "reproducibility-metadata-only")
        self.assertEqual(first["field_provenance"]["captured_at"], "observed")
        self.assertEqual(
            first["field_provenance"]["system.control_run_id"], "locally_verified"
        )
        verified = self.registry.verify_state(first["state_id"])
        self.assertEqual(verified["status"], "valid")
        self.assertFalse(verified["interaction_event_linked"])

    def test_local_model_weight_and_tokenizer_artifacts_are_hashed_without_paths(self):
        model_file = self.root / "fixture-model.gguf"
        weights_file = self.root / "weights.bin"
        tokenizer_file = self.root / "tokenizer.json"
        model_file.write_bytes(b"MODEL-BYTES")
        weights_file.write_bytes(b"WEIGHT-BYTES")
        tokenizer_file.write_bytes(b'{"tokenizer":"fixture"}')
        descriptor = self.descriptor(self.run_a["run_id"])
        state = self.capture(
            descriptor,
            local_artifacts={
                "model": model_file,
                "weights": weights_file,
                "tokenizer": tokenizer_file,
            },
        )
        self.assertEqual(
            state["model"]["model_hash"],
            "sha256:" + hashlib.sha256(b"MODEL-BYTES").hexdigest(),
        )
        self.assertEqual(
            state["model"]["weight_hash"],
            "sha256:" + hashlib.sha256(b"WEIGHT-BYTES").hexdigest(),
        )
        self.assertEqual(
            state["model"]["tokenizer_hash"],
            "sha256:" + hashlib.sha256(tokenizer_file.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            state["field_provenance"]["model.artifacts.weights"], "locally_verified"
        )
        self.assertEqual(
            state["field_provenance"]["model.weight_hash"], "locally_verified"
        )
        encoded = canonical_json_bytes(state).decode("utf-8")
        self.assertNotIn(str(model_file), encoded)
        self.assertNotIn(str(weights_file), encoded)
        self.assertNotIn(str(tokenizer_file), encoded)
        self.assertNotIn("MODEL-BYTES", encoded)
        self.assertNotIn("WEIGHT-BYTES", encoded)

    def test_directory_artifact_uses_explicit_manifest_identity(self):
        directory = self.root / "sharded"
        directory.mkdir()
        (directory / "a.bin").write_bytes(b"A")
        (directory / "b.bin").write_bytes(b"B")
        descriptor = self.descriptor(self.run_a["run_id"])
        state = self.capture(descriptor, local_artifacts={"weights": directory})
        artifact = state["model"]["artifacts"]["weights"]
        self.assertEqual(artifact["kind"], "directory-manifest")
        self.assertEqual(artifact["file_count"], 2)
        self.assertEqual(
            artifact["manifest_protocol"], "qsol-control-local-artifact-manifest/1"
        )
        self.assertEqual(state["model"]["weight_hash"], artifact["sha256"])

    def test_unspecified_field_provenance_defaults_to_unknown(self):
        state = self.capture(self.descriptor(self.run_a["run_id"]))
        self.assertEqual(state["field_provenance"]["model.model_hash"], "unknown")
        self.assertEqual(state["field_provenance"]["execution.seed"], "unknown")
        self.assertEqual(state["field_provenance"]["system.ark_identity"], "unknown")

    def test_hidden_reasoning_and_credential_fields_fail_before_persistence(self):
        for section, key in (
            ("model", "api_key"),
            ("execution", "hidden_reasoning"),
            ("system", "access_token"),
        ):
            with self.subTest(section=section, key=key):
                descriptor = self.descriptor(self.run_a["run_id"])
                descriptor[section][key] = "ordinary-looking-secret"
                before = list((self.root / "records" / "model-states").glob("*.json"))
                with self.assertRaises(ModelStateError):
                    self.capture(descriptor)
                after = list((self.root / "records" / "model-states").glob("*.json"))
                self.assertEqual(before, after)

    def test_unknown_run_is_rejected(self):
        descriptor = self.descriptor("sha256:" + "f" * 64)
        with self.assertRaises(ModelStateError):
            self.capture(descriptor)

    def test_state_comparison_preserves_values_and_provenance_without_mind_inference(self):
        left = self.capture(self.descriptor(self.run_a["run_id"], revision="r1", temperature=0.2))
        right_descriptor = self.descriptor(self.run_b["run_id"], revision="r2", temperature=0.7)
        right_descriptor["field_provenance"]["model.revision"] = "locally_verified"
        right = self.capture(right_descriptor)
        comparison = self.registry.compare_states(left["state_id"], right["state_id"])
        paths = {item["path"] for item in comparison["changed_fields"]}
        self.assertIn("model.revision", paths)
        self.assertIn("execution.sampling", paths)
        self.assertFalse(comparison["model_mind_inference"])
        revision_change = next(
            item for item in comparison["changed_fields"] if item["path"] == "model.revision"
        )
        self.assertEqual(revision_change["left_provenance"], "provider_reported")
        self.assertEqual(revision_change["right_provenance"], "locally_verified")

    def test_cross_run_comparison_aligns_by_council_seat(self):
        left = self.capture(self.descriptor(self.run_a["run_id"], revision="r1"))
        right = self.capture(self.descriptor(self.run_b["run_id"], revision="r2"))
        report = self.registry.compare_runs(self.run_a["run_id"], self.run_b["run_id"])
        self.assertEqual(len(report["aligned"]), 1)
        self.assertEqual(report["aligned"][0]["key"], "seat:seat-A")
        self.assertEqual(
            report["aligned"][0]["comparison"]["left_state_id"], left["state_id"]
        )
        self.assertEqual(
            report["aligned"][0]["comparison"]["right_state_id"], right["state_id"]
        )
        self.assertFalse(report["model_mind_inference"])

    def test_archaeology_export_is_deterministic_self_describing_and_contains_no_model_bytes(self):
        model_file = self.root / "model.gguf"
        model_file.write_bytes(b"SUPER-SECRET-MODEL-BYTE-FIXTURE")
        state = self.capture(
            self.descriptor(self.run_a["run_id"]),
            local_artifacts={"model": model_file},
        )
        first = self.registry.build_archaeology_export(state_ids=[state["state_id"]])
        second = self.registry.build_archaeology_export(state_ids=[state["state_id"]])
        self.assertEqual(first, second)
        self.assertRegex(first["export_id"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(first["epistemic_boundary"], EPISTEMIC_BOUNDARY)
        self.assertFalse(first["hidden_chain_of_thought_captured"])
        self.assertFalse(first["model_mind_captured"])
        self.assertFalse(first["contains_model_artifact_bytes"])
        self.assertFalse(first["local_artifact_paths_persisted"])
        encoded = canonical_json_bytes(first)
        self.assertNotIn(b"SUPER-SECRET-MODEL-BYTE-FIXTURE", encoded)
        self.assertNotIn(str(model_file).encode("utf-8"), encoded)

    def test_restricted_archaeology_export_requires_acknowledgement_and_is_owner_only(self):
        state = self.capture(
            self.descriptor(self.run_a["run_id"], privacy="RESTRICTED")
        )
        with self.assertRaisesRegex(ModelStateError, "explicit acknowledgement"):
            self.registry.build_archaeology_export(state_ids=[state["state_id"]])
        output = self.root / "archaeology.json"
        export = self.registry.write_archaeology_export(
            output,
            state_ids=[state["state_id"]],
            allow_restricted=True,
        )
        self.assertEqual(export["privacy_class"], "RESTRICTED")
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)

    def test_tampered_registry_record_fails_content_identity(self):
        state = self.capture(self.descriptor(self.run_a["run_id"]))
        path = self.registry._path(state["state_id"])
        tampered = json.loads(path.read_text(encoding="utf-8"))
        tampered["model"]["model_id"] = "different-model"
        path.write_bytes(canonical_json_bytes(tampered))
        with self.assertRaisesRegex(ModelStateError, "content identity|state_id"):
            self.registry.get_state(state["state_id"])


if __name__ == "__main__":
    unittest.main()
