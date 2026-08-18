import json
import tempfile
import unittest
from pathlib import Path

from storage.ark_recovery_bundle import (
    ArkBundleError,
    build_ark_bundle,
    bundle_privacy_class,
    restore_ark_bundle,
    verify_ark_bundle,
)
from storage.interaction_store import InteractionStore
from storage.restore_capsule import pack_capsule, parse_capsule

FIXED_TIME = "2026-08-19T08:30:00+09:30"
EVENT_TIME = "2026-08-19T08:31:00+09:30"


class ArkMinimumBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = InteractionStore(self.root)
        self.alpha = self.store.storage.put_file(
            "alpha evidence",
            filename="alpha.txt",
            created_at=FIXED_TIME,
            privacy_class="INTERNAL",
            retention_class="ARCHIVE",
        )
        self.beta = self.store.storage.put_file(
            "beta later",
            filename="beta.txt",
            created_at=FIXED_TIME,
            privacy_class="INTERNAL",
            retention_class="ARCHIVE",
        )
        collection = self.store.storage.create_collection(
            name="ark-minimum",
            created_at=FIXED_TIME,
            privacy_class="INTERNAL",
        )
        self.collection_id = collection["collection_id"]
        self.snapshot_one = self.store.storage.update_collection(
            self.collection_id,
            add=[self.alpha["file_id"]],
            created_at=EVENT_TIME,
        )
        self.snapshot_two = self.store.storage.update_collection(
            self.collection_id,
            add=[self.beta["file_id"]],
            created_at="2026-08-19T08:32:00+09:30",
        )
        self.run = self.store.create_run(
            question="Can the exact historical snapshot survive offline?",
            mode="evidence_only",
            requester_kind="human",
            created_at=FIXED_TIME,
            evidence_state="known",
            file_ids=[self.alpha["file_id"]],
            collection_id=self.collection_id,
            snapshot_id=self.snapshot_one["snapshot_id"],
            oracle_refs=["oracle:event:fixture"],
            replayability="R2",
        )
        evidence = self.store.append_event(
            self.run["run_id"],
            kind="evidence",
            payload={"claim": "alpha"},
            occurred_at=EVENT_TIME,
            epistemic_role="observed",
            temporal_role="current",
            file_ids=[self.alpha["file_id"]],
            record_refs=["oracle:event:fixture"],
        )
        self.store.append_event(
            self.run["run_id"],
            kind="response",
            payload={"text": "Recovered from the exact snapshot."},
            occurred_at="2026-08-19T08:33:00+09:30",
            epistemic_role="derived",
            temporal_role="current",
            parent_event_ids=[evidence["event_id"]],
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_bundle_is_deterministic_and_round_trips_offline(self):
        first = build_ark_bundle(self.store, self.run["run_id"])
        second = build_ark_bundle(self.store, self.run["run_id"])
        self.assertEqual(first, second)
        report = verify_ark_bundle(first)
        self.assertEqual(report["status"], "verified")
        self.assertTrue(report["fixed_point"])
        self.assertTrue(report["offline_round_trip"])
        self.assertEqual(report["run_id"], self.run["run_id"])
        self.assertEqual(
            report["collection_snapshot_id"], self.snapshot_one["snapshot_id"]
        )

    def test_recovery_uses_exact_snapshot_not_live_source_head(self):
        capsule = build_ark_bundle(self.store, self.run["run_id"])
        target = self.root / "restored"
        restored = restore_ark_bundle(capsule, target)
        self.assertEqual(restored["run_id"], self.run["run_id"])
        recovered_store = InteractionStore(target)
        recovered_collection = recovered_store.storage.get_collection(self.collection_id)
        self.assertEqual(
            recovered_collection["head_snapshot_id"], self.snapshot_one["snapshot_id"]
        )
        self.assertNotEqual(
            recovered_collection["head_snapshot_id"], self.snapshot_two["snapshot_id"]
        )
        recovered_snapshot = recovered_store.storage.get_collection_snapshot(
            self.collection_id
        )
        self.assertEqual(recovered_snapshot["members"], [self.alpha["file_id"]])
        self.assertEqual(
            recovered_store.storage.read_file(self.alpha["file_id"]),
            b"alpha evidence",
        )

    def test_bundle_contains_no_derived_search_indexes(self):
        capsule = build_ark_bundle(self.store, self.run["run_id"])
        _, entries = parse_capsule(capsule)
        paths = [entry["logical_path"] for entry in entries]
        self.assertFalse(any("indexes" in path for path in paths))
        self.assertIn("CONTROL-RECOVERY.json", paths)
        self.assertIn("lattice/profile.json", paths)

    def test_semantically_incomplete_capsule_is_rejected_even_when_container_is_valid(self):
        capsule = build_ark_bundle(self.store, self.run["run_id"])
        _, entries = parse_capsule(capsule)
        alpha_object = self.alpha["object_id"][7:]
        object_path = f"objects/sha256/{alpha_object[:2]}/{alpha_object}"
        stripped = [
            {
                "logical_path": entry["logical_path"],
                "data": entry["data"],
                "kind": entry["kind"],
                "privacy_class": entry["privacy_class"],
                "recovery_class": entry["recovery_class"],
                "source_ref": entry.get("source_ref"),
            }
            for entry in entries
            if entry["logical_path"] != object_path
        ]
        for entry in stripped:
            if entry["logical_path"] == "CONTROL-RECOVERY.json":
                bootstrap = json.loads(entry["data"].decode("utf-8"))
                bootstrap["required_entry_paths"] = [
                    path for path in bootstrap["required_entry_paths"] if path != object_path
                ]
                bootstrap["object_paths"] = [
                    path for path in bootstrap["object_paths"] if path != object_path
                ]
                entry["data"] = json.dumps(
                    bootstrap,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
        incomplete = pack_capsule(stripped)
        with self.assertRaises((ArkBundleError, ValueError)):
            verify_ark_bundle(incomplete)

    def test_restricted_dependency_propagates_restricted_bundle_class(self):
        restricted = self.store.storage.put_file(
            "restricted evidence",
            filename="restricted.txt",
            created_at=FIXED_TIME,
            privacy_class="RESTRICTED",
            retention_class="ARCHIVE",
        )
        run = self.store.create_run(
            question="restricted?",
            mode="evidence_only",
            requester_kind="human",
            created_at=FIXED_TIME,
            evidence_state="unknown",
            file_ids=[restricted["file_id"]],
            replayability="R3",
        )
        capsule = build_ark_bundle(self.store, run["run_id"])
        self.assertEqual(bundle_privacy_class(capsule), "RESTRICTED")

    def test_restore_refuses_existing_target(self):
        capsule = build_ark_bundle(self.store, self.run["run_id"])
        target = self.root / "already-there"
        target.mkdir()
        with self.assertRaisesRegex(ArkBundleError, "must not already exist"):
            restore_ark_bundle(capsule, target)


if __name__ == "__main__":
    unittest.main()
