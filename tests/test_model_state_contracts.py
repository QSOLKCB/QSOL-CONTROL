import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ModelStateContractTests(unittest.TestCase):
    def load(self, relative):
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_manifest_registers_phase4_surfaces(self):
        manifest = self.load("manifest.json")
        self.assertEqual(manifest["schema_version"], "2.0.0")
        self.assertEqual(
            manifest["model_state_contract"], "ai/model-state-contract.json"
        )
        self.assertEqual(
            manifest["interfaces"]["model_state_cli"], "tools/model_state.py"
        )
        self.assertEqual(
            manifest["persistent_storage"]["model_state_runtime"],
            "storage/model_state_registry.py",
        )
        self.assertEqual(
            manifest["schemas"]["model_state_comparison"],
            "schema/model-state-comparison.schema.json",
        )
        self.assertEqual(
            manifest["schemas"]["model_state_run_comparison"],
            "schema/model-state-run-comparison.schema.json",
        )
        self.assertEqual(
            manifest["schemas"]["model_state_archaeology"],
            "schema/model-state-archaeology.schema.json",
        )
        self.assertEqual(manifest["status"]["completed_through_roadmap_phase"], 4)
        self.assertEqual(
            manifest["status"]["model_state_registry"], "implemented-phase-4"
        )
        self.assertFalse(manifest["status"]["model_state_hidden_chain_of_thought_capture"])
        self.assertFalse(manifest["status"]["model_state_model_mind_capture"])
        self.assertEqual(manifest["status"]["webui"], "not-yet-implemented")

    def test_model_state_schema_enforces_epistemic_boundary(self):
        schema = self.load("schema/model-state.schema.json")
        props = schema["properties"]
        self.assertEqual(props["protocol"]["const"], "qsol-control-model-state/1")
        self.assertEqual(
            props["epistemic_boundary"]["const"], "MODEL_STATE != MODEL_MIND"
        )
        self.assertFalse(props["hidden_chain_of_thought_captured"]["const"])
        self.assertFalse(props["model_mind_captured"]["const"])
        self.assertEqual(
            props["authority"]["const"], "reproducibility-metadata-only"
        )
        provenance = props["field_provenance"]
        self.assertIn("model.weight_hash", provenance["required"])
        self.assertIn("execution.tool_permission_envelope", provenance["required"])
        self.assertIn("system.control_run_id", provenance["required"])
        self.assertEqual(
            provenance["properties"]["system.control_run_id"]["const"],
            "locally_verified",
        )
        self.assertEqual(
            provenance["properties"]["captured_at"]["const"], "observed"
        )

    def test_archaeology_schema_forbids_mind_and_artifact_byte_claims(self):
        schema = self.load("schema/model-state-archaeology.schema.json")
        props = schema["properties"]
        self.assertEqual(
            props["epistemic_boundary"]["const"], "MODEL_STATE != MODEL_MIND"
        )
        self.assertFalse(props["hidden_chain_of_thought_captured"]["const"])
        self.assertFalse(props["model_mind_captured"]["const"])
        self.assertFalse(props["contains_model_artifact_bytes"]["const"])
        self.assertFalse(props["local_artifact_paths_persisted"]["const"])
        self.assertEqual(
            props["ui_boundary_label"]["const"], "Reproducibility metadata — not model mind"
        )

    def test_machine_contract_pins_ui_labels_and_privacy_gate(self):
        contract = self.load("ai/model-state-contract.json")
        self.assertEqual(contract["epistemic_boundary"], "MODEL_STATE != MODEL_MIND")
        self.assertEqual(contract["authority"], "reproducibility-metadata-only")
        labels = contract["ui_labels"]
        self.assertEqual(labels["panel_title"], "Model-state reproducibility metadata")
        self.assertEqual(labels["boundary_badge"], "Not model mind")
        self.assertEqual(labels["unknown_label"], "Unknown / not established")
        self.assertEqual(labels["provider_reported_label"], "Provider reported")
        self.assertEqual(labels["locally_verified_label"], "Locally verified")
        archaeology = contract["archaeology_export"]
        self.assertFalse(archaeology["contains_model_artifact_bytes"])
        self.assertFalse(archaeology["local_artifact_paths_persisted"])
        self.assertTrue(archaeology["restricted_requires_explicit_acknowledgement"])
        self.assertEqual(archaeology["output_file_mode"], "0600")

    def test_valid_fixture_identity_and_negative_fixture_boundary(self):
        valid = self.load("examples/schema/model-state.valid.json")
        state_id = valid["state_id"]
        payload = {key: value for key, value in valid.items() if key != "state_id"}
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        expected = "sha256:" + hashlib.sha256(encoded).hexdigest()
        self.assertEqual(state_id, expected)
        self.assertFalse(valid["hidden_chain_of_thought_captured"])
        self.assertFalse(valid["model_mind_captured"])

        invalid = self.load("examples/schema/model-state.invalid.json")
        self.assertTrue(invalid["hidden_chain_of_thought_captured"])
        self.assertTrue(invalid["model_mind_captured"])

    def test_roadmap_phase4_is_complete_but_webui_remains_open(self):
        roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
        phase4 = roadmap.split("## Phase 4 — AI model-state registry", 1)[1].split(
            "## Phase 5 — Human WebUI", 1
        )[0]
        self.assertNotIn("- [ ]", phase4)
        self.assertIn("MODEL_STATE != MODEL_MIND", phase4)
        self.assertIn("Phase 5 WebUI is **not** implemented yet", phase4)

        webui = (ROOT / "docs" / "WEBUI.md").read_text(encoding="utf-8")
        self.assertIn("Model-state reproducibility metadata", webui)
        self.assertIn("Not model mind", webui)
        self.assertIn("Unknown / not established", webui)
        self.assertIn("MODEL_STATE_COMPARISON != MIND_COMPARISON", webui)


if __name__ == "__main__":
    unittest.main()
