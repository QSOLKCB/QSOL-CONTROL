import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PostRoadmapExtensionContractTests(unittest.TestCase):
    def load(self, relative):
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_extension_manifest_is_separate_from_frozen_core_contract(self):
        core = self.load("manifest.json")
        ext = self.load("extensions/manifest.json")
        self.assertEqual(core["schema_version"], "2.6.0")
        self.assertEqual(core["status"]["completed_through_roadmap_phase"], 10)
        self.assertEqual(ext["protocol"], "qsol-control-post-roadmap-extensions/1")
        self.assertEqual(ext["core_contract_version"], "2.6.0")
        self.assertEqual(ext["authority"], "none")
        self.assertEqual(
            ext["extensions"]["remote_multi_user_gateway"]["status"],
            "implemented-reference",
        )
        self.assertEqual(
            ext["extensions"]["native_mobile_clients"]["status"],
            "implemented-reference",
        )
        self.assertEqual(
            ext["extensions"]["distributed_consensus_coordination"]["status"],
            "implemented-external-adapter",
        )

    def test_deferred_roadmap_has_explicit_resolutions_not_open_promises(self):
        roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
        section = roadmap.split("## Post-roadmap deferred resolution — PR #15", 1)[1]
        self.assertNotIn("- [ ]", section)
        self.assertIn("Remote multi-user deployment: resolved by", section)
        self.assertIn("Mobile native applications: resolved by", section)
        self.assertIn("Distributed consensus for CONTROL storage: resolved by", section)
        self.assertIn("Automatic truth scoring: resolved as a permanent forbidden non-goal", section)
        self.assertIn("HIDDEN_CHAIN_OF_THOUGHT_CAPTURE = FORBIDDEN", section)

    def test_release_inventory_contains_optional_extension_source(self):
        inventory = self.load("release/release-inventory.json")
        self.assertIn("EXTENSIONS.md", inventory["top_level_files"])
        self.assertIn("extensions", inventory["roots"])
        self.assertIn("mobile", inventory["roots"])
        self.assertEqual(inventory["repository_contract_version"], "2.6.0")

    def test_remote_mobile_consensus_contracts_preserve_authority_boundaries(self):
        remote = self.load("ai/remote-gateway-contract.json")
        mobile = self.load("ai/mobile-client-contract.json")
        consensus = self.load("ai/consensus-adapter-contract.json")
        self.assertFalse(remote["transport"]["client_supplied_caller_identity"])
        self.assertTrue(remote["network"]["non_loopback_requires_tls"])
        self.assertFalse(remote["epistemic_privilege_added"])
        self.assertFalse(mobile["truth_scoring_ui"])
        self.assertFalse(mobile["hidden_chain_of_thought_ui"])
        self.assertFalse(consensus["consensus_algorithm_implemented_by_control"])
        self.assertFalse(consensus["control_storage_mutated_by_adapter"])
        self.assertFalse(consensus["semantic_authority_claimed"])


if __name__ == "__main__":
    unittest.main()
