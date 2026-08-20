import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Phase9ContractTests(unittest.TestCase):
    def load(self, relative):
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_manifest_registers_phase9_additively(self):
        manifest = self.load("manifest.json")
        self.assertEqual(manifest["schema_version"], "2.5.0")
        self.assertEqual(
            manifest["int_composition_contract"], "ai/int-composition-contract.json"
        )
        self.assertEqual(
            manifest["int_composition_document"], "docs/INT-COMPOSITION.md"
        )
        self.assertEqual(
            manifest["interfaces"]["int_composition_cli"], "tools/int_composition.py"
        )
        self.assertEqual(
            manifest["validation"]["int_composition_command"],
            "python3 tools/int_composition.py validate",
        )
        self.assertEqual(
            manifest["schemas"]["int_composition_report"],
            "schema/int-composition-report.schema.json",
        )
        self.assertEqual(manifest["status"]["completed_through_roadmap_phase"], 9)
        self.assertEqual(manifest["status"]["int_composition"], "implemented-phase-9")
        self.assertFalse(manifest["status"]["int_composition_int_authority_claimed"])
        self.assertFalse(manifest["status"]["int_composition_truth_claimed"])
        self.assertTrue(manifest["status"]["webui"].startswith("implemented-phase-5"))
        self.assertTrue(manifest["status"]["ai_api"].startswith("implemented-phase-6"))
        self.assertEqual(manifest["status"]["replay"], "implemented-phase-7")
        self.assertEqual(
            manifest["status"]["ark_repository_recovery"], "implemented-phase-8"
        )

    def test_ai_bootstrap_registers_phase9_without_rewriting_phase6(self):
        bootstrap = self.load("README4AI.md")
        self.assertEqual(bootstrap["schema_version"], 12)
        self.assertEqual(bootstrap["contracts"]["schema_version"], "2.5.0")
        self.assertEqual(bootstrap["agent_api"]["status"], "implemented_phase6")
        phase9 = bootstrap["int_composition"]
        self.assertEqual(phase9["status"], "implemented_phase9")
        self.assertEqual(phase9["case_count"], 11)
        self.assertEqual(phase9["scope"], "pinned_parent_evidence_only")
        self.assertEqual(phase9["current_parent_compatibility_default"], "not_claimed")
        self.assertFalse(phase9["silent_pin_refresh"])
        self.assertFalse(phase9["int_authority_claimed"])
        self.assertFalse(phase9["truth_claimed"])
        self.assertEqual(bootstrap["authority"]["int_composition"], "none")
        self.assertIn(
            "INTEGRATION_MUST_NOT_INCREASE_SEMANTIC_AUTHORITY",
            bootstrap["core_invariants"],
        )

    def test_phase9_roadmap_is_complete_and_phase10_remains_partial(self):
        roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
        phase9 = roadmap.split("## Phase 9 — INT composition batteries", 1)[1].split(
            "## Phase 10 — Hardening and release discipline", 1
        )[0]
        self.assertNotIn("- [ ]", phase9)
        self.assertIn("qsol-control-int-composition-report/1", phase9)
        self.assertIn("PINNED_PARENT_COMPATIBILITY != CURRENT_PARENT_COMPATIBILITY", phase9)
        phase10 = roadmap.split("## Phase 10 — Hardening and release discipline", 1)[1].split(
            "## Deferred / explicitly not promised yet", 1
        )[0]
        self.assertIn("- [ ]", phase10)

    def test_readme_reports_phase9_complete_and_phase10_next(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Phase 9 INT composition batteries", readme)
        self.assertIn("Repository contract version is `2.5.0`", readme)
        self.assertIn("PR #12: Phase 8 repository-level ARK recovery bridge, merged.", readme)
        self.assertIn("PR #13: Phase 9 INT composition batteries, current implementation branch.", readme)
        self.assertIn("only unfinished numbered roadmap phase", readme)

    def test_contract_and_schema_forbid_authority_and_truth_inheritance(self):
        contract = self.load("ai/int-composition-contract.json")
        schema = self.load("schema/int-composition-report.schema.json")
        self.assertEqual(contract["authority"], "conformance-only")
        self.assertFalse(contract["int_authority_claimed"])
        self.assertFalse(
            contract["methodology_source"]["compatibility_inheritance"]
        )
        self.assertFalse(
            contract["receipts"]["live_parent_compatibility_inferred_from_pins"]
        )
        self.assertFalse(schema["properties"]["int_authority_claimed"]["const"])
        self.assertFalse(schema["properties"]["truth_claimed"]["const"])


if __name__ == "__main__":
    unittest.main()
