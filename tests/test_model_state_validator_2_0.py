import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "qsol_control_validate_phase4", ROOT / "tools" / "validate_control.py"
)
validator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validator)


class ModelStateValidator20Tests(unittest.TestCase):
    def load_valid(self):
        return json.loads(
            (ROOT / "examples" / "schema" / "model-state.valid.json").read_text(
                encoding="utf-8"
            )
        )

    def test_valid_2_0_fixture_passes_custom_validator(self):
        validator.validate_model_state_instance(self.load_valid())

    def test_legacy_shape_missing_phase4_gate_fields_is_rejected(self):
        value = self.load_valid()
        for field in (
            "field_provenance",
            "privacy_class",
            "epistemic_boundary",
            "model_mind_captured",
            "authority",
        ):
            value.pop(field)
        with self.assertRaises(ValueError):
            validator.validate_model_state_instance(value)

    def test_content_derived_state_id_is_enforced(self):
        value = self.load_valid()
        value["state_id"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "state_id.*canonical content"):
            validator.validate_model_state_instance(value)

    def test_tool_envelope_consistency_is_enforced(self):
        value = self.load_valid()
        value["execution"]["tool_permission_envelope"]["tools"] = ["shell"]
        with self.assertRaisesRegex(ValueError, "permission lists disagree"):
            validator.validate_model_state_instance(value)


if __name__ == "__main__":
    unittest.main()
