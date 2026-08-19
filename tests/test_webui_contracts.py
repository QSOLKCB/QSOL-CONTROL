import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WebUIContractTests(unittest.TestCase):
    def test_webui_contract_pins_authority_and_labels(self):
        contract = json.loads((ROOT / "ai" / "webui-contract.json").read_text(encoding="utf-8"))
        self.assertEqual(contract["protocol"], "qsol-control-webui/1")
        self.assertEqual(contract["bind_policy"]["default"], "127.0.0.1")
        self.assertTrue(contract["security_boundary"]["loopback_host_header_required"])
        self.assertTrue(contract["security_boundary"]["dns_rebinding_non_loopback_host_rejected"])
        self.assertTrue(contract["security_boundary"]["state_changing_origin_must_match_loopback_server"])
        self.assertFalse(contract["truth_percentage"]["implemented"])
        labels = contract["model_state_inspector"]["labels"]
        self.assertEqual(labels["panel_title"], "Model-state reproducibility metadata")
        self.assertEqual(labels["boundary_badge"], "Not model mind")
        self.assertIn("PROVIDER_REPORTED != LOCALLY_VERIFIED", contract["invariants"])

    def test_static_assets_do_not_use_innerhtml_for_untrusted_records(self):
        app = (ROOT / "webui" / "static" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", app)
        self.assertIn("textContent", app)
        self.assertIn("CONSENSUS ≠ TRUTH", (ROOT / "webui" / "static" / "index.html").read_text(encoding="utf-8"))

    def test_phase5_roadmap_is_complete(self):
        roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
        phase = roadmap.split("## Phase 5 — Human WebUI", 1)[1].split("## Phase 6 — AI / agent API", 1)[0]
        self.assertNotIn("- [ ]", phase)
        self.assertIn("Never display a synthetic `truth percentage`", phase)
        self.assertIn("MODEL_STATE != MODEL_MIND", phase)

    def test_manifest_registers_webui_without_claiming_remote_deployment(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["interfaces"]["human"], "local-loopback-webui")
        self.assertEqual(manifest["interfaces"]["webui_cli"], "tools/webui.py")
        self.assertEqual(manifest["status"]["completed_through_roadmap_phase"], 5)
        self.assertEqual(manifest["status"]["webui"], "implemented-phase-5-local-loopback")
        self.assertFalse(manifest["webui"]["remote_multi_user_deployment"])
        self.assertTrue(manifest["webui"]["loopback_host_header_required"])
        self.assertTrue(manifest["webui"]["dns_rebinding_non_loopback_host_rejected"])
        self.assertTrue(manifest["webui"]["same_origin_mutations_required"])
        self.assertFalse(manifest["webui"]["truth_percentage"])


if __name__ == "__main__":
    unittest.main()
