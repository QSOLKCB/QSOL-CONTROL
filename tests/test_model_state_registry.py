import hashlib
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from storage.control_store import StorageError, canonical_json_bytes
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

    def descriptor(
        self,
        run_id,
        *,
        revision="r1",
        runtime_version="0.12.0",
        quantization="Q4_K_M",
        temperature=0.2,
        privacy="INTERNAL",
        council_seat="seat-A",
        provider="local",
        model_id="fixture-model",
    ):
        return {
            "captured_at": TIME_A if run_id == self.run_a["run_id"] else TIME_B,
            "model": {
                "provider": provider,
                "runtime": "ollama",
                "runtime_version": runtime_version,
                "model_id": model_id,
                "revision": revision,
                "model_hash": None,
                "weight_hash": None,
                "tokenizer_identity": "fixture-tokenizer",
                "tokenizer_hash": None,
                "quantization": quantization,
            },
            "execution": {
                "council_seat": council_seat,
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
                "execution.council_seat": "observed",
                "execution.mode": "observed",
                "execution.sampling": "observed",
                "execution.context_limit": "provider_reported",
                "system.nexus_identity": "observed",
                "system.hardware_runtime_metadata": "observed",
            },
            "privacy_class": privacy,
        }

    def capture(self, descriptor, *, local_artifacts=None, link_run_event=False):
        return self.registry.capture(
            captured_at=descriptor["captured_at"],
            model=descriptor["model"],
            execution=descriptor["execution"],
            system=descriptor["system"],
            field_provenance=descriptor["field_provenance"],
            privacy_class=descriptor["privacy_class"],
            local_artifacts=local_artifacts,
            link_run_event=link_run_event,
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

    def test_registered_runtime_links_compact_projection(self):
        descriptor = self.descriptor(self.run_a["run_id"])
        state = self.capture(descriptor, link_run_event=True)
        events = self.interactions.list_events(self.run_a["run_id"])
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["kind"], "model_state")
        self.assertEqual(event["record_refs"], [state["state_id"]])
        self.assertEqual(event["payload"]["state_id"], state["state_id"])
        self.assertNotIn("field_provenance", event["payload"])
        self.assertEqual(event["payload"]["model"]["metadata_provenance"], "unknown")
        self.assertIn("field_provenance", self.registry.get_state(state["state_id"]))

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

    def test_registered_runtime_rejects_caller_self_awarded_locally_verified(self):
        descriptor = self.descriptor(self.run_a["run_id"])
        descriptor["field_provenance"]["model.model_id"] = "locally_verified"
        with self.assertRaisesRegex(ModelStateError, "reserved for CONTROL verification"):
            self.capture(descriptor)
        self.assertEqual(list((self.root / "records" / "model-states").glob("*.json")), [])

    def test_vendor_prefixed_credentials_fail_closed_before_persistence(self):
        for key in ("openai_api_key", "aws_secret_access_key", "github_token"):
            with self.subTest(key=key):
                descriptor = self.descriptor(self.run_a["run_id"])
                descriptor["system"]["hardware_runtime_metadata"][key] = "sk-live-secret"
                before = list((self.root / "records" / "model-states").glob("*.json"))
                with self.assertRaisesRegex(ModelStateError, "credential field"):
                    self.capture(descriptor)
                after = list((self.root / "records" / "model-states").glob("*.json"))
                self.assertEqual(before, after)

    def test_hidden_reasoning_and_generic_credential_fields_fail_before_persistence(self):
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

    def test_inherited_oracle_refs_are_not_promoted_to_locally_verified(self):
        run = self.interactions.create_run(
            question="Preserve lineage without promoting ORACLE authority.",
            mode="council",
            requester_kind="human",
            created_at=TIME_A,
            evidence_state="unknown",
            oracle_refs=["oracle:unverified-user-input"],
            replayability="R3",
        )
        descriptor = self.descriptor(run["run_id"])
        descriptor["system"]["oracle_refs"] = None
        state = self.capture(descriptor)
        self.assertEqual(state["system"]["oracle_refs"], ["oracle:unverified-user-input"])
        self.assertEqual(state["field_provenance"]["system.oracle_refs"], "unknown")

    def test_tool_envelope_cannot_add_undeclared_tools(self):
        descriptor = self.descriptor(self.run_a["run_id"])
        descriptor["execution"]["tool_permissions"] = []
        descriptor["execution"]["tool_permission_envelope"]["tools"] = ["shell"]
        with self.assertRaisesRegex(ModelStateError, "tool_permissions.*disagree"):
            self.capture(descriptor)

    def test_unknown_run_is_rejected(self):
        descriptor = self.descriptor("sha256:" + "f" * 64)
        with self.assertRaises(StorageError):
            self.capture(descriptor)

    def test_state_comparison_preserves_values_provenance_and_full_identity(self):
        left = self.capture(
            self.descriptor(
                self.run_a["run_id"],
                revision="r1",
                runtime_version="0.12.0",
                quantization="Q4_K_M",
                temperature=0.2,
            )
        )
        right_descriptor = self.descriptor(
            self.run_b["run_id"],
            revision="r1",
            runtime_version="0.13.0",
            quantization="Q8_0",
            temperature=0.7,
        )
        right = self.capture(right_descriptor)
        comparison = self.registry.compare_states(left["state_id"], right["state_id"])
        paths = {item["path"] for item in comparison["changed_fields"]}
        self.assertIn("model.runtime_version", paths)
        self.assertIn("model.quantization", paths)
        self.assertIn("execution.sampling", paths)
        self.assertFalse(comparison["same_model_identity"])
        self.assertFalse(comparison["model_mind_inference"])

    def test_cross_run_comparison_aligns_by_council_seat(self):
        left = self.capture(self.descriptor(self.run_a["run_id"], revision="r1"))
        right = self.capture(self.descriptor(self.run_b["run_id"], revision="r2"))
        report = self.registry.compare_runs(self.run_a["run_id"], self.run_b["run_id"])
        self.assertEqual(len(report["aligned"]), 1)
        self.assertTrue(report["aligned"][0]["key"].startswith("seat:"))
        self.assertEqual(report["aligned"][0]["comparison"]["left_state_id"], left["state_id"])
        self.assertEqual(report["aligned"][0]["comparison"]["right_state_id"], right["state_id"])
        self.assertFalse(report["model_mind_inference"])

    def test_fallback_alignment_key_has_no_delimiter_collision(self):
        left = {
            "execution": {"council_seat": None},
            "model": {"provider": "a:b", "model_id": "c"},
        }
        right = {
            "execution": {"council_seat": None},
            "model": {"provider": "a", "model_id": "b:c"},
        }
        self.assertNotEqual(self.registry._run_key(left), self.registry._run_key(right))

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
        state = self.capture(self.descriptor(self.run_a["run_id"], privacy="RESTRICTED"))
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
