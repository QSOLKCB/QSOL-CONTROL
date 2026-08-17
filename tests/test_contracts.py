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
        self.assertEqual(report["phase"], 1)
        self.assertEqual(report["lattice_cells"], 27)
        self.assertGreaterEqual(report["documentation_files"], 10)
        self.assertEqual(report["schemas"], 8)
        self.assertEqual(report["schema_examples"], 14)
        self.assertEqual(report["persistent_storage"], "qsol-control-collection/1")
        self.assertEqual(
            report["schema_draft"],
            "https://json-schema.org/draft/2020-12/schema",
        )

    def test_python_minimum_accepts_major_minor(self):
        self.assertEqual(validator.parse_python_minimum("3.11"), (3, 11))

    def test_python_minimum_rejects_patch_component(self):
        with self.assertRaisesRegex(ValueError, "MAJOR.MINOR"):
            validator.parse_python_minimum("3.11.1")

    def test_human_and_ai_callers_have_equal_epistemic_authority(self):
        constitution = validator.load_json(ROOT / "ai" / "constitution.json")
        self.assertIn(
            "HUMAN_CALLER_AUTHORITY == AI_CALLER_AUTHORITY",
            constitution["invariants"],
        )

    def test_search_and_collection_storage_cannot_acquire_truth_authority(self):
        constitution = validator.load_json(ROOT / "ai" / "constitution.json")
        invariants = constitution["invariants"]
        self.assertIn("SEARCH_SCORE != TRUTH", invariants)
        self.assertIn("SEMANTIC_SIMILARITY != EVIDENCE_STRENGTH", invariants)
        self.assertIn("INDEX != CANONICAL_MEMORY", invariants)
        self.assertIn("COLLECTION_MEMBERSHIP != ENDORSEMENT", invariants)

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

    def test_valid_file_fixture_is_accepted(self):
        fixture = validator.load_json(ROOT / "examples" / "schema" / "file-record.valid.json")
        validator.validate_file_instance(fixture)

    def test_forbidden_file_fixture_is_rejected(self):
        fixture = validator.load_json(ROOT / "examples" / "schema" / "file-record.invalid.json")
        with self.assertRaises(ValueError):
            validator.validate_file_instance(fixture)

    def test_valid_collection_fixture_is_accepted(self):
        fixture = validator.load_json(ROOT / "examples" / "schema" / "collection-record.valid.json")
        validator.validate_collection_instance(fixture)

    def test_invalid_collection_fixture_is_rejected(self):
        fixture = validator.load_json(ROOT / "examples" / "schema" / "collection-record.invalid.json")
        with self.assertRaises(ValueError):
            validator.validate_collection_instance(fixture)

    def test_valid_collection_snapshot_fixture_is_accepted(self):
        fixture = validator.load_json(ROOT / "examples" / "schema" / "collection-snapshot.valid.json")
        validator.validate_collection_snapshot_instance(fixture)

    def test_duplicate_collection_snapshot_member_is_rejected(self):
        fixture = validator.load_json(ROOT / "examples" / "schema" / "collection-snapshot.invalid.json")
        with self.assertRaises(ValueError):
            validator.validate_collection_snapshot_instance(fixture)

    def test_valid_search_index_fixture_is_accepted(self):
        fixture = validator.load_json(ROOT / "examples" / "schema" / "search-index.valid.json")
        validator.validate_search_index_instance(fixture)

    def test_search_index_claiming_truth_authority_is_rejected(self):
        fixture = validator.load_json(ROOT / "examples" / "schema" / "search-index.invalid.json")
        with self.assertRaises(ValueError):
            validator.validate_search_index_instance(fixture)

    def test_dna_lattice_schema_is_declared_2020_12(self):
        schema = validator.load_json(ROOT / "schema" / "dna-lattice.schema.json")
        self.assertEqual(
            schema["$schema"],
            "https://json-schema.org/draft/2020-12/schema",
        )
        self.assertEqual(schema["properties"]["authority"]["const"], "none")


if __name__ == "__main__":
    unittest.main()
