import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "qsol_control_int_composition", ROOT / "tools" / "int_composition.py"
)
composition = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(composition)


class IntCompositionTests(unittest.TestCase):
    def exact_observation(self):
        pins = composition.load_json(ROOT / "composition" / "parent-pins.json")
        parents = {}
        for name, row in pins["parents"].items():
            expected_protocol = row["expected"].get("protocol") or row["expected"].get("release_protocol")
            parents[name] = {
                "available": True,
                "commit": row["pinned_commit"],
                "git_blob_sha1": row["artifact"]["git_blob_sha1"],
                "protocol": expected_protocol,
                "schema_version": row["expected"].get("schema_version"),
            }
        return {"protocol": composition.OBSERVED_PROTOCOL, "parents": parents}

    def test_pinned_battery_report_is_deterministic_and_all_cases_pass(self):
        left = composition.run_batteries()
        right = composition.run_batteries()
        self.assertEqual(left, right)
        composition.validate_report(left)
        self.assertEqual(left["compatibility"], "compatible")
        self.assertEqual(left["summary"]["case_count"], 11)
        self.assertEqual(left["summary"]["passed"], 11)
        self.assertEqual(left["summary"]["failed"], 0)
        self.assertEqual(
            left["summary"]["current_parent_compatibility"], "not_claimed"
        )
        self.assertFalse(left["int_authority_claimed"])
        self.assertFalse(left["truth_claimed"])

    def test_parent_receipts_are_exact_pinned_evidence_only(self):
        report = composition.run_batteries()
        for name, receipt in report["parents"].items():
            self.assertEqual(receipt["parent"], name)
            self.assertEqual(receipt["compatibility"], "compatible")
            self.assertEqual(receipt["scope"], "pinned_parent_evidence_only")
            self.assertEqual(receipt["current_parent_compatibility"], "not_claimed")
            self.assertEqual(receipt["authority"], "compatibility-evidence-only")

    def test_exact_current_parent_observation_can_be_classified_no_drift(self):
        report = composition.run_batteries(observed=self.exact_observation())
        observation = report["current_parent_observation"]
        self.assertEqual(observation["compatibility"], "compatible")
        self.assertFalse(observation["requires_review"])
        self.assertTrue(
            all(row["drift"] == "NO_DRIFT" for row in observation["parents"].values())
        )

    def test_content_drift_requires_review_and_is_not_silently_accepted(self):
        observed = self.exact_observation()
        observed["parents"]["oracle"]["git_blob_sha1"] = "0" * 40
        result = composition.classify_observed_parents(
            composition.load_json(ROOT / "composition" / "parent-pins.json"),
            observed,
        )
        self.assertEqual(result["parents"]["oracle"]["drift"], "CONTENT_DRIFT")
        self.assertEqual(result["parents"]["oracle"]["compatibility"], "untested")
        self.assertTrue(result["requires_review"])

    def test_protocol_major_drift_is_incompatible(self):
        observed = self.exact_observation()
        observed["parents"]["oracle"]["commit"] = "1" * 40
        observed["parents"]["oracle"]["git_blob_sha1"] = "2" * 40
        observed["parents"]["oracle"]["protocol"] = "QSOL-ORACLE/2"
        result = composition.classify_observed_parents(
            composition.load_json(ROOT / "composition" / "parent-pins.json"),
            observed,
        )
        self.assertEqual(result["parents"]["oracle"]["drift"], "BREAKING_DRIFT")
        self.assertEqual(result["compatibility"], "incompatible")
        self.assertTrue(result["requires_review"])

    def test_source_unavailable_is_unknown_not_contradicted(self):
        observed = self.exact_observation()
        observed["parents"]["nexus"] = {"available": False}
        result = composition.classify_observed_parents(
            composition.load_json(ROOT / "composition" / "parent-pins.json"),
            observed,
        )
        self.assertEqual(result["parents"]["nexus"]["drift"], "SOURCE_UNAVAILABLE")
        self.assertEqual(result["parents"]["nexus"]["compatibility"], "unknown")
        self.assertTrue(result["requires_review"])

    def test_local_contract_git_blob_pins_are_verified(self):
        pins = composition.load_json(ROOT / "composition" / "parent-pins.json")
        composition.validate_pins(pins)
        for row in pins["local_contracts"].values():
            data = (ROOT / row["path"]).read_bytes()
            self.assertEqual(composition.git_blob_sha1(data), row["git_blob_sha1"])

    def test_case_index_covers_every_phase9_roadmap_battery(self):
        index = composition.load_json(ROOT / "composition" / "cases.json")
        rows = composition.validate_cases(index)
        names = {row["name"] for row in rows}
        self.assertEqual(
            names,
            {
                "control_oracle_compatibility",
                "control_nexus_compatibility",
                "control_thoth_concap_compatibility",
                "authority_non_escalation",
                "stale_parent_handling",
                "vote_evidence_separation",
                "memory_canonical_separation",
                "model_state_identity_separation",
                "collection_index_authority_separation",
                "dna_raw_byte_separation",
                "schema_version_drift",
            },
        )

    def test_report_schema_and_contract_pin_nonclaims(self):
        schema = json.loads(
            (ROOT / "schema" / "int-composition-report.schema.json").read_text(
                encoding="utf-8"
            )
        )
        contract = json.loads(
            (ROOT / "ai" / "int-composition-contract.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(schema["properties"]["int_authority_claimed"]["const"])
        self.assertFalse(schema["properties"]["truth_claimed"]["const"])
        self.assertEqual(contract["authority"], "conformance-only")
        self.assertFalse(contract["int_authority_claimed"])
        self.assertFalse(
            contract["receipts"]["live_parent_compatibility_inferred_from_pins"]
        )


if __name__ == "__main__":
    unittest.main()
