import copy
import tempfile
import unittest
from pathlib import Path

from storage.control_store import StorageError, canonical_json_bytes
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
            name="phase-1b", created_at=FIXED_TIME, privacy_class="INTERNAL"
        )
        self.snapshot = self.store.storage.update_collection(
            self.collection["collection_id"],
            add=[self.file["file_id"]],
            created_at=EVENT_TIME,
        )

    def tearDown(self):
        self.temp.cleanup()

    def create_run(self, question="What survives the round trip?", **overrides):
        args = dict(
            question=question,
            mode="evidence_only",
            requester_kind="human",
            created_at=FIXED_TIME,
            evidence_state="known",
            oracle_refs=["oracle:event:fixture"],
            file_ids=[self.file["file_id"]],
            collection_id=self.collection["collection_id"],
            snapshot_id=self.snapshot["snapshot_id"],
            replayability="R2",
        )
        args.update(overrides)
        return self.store.create_run(**args)

    def test_lattice_address_matches_contract_axes(self):
        self.assertEqual(lattice_address("question", "derived", "current"), "L[0,1,0]")
        self.assertEqual(lattice_address("response", "derived", "historical"), "L[1,1,1]")
        self.assertEqual(lattice_address("evidence", "observed", "recovery"), "L[2,0,2]")

    def test_run_id_is_content_addressed_and_v2(self):
        first = self.create_run()
        repeated = self.create_run()
        changed = self.create_run("A different question")
        self.assertEqual(first["run_id"], repeated["run_id"])
        self.assertNotEqual(first["run_id"], changed["run_id"])
        self.assertEqual(first["protocol"], "qsol-control-interaction/2")
        self.assertEqual(first["authority"], "storage-only")

    def test_non_unknown_evidence_requires_oracle_provenance(self):
        with self.assertRaisesRegex(StorageError, "ORACLE provenance"):
            self.create_run(oracle_refs=[])
        unknown = self.create_run("unknown", evidence_state="unknown", oracle_refs=[])
        self.assertEqual(unknown["evidence_state"], "unknown")

    def test_question_rejects_obvious_credentials(self):
        with self.assertRaisesRegex(StorageError, "credential marker"):
            self.create_run("token ghp_super_secret")

    def test_run_binds_exact_file_and_collection_snapshot(self):
        run = self.create_run()
        self.assertEqual(run["file_ids"], [self.file["file_id"]])
        self.assertEqual(run["collection_ref"]["snapshot_id"], self.snapshot["snapshot_id"])
        self.assertEqual(self.store.get_run(run["run_id"]), run)

    def test_append_only_event_chain_and_lattice_lineage(self):
        run = self.create_run()
        evidence = self.store.append_event(
            run["run_id"], kind="evidence", payload={"claim": "fixture observation"},
            occurred_at=EVENT_TIME, epistemic_role="observed", temporal_role="current",
            file_ids=[self.file["file_id"]], record_refs=["oracle:event:fixture"],
        )
        response = self.store.append_event(
            run["run_id"], kind="response", payload={"text": "The fixture survives."},
            occurred_at="2026-08-19T08:00:00+09:30", epistemic_role="derived",
            temporal_role="current", parent_event_ids=[evidence["event_id"]],
        )
        events = self.store.list_events(run["run_id"])
        self.assertEqual([event["sequence"] for event in events], [0, 1])
        self.assertEqual(evidence["lattice_address"], "L[2,0,0]")
        self.assertEqual(response["lattice_address"], "L[1,1,0]")

    def test_derived_event_requires_explicit_inputs(self):
        run = self.create_run()
        with self.assertRaisesRegex(StorageError, "explicit input lineage"):
            self.store.append_event(
                run["run_id"], kind="response", payload={"text": "orphan"},
                occurred_at=EVENT_TIME, epistemic_role="derived", temporal_role="current",
                parent_event_ids=[],
            )

    def test_event_payload_rejects_obvious_credentials(self):
        run = self.create_run()
        with self.assertRaisesRegex(StorageError, "credential marker"):
            self.store.append_event(
                run["run_id"], kind="evidence", payload={"token": "Bearer secret"},
                occurred_at=EVENT_TIME, epistemic_role="observed", temporal_role="current",
            )

    def test_model_state_payload_cannot_capture_hidden_reasoning(self):
        run = self.create_run()
        payload = {
            "protocol": "qsol-control-model-state/1",
            "state_id": "sha256:" + "a" * 64,
            "captured_at": EVENT_TIME,
            "model": {"provider": "fixture", "runtime": "fixture", "model_id": "fixture"},
            "execution": {},
            "system": {"control_run_id": run["run_id"]},
            "hidden_chain_of_thought_captured": True,
        }
        with self.assertRaisesRegex(StorageError, "hidden chain-of-thought"):
            self.store.append_event(
                run["run_id"], kind="model_state", payload=payload, occurred_at=EVENT_TIME
            )

    def test_event_parent_must_belong_to_same_run(self):
        first = self.create_run("first")
        second = self.create_run("second")
        parent = self.store.append_event(
            first["run_id"], kind="evidence", payload={"x": 1}, occurred_at=EVENT_TIME,
            epistemic_role="observed", temporal_role="current",
        )
        with self.assertRaisesRegex(StorageError, "different run"):
            self.store.append_event(
                second["run_id"], kind="response", payload={"x": 2}, occurred_at=EVENT_TIME,
                epistemic_role="derived", temporal_role="current",
                parent_event_ids=[parent["event_id"]],
            )

    def test_run_fingerprint_is_deterministic_and_integrity_only(self):
        run = self.create_run()
        self.store.append_event(
            run["run_id"], kind="response", payload={"text": "answer"}, occurred_at=EVENT_TIME,
            epistemic_role="derived", temporal_role="current", record_refs=["run:question"],
        )
        first = self.store.fingerprint_run(run["run_id"])
        second = self.store.fingerprint_run(run["run_id"])
        report = self.store.verify_run(run["run_id"])
        self.assertEqual(first, second)
        self.assertEqual(first["authority"], "integrity-not-truth")
        self.assertEqual(report["fingerprint"], first["fingerprint"])

    def test_verify_reads_bound_object_bytes(self):
        run = self.create_run()
        self.store._verify_bound_objects(run, [])
        object_path = self.store.storage._object_path(self.file["object_id"])
        object_path.write_bytes(b"tampered")
        with self.assertRaisesRegex(StorageError, "verification"):
            self.store.verify_run(run["run_id"])

    def test_existing_run_repairs_missing_empty_head(self):
        run = self.create_run()
        self.store._head_path(run["run_id"]).unlink()
        repeated = self.create_run()
        self.assertEqual(repeated["run_id"], run["run_id"])
        self.assertEqual(self.store.list_events(run["run_id"]), [])

    def test_path_traversal_run_id_is_rejected(self):
        with self.assertRaisesRegex(StorageError, "invalid run_id"):
            self.store.get_run("../../outside")

    def test_import_rejects_duplicate_event_identity(self):
        run = self.create_run()
        self.store.append_event(
            run["run_id"], kind="response", payload={"text": "answer"}, occurred_at=EVENT_TIME,
            epistemic_role="derived", temporal_role="current", record_refs=["run:question"],
        )
        bundle = self.store.export_record_set(run["run_id"])
        bundle["events"].append(copy.deepcopy(bundle["events"][0]))
        with self.assertRaisesRegex(StorageError, "duplicate event identity"):
            self.store.import_record_set(bundle)

    def test_import_rejects_authority_escalation_even_with_rehashed_id(self):
        run = self.create_run()
        bundle = self.store.export_record_set(run["run_id"])
        hostile = copy.deepcopy(bundle)
        hostile["run"]["authority"] = "truth"
        payload = {k: v for k, v in hostile["run"].items() if k != "run_id"}
        hostile["run"]["run_id"] = self.store._identity(payload)
        target = InteractionStore(self.root / "hostile-target")
        target_file = target.storage.put_file(
            "phase 1b evidence", filename="evidence.txt", created_at=FIXED_TIME,
            privacy_class="INTERNAL", retention_class="ARCHIVE",
        )
        target_collection = target.storage.create_collection(
            name="phase-1b", created_at=FIXED_TIME, privacy_class="INTERNAL"
        )
        target.storage.update_collection(
            target_collection["collection_id"], add=[target_file["file_id"]], created_at=EVENT_TIME
        )
        with self.assertRaisesRegex(StorageError, "storage-only"):
            target.import_record_set(hostile)

    def test_record_set_carries_strictest_privacy(self):
        restricted = self.store.storage.put_file(
            "restricted", filename="r.txt", created_at=FIXED_TIME,
            privacy_class="RESTRICTED", retention_class="ARCHIVE",
        )
        run = self.store.create_run(
            question="restricted run", mode="evidence_only", requester_kind="human",
            created_at=FIXED_TIME, evidence_state="unknown", file_ids=[restricted["file_id"]],
            replayability="R3",
        )
        bundle = self.store.export_record_set(run["run_id"])
        self.assertEqual(bundle["privacy_class"], "RESTRICTED")

    def test_lineage_loop_detector_rejects_cycles(self):
        a = "sha256:" + "a" * 64
        b = "sha256:" + "b" * 64
        with self.assertRaisesRegex(StorageError, "lineage loop"):
            InteractionStore._check_parent_dag([
                {"event_id": a, "parent_event_ids": [b]},
                {"event_id": b, "parent_event_ids": [a]},
            ])

    def test_record_set_round_trips_when_dependencies_exist(self):
        run = self.create_run()
        self.store.append_event(
            run["run_id"], kind="evidence", payload={"claim": "fixture observation"},
            occurred_at=EVENT_TIME, epistemic_role="observed", temporal_role="current",
            file_ids=[self.file["file_id"]],
        )
        bundle = self.store.export_record_set(run["run_id"])
        target_temp = tempfile.TemporaryDirectory()
        try:
            target = InteractionStore(target_temp.name)
            target_file = target.storage.put_file(
                "phase 1b evidence", filename="evidence.txt", created_at=FIXED_TIME,
                privacy_class="INTERNAL", retention_class="ARCHIVE",
            )
            target_collection = target.storage.create_collection(
                name="phase-1b", created_at=FIXED_TIME, privacy_class="INTERNAL"
            )
            target_snapshot = target.storage.update_collection(
                target_collection["collection_id"], add=[target_file["file_id"]], created_at=EVENT_TIME
            )
            self.assertEqual(target_snapshot["snapshot_id"], self.snapshot["snapshot_id"])
            report = target.import_record_set(bundle)
            self.assertEqual(report["run_id"], run["run_id"])
            self.assertEqual(target.export_record_set(run["run_id"]), bundle)
        finally:
            target_temp.cleanup()


if __name__ == "__main__":
    unittest.main()
