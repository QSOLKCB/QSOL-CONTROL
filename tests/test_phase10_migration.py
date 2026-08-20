import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "qsol_control_migration", ROOT / "tools" / "migration.py"
)
migration = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(migration)


class Phase10MigrationTests(unittest.TestCase):
    def test_policy_is_valid_and_targets_phase10_contract(self):
        policy = migration.load_policy()
        migration.validate_policy(policy)
        self.assertEqual(policy["current_contract_version"], "2.6.0")
        self.assertFalse(policy["rules"]["in_place_rewrite"])
        self.assertTrue(policy["rules"]["source_preserved"])

    def test_adjacent_upgrade_is_deterministic_and_source_preserving(self):
        left = migration.plan_migration("2.5.0", "2.6.0")
        right = migration.plan_migration("2.5.0", "2.6.0")
        self.assertEqual(left, right)
        migration.validate_receipt(left)
        self.assertEqual(left["status"], "planned")
        self.assertEqual(len(left["steps"]), 1)
        self.assertTrue(left["source_preserved"])
        self.assertFalse(left["in_place_rewrite"])
        self.assertFalse(left["canonical_store_rewrite_required"])
        self.assertFalse(left["semantic_authority_claimed"])

    def test_multi_step_upgrade_uses_declared_chain(self):
        receipt = migration.plan_migration("2.0.0", "2.6.0")
        self.assertEqual(len(receipt["steps"]), 6)
        self.assertEqual(receipt["steps"][0]["from"], "2.0.0")
        self.assertEqual(receipt["steps"][-1]["to"], "2.6.0")

    def test_same_version_is_no_op(self):
        receipt = migration.plan_migration("2.6.0", "2.6.0")
        self.assertEqual(receipt["status"], "no_op")
        self.assertEqual(receipt["steps"], [])

    def test_downgrade_and_unknown_major_fail_closed(self):
        with self.assertRaisesRegex(migration.MigrationError, "downgrade"):
            migration.plan_migration("2.6.0", "2.5.0")
        with self.assertRaisesRegex(migration.MigrationError, "unknown/breaking"):
            migration.plan_migration("1.9.0", "2.6.0")
        with self.assertRaisesRegex(migration.MigrationError, "unknown/breaking"):
            migration.plan_migration("3.0.0", "2.6.0")


if __name__ == "__main__":
    unittest.main()
