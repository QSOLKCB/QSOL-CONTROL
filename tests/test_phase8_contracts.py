import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Phase8ContractTests(unittest.TestCase):
    def load(self, relative):
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_manifest_registers_phase8_without_erasing_prior_phases(self):
        manifest = self.load("manifest.json")
        major, minor, patch = (int(part) for part in manifest["schema_version"].split("."))
        self.assertEqual(major, 2)
        self.assertGreaterEqual((minor, patch), (4, 0))
        self.assertEqual(
            manifest["ark_repository_recovery_contract"],
            "ai/ark-repository-recovery-contract.json",
        )
        self.assertEqual(
            manifest["ark_repository_recovery_document"],
            "docs/ARK-REPOSITORY-RECOVERY.md",
        )
        self.assertEqual(
            manifest["interfaces"]["ark_repository_recovery_cli"],
            "tools/repository_recovery.py",
        )
        self.assertEqual(
            manifest["persistent_storage"]["ark_repository_recovery_runtime"],
            "storage/ark_repository_bundle.py",
        )
        self.assertEqual(
            manifest["schemas"]["ark_repository_recovery"],
            "schema/ark-repository-recovery.schema.json",
        )
        self.assertGreaterEqual(
            manifest["status"]["completed_through_roadmap_phase"], 8
        )
        self.assertEqual(
            manifest["status"]["ark_repository_recovery"],
            "implemented-phase-8",
        )
        self.assertEqual(manifest["status"]["replay"], "implemented-phase-7")
        self.assertTrue(manifest["status"]["webui"].startswith("implemented-phase-5"))

    def test_ai_bootstrap_registers_phase8_additively(self):
        bootstrap = self.load("README4AI.md")
        self.assertGreaterEqual(bootstrap["schema_version"], 11)
        contract_major, contract_minor, _ = (
            int(part) for part in bootstrap["contracts"]["schema_version"].split(".")
        )
        self.assertEqual(contract_major, 2)
        self.assertGreaterEqual(contract_minor, 4)
        recovery = bootstrap["ark_repository_recovery"]
        self.assertEqual(recovery["status"], "implemented_phase8")
        self.assertFalse(recovery["optional_material_is_canonical"])
        self.assertTrue(recovery["strictest_privacy_recomputed_after_restore"])
        self.assertTrue(recovery["all_canonical_records_semantically_validated"])
        self.assertTrue(recovery["untrusted_bootstrap_map_capsules_bounded_before_read"])
        self.assertFalse(recovery["webui_required"])
        self.assertFalse(recovery["original_search_engine_required"])
        self.assertEqual(bootstrap["agent_api"]["status"], "implemented_phase6")
        self.assertEqual(bootstrap["replay"]["status"], "implemented_phase7")

    def test_phase8_roadmap_gate_is_complete(self):
        roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
        phase8 = roadmap.split("## Phase 8 — ARK recovery bridge", 1)[1].split(
            "## Phase 9 — INT composition batteries", 1
        )[0]
        self.assertNotIn("- [ ]", phase8)
        self.assertIn("qsol-control-ark-repository-recovery/1", phase8)
        self.assertIn("RECOVERY_PACKAGE != SEMANTIC_AUTHORITY", phase8)
        self.assertIn("RAW_OBJECT_BYTES = CANONICAL", phase8)

    def test_phase8_contract_and_schema_pin_bounds_and_nonclaims(self):
        contract = self.load("ai/ark-repository-recovery-contract.json")
        schema = self.load("schema/ark-repository-recovery.schema.json")
        self.assertEqual(contract["protocol"], "qsol-control-ark-repository-recovery/1")
        self.assertEqual(contract["package_shape"]["maximum_capsules"], 10000)
        self.assertEqual(
            contract["package_shape"]["maximum_capsule_file_bytes"], 75497472
        )
        self.assertTrue(
            contract["privacy"]["strictest_restored_class_recomputed"]
        )
        self.assertTrue(
            contract["reconstruction"]["orphan_canonical_records_rejected"]
        )
        self.assertTrue(
            contract["reconstruction"]["untrusted_container_sizes_bounded_before_read"]
        )
        self.assertEqual(schema["properties"]["capsules"]["maxItems"], 10000)
        item = schema["properties"]["capsules"]["items"]["properties"]
        self.assertEqual(item["size_bytes"]["maximum"], 75497472)
        self.assertFalse(schema["properties"]["requires_webui"]["const"])
        self.assertFalse(
            schema["properties"]["requires_original_search_engine"]["const"]
        )
        self.assertEqual(schema["properties"]["authority"]["const"], "none")

    def test_readme_preserves_phase8_after_later_phases(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Phase 8 ARK repository recovery", readme)
        self.assertIn("PR #11: Phase 7 replay and longitudinal research, merged.", readme)
        self.assertIn("PR #12: Phase 8 repository-level ARK recovery bridge, merged.", readme)
        self.assertIn("docs/ARK-REPOSITORY-RECOVERY.md", readme)
        self.assertIn("RAW_OBJECT_BYTES = CANONICAL", readme)


if __name__ == "__main__":
    unittest.main()
