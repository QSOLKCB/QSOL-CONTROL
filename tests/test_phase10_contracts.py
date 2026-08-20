import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Phase10ContractTests(unittest.TestCase):
    def load(self, relative):
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_manifest_registers_phase10_additively(self):
        manifest = self.load("manifest.json")
        self.assertEqual(manifest["schema_version"], "2.6.0")
        self.assertEqual(manifest["status"]["completed_through_roadmap_phase"], 10)
        self.assertEqual(
            manifest["phase10_hardening_contract"],
            "ai/phase10-hardening-contract.json",
        )
        self.assertEqual(manifest["migration_policy"], "ai/migration-policy.json")
        self.assertEqual(manifest["release_contract"], "ai/release-contract.json")
        self.assertEqual(
            manifest["interfaces"]["release_bundle_cli"],
            "tools/release_bundle.py",
        )
        self.assertEqual(
            manifest["interfaces"]["migration_cli"], "tools/migration.py"
        )
        self.assertEqual(
            manifest["interfaces"]["file_metadata_audit_cli"],
            "tools/file_metadata_audit.py",
        )
        self.assertEqual(manifest["status"]["int_composition"], "implemented-phase-9")
        self.assertEqual(manifest["status"]["ark_repository_recovery"], "implemented-phase-8")
        self.assertTrue(manifest["status"]["webui"].startswith("implemented-phase-5"))

    def test_ai_bootstrap_registers_phase10_without_rewriting_phase6(self):
        bootstrap = self.load("README4AI.md")
        self.assertGreaterEqual(bootstrap["schema_version"], 13)
        self.assertEqual(bootstrap["contracts"]["schema_version"], "2.6.0")
        self.assertEqual(bootstrap["agent_api"]["status"], "implemented_phase6")
        hardening = bootstrap["phase10_hardening"]
        self.assertEqual(hardening["status"], "implemented_phase10")
        self.assertFalse(hardening["remote_multi_user_deployment"])
        self.assertEqual(hardening["compressed_untrusted_import_default"], "deny")
        self.assertFalse(hardening["release_verification_decompresses"])
        self.assertFalse(hardening["migration_in_place_rewrite"])

    def test_phase10_roadmap_is_complete_but_deferred_scope_remains_deferred(self):
        roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
        phase10 = roadmap.split("## Phase 10 — Hardening and release discipline", 1)[1].split(
            "## Deferred / explicitly not promised yet", 1
        )[0]
        deferred = roadmap.split("## Deferred / explicitly not promised yet", 1)[1]
        self.assertNotIn("- [ ]", phase10)
        self.assertIn("- [ ] Remote multi-user deployment.", deferred)
        self.assertIn("MERGED_MAIN != PUBLISHED_RELEASE", phase10)
        self.assertIn("GREEN_CI != RELEASED", phase10)

    def test_phase10_contracts_pin_nonclaims_and_bounds(self):
        hardening = self.load("ai/phase10-hardening-contract.json")
        migration = self.load("ai/migration-policy.json")
        release = self.load("ai/release-contract.json")
        release_schema = self.load("schema/release-manifest.schema.json")
        migration_schema = self.load("schema/migration-receipt.schema.json")
        self.assertEqual(hardening["repository_contract_version"], "2.6.0")
        self.assertFalse(
            hardening["network_browser_threat_model"]["remote_multi_user_deployment"]
        )
        self.assertEqual(
            hardening["archive_safety"]["compressed_untrusted_import_default"],
            "deny",
        )
        self.assertFalse(release["verification"]["decompresses_members"])
        self.assertFalse(release_schema["properties"]["semantic_authority_claimed"]["const"])
        self.assertFalse(migration["rules"]["in_place_rewrite"])
        self.assertTrue(migration["rules"]["source_preserved"])
        self.assertFalse(migration_schema["properties"]["semantic_authority_claimed"]["const"])

    def test_readme_reports_numbered_roadmap_complete_without_claiming_release(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Phase 10 Hardening and release discipline", readme)
        self.assertIn("Repository contract version is `2.6.0`", readme)
        self.assertIn("PR #13: Phase 9 INT composition batteries, merged.", readme)
        self.assertIn("PR #14: Phase 10 hardening and release discipline", readme)
        self.assertIn("numbered roadmap is complete", readme.lower())
        self.assertIn("NUMBERED_ROADMAP_COMPLETE != PUBLISHED_RELEASE", readme)


if __name__ == "__main__":
    unittest.main()
