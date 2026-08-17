import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "qsol_control_validate", ROOT / "tools" / "validate_control.py"
)
validator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validator)


class ControlContractTests(unittest.TestCase):
    def test_repository_contracts_validate(self):
        report = validator.validate()
        self.assertEqual(report["status"], "valid")
        self.assertEqual(report["lattice_cells"], 27)
        self.assertGreaterEqual(report["documentation_files"], 10)
        self.assertEqual(report["schemas"], 3)
        self.assertEqual(report["schema_examples"], 6)
        self.assertEqual(
            report["schema_draft"],
            "https://json-schema.org/draft/2020-12/schema",
        )

    def test_human_and_ai_callers_have_equal_epistemic_authority(self):
        constitution = validator.load_json(ROOT / "ai" / "constitution.json")
        self.assertIn(
            "HUMAN_CALLER_AUTHORITY == AI_CALLER_AUTHORITY",
            constitution["invariants"],
        )

    def test_lattice_is_storage_only(self):
        lattice = validator.load_json(ROOT / "ai" / "lattice-contract.json")
        self.assertEqual(lattice["authority"], "storage-only")
        self.assertFalse(lattice["literal_geometric_claim"])

    def test_hidden_chain_of_thought_capture_is_forbidden(self):
        schema = validator.load_json(ROOT / "schema" / "model-state.schema.json")
        field = schema["properties"]["hidden_chain_of_thought_captured"]
        self.assertIs(field["const"], False)

    def test_valid_query_fixture_is_accepted(self):
        fixture = validator.load_json(ROOT / "examples" / "schema" / "control-query.valid.json")
        validator.validate_query_instance(fixture)

    def test_invalid_query_fixture_is_rejected(self):
        fixture = validator.load_json(ROOT / "examples" / "schema" / "control-query.invalid.json")
        with self.assertRaises(ValueError):
            validator.validate_query_instance(fixture)

    def test_valid_interaction_fixture_is_accepted(self):
        fixture = validator.load_json(ROOT / "examples" / "schema" / "interaction-record.valid.json")
        validator.validate_interaction_instance(fixture)

    def test_invalid_interaction_fixture_is_rejected(self):
        fixture = validator.load_json(ROOT / "examples" / "schema" / "interaction-record.invalid.json")
        with self.assertRaises(ValueError):
            validator.validate_interaction_instance(fixture)

    def test_valid_model_state_fixture_is_accepted(self):
        fixture = validator.load_json(ROOT / "examples" / "schema" / "model-state.valid.json")
        validator.validate_model_state_instance(fixture)

    def test_hidden_chain_of_thought_fixture_is_rejected(self):
        fixture = validator.load_json(ROOT / "examples" / "schema" / "model-state.invalid.json")
        with self.assertRaises(ValueError):
            validator.validate_model_state_instance(fixture)


if __name__ == "__main__":
    unittest.main()
