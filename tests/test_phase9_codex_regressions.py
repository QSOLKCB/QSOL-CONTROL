import contextlib
import copy
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "qsol_control_int_composition_codex", ROOT / "tools" / "int_composition.py"
)
composition = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(composition)


class Phase9CodexRegressionTests(unittest.TestCase):
    def pins(self):
        return composition.load_json(ROOT / "composition" / "parent-pins.json")

    def exact_observation(self):
        pins = self.pins()
        parents = {}
        for name, row in pins["parents"].items():
            expected = row["expected"]
            parents[name] = {
                "available": True,
                "commit": row["pinned_commit"],
                "git_blob_sha1": row["artifact"]["git_blob_sha1"],
                "protocol": expected.get("protocol") or expected.get("release_protocol"),
                "schema_version": expected.get("schema_version"),
            }
        return {"protocol": composition.OBSERVED_PROTOCOL, "parents": parents}

    def write_observed(self, value):
        temp = tempfile.TemporaryDirectory()
        path = Path(temp.name) / "observed.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return temp, path

    def test_final_protocol_component_is_used_for_thoth_major(self):
        self.assertEqual(
            composition._major("QSOL-THOTH/CONCAP-COMPATIBILITY/2"), 2
        )
        observed = self.exact_observation()
        observed["parents"]["thoth"]["commit"] = "1" * 40
        observed["parents"]["thoth"]["git_blob_sha1"] = "2" * 40
        observed["parents"]["thoth"]["protocol"] = (
            "QSOL-THOTH/CONCAP-COMPATIBILITY/2"
        )
        result = composition.classify_observed_parents(self.pins(), observed)
        self.assertEqual(result["parents"]["thoth"]["drift"], "BREAKING_DRIFT")
        self.assertEqual(result["compatibility"], "incompatible")

    def test_exact_identity_with_contradictory_metadata_is_rejected(self):
        observed = self.exact_observation()
        observed["parents"]["oracle"]["protocol"] = "QSOL-ORACLE/2"
        with self.assertRaisesRegex(composition.CompositionError, "contradicts pinned"):
            composition.classify_observed_parents(self.pins(), observed)

        observed = self.exact_observation()
        observed["parents"]["nexus"]["schema_version"] = 2
        with self.assertRaisesRegex(composition.CompositionError, "contradicts pinned"):
            composition.classify_observed_parents(self.pins(), observed)

    def test_int_methodology_identity_fields_are_validated(self):
        pins = self.pins()
        broken = copy.deepcopy(pins)
        broken["int_methodology"]["pinned_commit"] = "not-a-commit"
        with self.assertRaises(composition.CompositionError):
            composition.validate_pins(broken)

        broken = copy.deepcopy(pins)
        del broken["int_methodology"]["artifact"]["git_blob_sha1"]
        with self.assertRaises(composition.CompositionError):
            composition.validate_pins(broken)

        broken = copy.deepcopy(pins)
        broken["int_methodology"]["artifact"]["path"] = "../escape.json"
        with self.assertRaises(composition.CompositionError):
            composition.validate_pins(broken)

    def test_unavailable_parents_preserve_unknown_aggregate(self):
        observed = {
            "protocol": composition.OBSERVED_PROTOCOL,
            "parents": {
                "oracle": {"available": False},
                "nexus": {"available": False},
                "thoth": {"available": False},
            },
        }
        result = composition.classify_observed_parents(self.pins(), observed)
        self.assertEqual(result["compatibility"], "unknown")
        self.assertTrue(result["requires_review"])
        self.assertTrue(
            all(row["compatibility"] == "unknown" for row in result["parents"].values())
        )

    def test_failure_report_is_structurally_valid_and_emitted(self):
        observed = self.exact_observation()
        observed["parents"]["oracle"]["commit"] = "1" * 40
        observed["parents"]["oracle"]["git_blob_sha1"] = "2" * 40
        observed["parents"]["oracle"]["protocol"] = "QSOL-ORACLE/2"
        report = composition.run_batteries(observed=observed)
        self.assertEqual(report["compatibility"], "incompatible")
        self.assertGreater(report["summary"]["failed"], 0)
        composition.validate_report(report)

        temp, path = self.write_observed(observed)
        try:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = composition.main(["run", "--observed-parents", str(path), "--json"])
            emitted = json.loads(stdout.getvalue())
        finally:
            temp.cleanup()
        self.assertEqual(code, 1)
        self.assertEqual(emitted["compatibility"], "incompatible")
        self.assertGreater(emitted["summary"]["failed"], 0)

    def test_validate_returns_review_required_for_unresolved_drift(self):
        observed = self.exact_observation()
        observed["parents"]["oracle"]["git_blob_sha1"] = "0" * 40
        temp, path = self.write_observed(observed)
        try:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = composition.main(["validate", "--observed-parents", str(path)])
            result = json.loads(stdout.getvalue())
        finally:
            temp.cleanup()
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "review_required")
        self.assertEqual(result["current_parent_compatibility"], "untested")
        self.assertTrue(result["requires_review"])


if __name__ == "__main__":
    unittest.main()
