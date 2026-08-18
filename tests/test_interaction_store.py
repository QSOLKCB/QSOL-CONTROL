import copy
import tempfile
import unittest
from pathlib import Path

from storage.control_store import StorageError
from storage.interaction_store import InteractionStore, lattice_address

FIXED_TIME = "2026-08-19T07:58:00+09:30"
EVENT_TIME = "2026-08-19T07:59:00+09:30"


class InteractionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = InteractionStore(self.root)
        self.file = self.store.storage.put_file(
            "phase 1b evidence",
            filename="evidence.txt",
            created_at=FIXED_TIME,
            privacy_class="INTERNAL",
            retention_class="ARCHIVE",
        )
        self.collection = self.store.storage.create_collection(
            name="phase-1b",
            created_at=FIXED_TIME,
            privacy_class="INTERNAL",
        )
        self.snapshot = self.store.storage.update_collection(
            self.collection["collection_id"],
            add=[self.file["file_id"]],
            created_at=EVENT_TIME,
        )

    def tearDown(self):
        self.temp.cleanup()

    def create_run(self, question="What survives the round trip?"):
        return self.store.create_run(
            question=question,
            mode="evidence_only",
            requester_kind="human",
            created_at=FIXED_TIME,
            evidence_state="known",
            file_ids=[self.file["file_id"]],
            collection_id=self.collection["collection_id"],
            snapshot_id=self.snapshot["snapshot_id"],
            replayability="R2",
        )

    def test_lattice_address_matches_contract_axes(self):
        self.assertEqual(lattice_address("question", "derived", "current"), "L[0,1,0]")
        self.assertEqual(lattice_address("response", "derived", "historical"), "L[1,1,1]")
        self.assertEqual(lattice_address("evidence", "observed", "recovery"), "L[2,0,2]")

    def test_run_id_is_content_addressed_and_stable(self):
        first = self.create_run()
        repeated = self.create_run()
        changed = self.create_run("A different question")
        self.assertEqual(first["run_id"], repeated["run_id"])
        self.assertNotEqual(first["run_id"], changed["run_id"])
        self.assertEqual(first["question"]["lattice_address"], "L[0,1,0]")

    def test_run_binds_exact_file_and_collection_snapshot(self):
        run = self.create_run()
        self.assertEqual(run["file_ids"], [self.file["file_id"]])
        self.assertEqual(
            run["collection_ref"],
            {
                "collection_id": self.collection["collection_id"],
                "snapshot_id": self.snapshot["snapshot_id"],
            },
        )
        reread = self.store.get_run(run["run_id"])
        self.assertEqual(reread, run)

    def test_append_only_event_chain_and_lattice_lineage(self):
        run = self.create_run()
        evidence = self.store.append_event(
            run["run_id"],
            kind="evidence",
            payload={"claim": "fixture observation"},
            occurred_at=EVENT_TIME,
            epistemic_role="observed",
            temporal_role="current",
            file_ids=[self.file["file_id"]],
            record_refs=["fixture:oracle-event-1"],
        )
        response = self.store.append_event(
            run["run_id"],
            kind="response",
            payload={"text": "The fixture survives."},
            occurred_at="2026-08-19T08:00:00+09:30",
            epistemic_role="derived",
            temporal_role="current",
            parent_event_ids=[evidence["event_id"]],
        )
        events = self.store.list_events(run["run_id"])
        self.assertEqual([event["sequence"] for event in events], [0, 1])
        self.assertEqual(evidence["lattice_address"], "L[2,0,0]")
        self.assertEqual(response["lattice_address"], "L[1,1,0]")
        self.assertEqual(response["previous_event_id"], evidence["event_id"])
        self.assertEqual(response["parent_event_ids"], [evidence["event_id"]])

    def test_receipt_event_cannot_invent_qre_lattice_role(self):
        run = self.create_run()
        with self.assertRaisesRegex(StorageError, "do not use"):
            self.store.append_event(
                run["run_id"],
                kind="receipt",
                payload={"receipt": "fixture"},
                occurred_at=EVENT_TIME,
                epistemic_role="observed",
                temporal_role="current",
            )

    def test_event_parent_must_belong_to_same_run(self):
        first = self.create_run("first")
        second = self.create_run("second")
        parent = self.store.append_event(
            first["run_id"],
            kind="evidence",
            payload={"x": 1},
            occurred_at=EVENT_TIME,
            epistemic_role="observed",
            temporal_role="current",
        )
        with self.assertRaisesRegex(StorageError, "different run"):
            self.store.append_event(
                second["run_id"],
                kind="response",
                payload={"x": 2},
                occurred_at=EVENT_TIME,
                epistemic_role="derived",
                temporal_role="current",
                parent_event_ids=[parent["event_id"]],
            )

    def test_run_fingerprint_is_deterministic_and_integrity_only(self):
        run = self.create_run()
        self.store.append_event(
            run["run_id"],
            kind="response",
            payload={"text": "answer"},
            occurred_at=EVENT_TIME,
            epistemic_role="derived",
            temporal_role="current",
        )
        first = self.store.fingerprint_run(run["run_id"])
        second = self.store.fingerprint_run(run["run_id"])
        report = self.store.verify_run(run["run_id"])
        self.assertEqual(first, second)
        self.assertEqual(first["authority"], "integrity-not-truth")
        self.assertEqual(report["status"], "valid")
        self.assertEqual(report["fingerprint"], first["fingerprint"])

    def test_corrupted_event_is_detected(self):
        run = self.create_run()
        event = self.store.append_event(
            run["run_id"],
            kind="response",
            payload={"text": "untampered"},
            occurred_at=EVENT_TIME,
            epistemic_role="derived",
            temporal_role="current",
        )
        path = self.store._event_path(event["event_id"])
        path.write_text('{"event_id":"sha256:' + "0" * 64 + '"}', encoding="utf-8")
        with self.assertRaises(StorageError):
            self.store.verify_run(run["run_id"])

    def test_path_traversal_run_id_is_rejected(self):
        with self.assertRaisesRegex(StorageError, "invalid run_id"):
            self.store.get_run("../../outside")
        self.assertFalse((self.root.parent / "outside").exists())

    def test_import_rejects_duplicate_event_identity(self):
        run = self.create_run()
        self.store.append_event(
            run["run_id"],
            kind="response",
            payload={"text": "answer"},
            occurred_at=EVENT_TIME,
            epistemic_role="derived",
            temporal_role="current",
        )
        bundle = self.store.export_record_set(run["run_id"])
        bundle["events"].append(copy.deepcopy(bundle["events"][0]))
        with self.assertRaisesRegex(StorageError, "duplicate event identity"):
            self.store.import_record_set(bundle)

    def test_import_rejects_malformed_run_identity_before_write(self):
        run = self.create_run()
        bundle = self.store.export_record_set(run["run_id"])
        malformed = copy.deepcopy(bundle)
        malformed["run"]["run_id"] = "../../escape"
        other = InteractionStore(self.root / "import-target")
        with self.assertRaisesRegex(StorageError, "invalid run_id"):
            other.import_record_set(malformed)
        self.assertEqual(list(other.runs.glob("*.json")), [])

    def test_lineage_loop_detector_rejects_cycles(self):
        a = "sha256:" + "a" * 64
        b = "sha256:" + "b" * 64
        with self.assertRaisesRegex(StorageError, "lineage loop"):
            InteractionStore._check_parent_dag(
                [
                    {"event_id": a, "parent_event_ids": [b]},
                    {"event_id": b, "parent_event_ids": [a]},
                ]
            )

    def test_record_set_round_trips_when_canonical_dependencies_exist(self):
        run = self.create_run()
        self.store.append_event(
            run["run_id"],
            kind="evidence",
            payload={"claim": "fixture observation"},
            occurred_at=EVENT_TIME,
            epistemic_role="observed",
            temporal_role="current",
            file_ids=[self.file["file_id"]],
        )
        self.store.append_event(
            run["run_id"],
            kind="response",
            payload={"text": "verified response"},
            occurred_at="2026-08-19T08:00:00+09:30",
            epistemic_role="derived",
            temporal_role="current",
        )
        bundle = self.store.export_record_set(run["run_id"])

        target_temp = tempfile.TemporaryDirectory()
        try:
            target = InteractionStore(target_temp.name)
            target_file = target.storage.put_file(
                "phase 1b evidence",
                filename="evidence.txt",
                created_at=FIXED_TIME,
                privacy_class="INTERNAL",
                retention_class="ARCHIVE",
            )
            target_collection = target.storage.create_collection(
                name="phase-1b",
                created_at=FIXED_TIME,
                privacy_class="INTERNAL",
            )
            target_snapshot = target.storage.update_collection(
                target_collection["collection_id"],
                add=[target_file["file_id"]],
                created_at=EVENT_TIME,
            )
            self.assertEqual(target_file["file_id"], self.file["file_id"])
            self.assertEqual(target_collection["collection_id"], self.collection["collection_id"])
            self.assertEqual(target_snapshot["snapshot_id"], self.snapshot["snapshot_id"])

            report = target.import_record_set(bundle)
            self.assertEqual(report["run_id"], run["run_id"])
            self.assertEqual(target.export_record_set(run["run_id"]), bundle)
        finally:
            target_temp.cleanup()


if __name__ == "__main__":
    unittest.main()
