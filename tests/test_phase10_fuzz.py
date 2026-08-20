import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "qsol_control_adversarial_storage", ROOT / "tools" / "adversarial_storage.py"
)
adversarial = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(adversarial)


class Phase10AdversarialStorageTests(unittest.TestCase):
    def test_battery_is_deterministic_and_green(self):
        left = adversarial.run_battery(seed=adversarial.DEFAULT_SEED, iterations=48)
        right = adversarial.run_battery(seed=adversarial.DEFAULT_SEED, iterations=48)
        self.assertEqual(left, right)
        self.assertEqual(left["status"], "pass")
        self.assertEqual(left["failed"], 0)
        self.assertGreater(left["passed"], 48)
        self.assertFalse(left["truth_claimed"])

    def test_iteration_bounds_fail_closed(self):
        with self.assertRaises(ValueError):
            adversarial.run_battery(iterations=0)
        with self.assertRaises(ValueError):
            adversarial.run_battery(iterations=adversarial.MAX_ITERATIONS + 1)


if __name__ == "__main__":
    unittest.main()
