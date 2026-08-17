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


if __name__ == "__main__":
    unittest.main()
