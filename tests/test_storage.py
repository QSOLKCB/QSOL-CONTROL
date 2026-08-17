import tempfile
import unittest
from pathlib import Path

from storage.control_store import ControlStore, StorageError

FIXED_TIME = "2026-08-18T07:44:00+09:30"


class PersistentStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = ControlStore(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def put_text(self, text: str, filename: str, *, privacy_class: str = "INTERNAL"):
        return self.store.put_file(
            text,
            filename=filename,
            created_at=FIXED_TIME,
            privacy_class=privacy_class,
            retention_class="ARCHIVE",
        )

    def create_collection(self, name: str = "research", *, privacy_class: str = "INTERNAL"):
        return self.store.create_collection(
            name=name,
            created_at=FIXED_TIME,
            privacy_class=privacy_class,
        )

    def test_file_bytes_are_content_addressed_and_metadata_is_immutable(self):
        first = self.put_text("same bytes", "first.txt")
        repeated = self.put_text("same bytes", "first.txt")
        renamed = self.put_text("same bytes", "renamed.txt")
        self.assertEqual(first["file_id"], repeated["file_id"])
        self.assertEqual(first["object_id"], renamed["object_id"])
        self.assertNotEqual(first["file_id"], renamed["file_id"])
        self.assertEqual(self.store.read_file(first["file_id"]), b"same bytes")

    def test_forbidden_privacy_class_cannot_enter_durable_store(self):
        with self.assertRaisesRegex(StorageError, "FORBIDDEN"):
            self.put_text("do not persist", "secret.txt", privacy_class="FORBIDDEN")

    def test_collection_membership_creates_immutable_snapshots(self):
        alpha = self.put_text("alpha", "alpha.txt")
        beta = self.put_text("beta", "beta.txt")
        collection = self.create_collection()
        initial = self.store.get_collection_snapshot(collection["collection_id"])
        updated = self.store.update_collection(
            collection["collection_id"],
            add=[beta["file_id"], alpha["file_id"]],
            created_at="2026-08-18T07:45:00+09:30",
        )
        self.assertEqual(initial["revision"], 0)
        self.assertEqual(initial["members"], [])
        self.assertEqual(updated["revision"], 1)
        self.assertEqual(updated["previous_snapshot_id"], initial["snapshot_id"])
        self.assertEqual(updated["members"], sorted([alpha["file_id"], beta["file_id"]]))
        reread_initial = self.store.get_collection_snapshot(
            collection["collection_id"], initial["snapshot_id"]
        )
        self.assertEqual(reread_initial, initial)

    def test_collection_update_rejects_unknown_removal(self):
        alpha = self.put_text("alpha", "alpha.txt")
        collection = self.create_collection()
        with self.assertRaisesRegex(StorageError, "non-member"):
            self.store.update_collection(collection["collection_id"], remove=[alpha["file_id"]])

    def test_public_collection_rejects_internal_file(self):
        internal = self.put_text("internal", "internal.txt", privacy_class="INTERNAL")
        collection = self.create_collection("public", privacy_class="PUBLIC")
        with self.assertRaisesRegex(StorageError, "more-restricted"):
            self.store.update_collection(collection["collection_id"], add=[internal["file_id"]])

    def test_internal_collection_rejects_restricted_file(self):
        restricted = self.put_text("restricted", "restricted.txt", privacy_class="RESTRICTED")
        collection = self.create_collection("internal", privacy_class="INTERNAL")
        with self.assertRaisesRegex(StorageError, "more-restricted"):
            self.store.update_collection(collection["collection_id"], add=[restricted["file_id"]])

    def test_restricted_collection_may_contain_less_restricted_files(self):
        public = self.put_text("public", "public.txt", privacy_class="PUBLIC")
        internal = self.put_text("internal", "internal.txt", privacy_class="INTERNAL")
        restricted = self.put_text("restricted", "restricted.txt", privacy_class="RESTRICTED")
        collection = self.create_collection("restricted", privacy_class="RESTRICTED")
        snapshot = self.store.update_collection(
            collection["collection_id"],
            add=[public["file_id"], internal["file_id"], restricted["file_id"]],
            created_at="2026-08-18T07:45:00+09:30",
        )
        self.assertEqual(len(snapshot["members"]), 3)

    def test_lexical_search_is_deterministic_and_not_truth_scoring(self):
        apple = self.put_text("apple orchard fruit apple", "apple.txt")
        quantum = self.put_text("quantum entanglement bell experiment", "quantum.txt")
        collection = self.create_collection()
        self.store.update_collection(
            collection["collection_id"],
            add=[apple["file_id"], quantum["file_id"]],
            created_at="2026-08-18T07:45:00+09:30",
        )
        index = self.store.build_lexical_index(
            collection["collection_id"], built_at="2026-08-18T07:46:00+09:30"
        )
        results = self.store.search_lexical(collection["collection_id"], "bell quantum")
        self.assertEqual(results[0]["file_id"], quantum["file_id"])
        self.assertEqual(results[0]["index_id"], index["index_id"])
        self.assertEqual(
            results[0]["score_meaning"], "retrieval_similarity_not_truth_or_evidence_strength"
        )

    def test_semantic_index_can_use_external_vectors_without_owning_embedding_generation(self):
        cat = self.put_text("cat", "cat.txt")
        rocket = self.put_text("rocket", "rocket.txt")
        collection = self.create_collection()
        self.store.update_collection(
            collection["collection_id"],
            add=[cat["file_id"], rocket["file_id"]],
            created_at="2026-08-18T07:45:00+09:30",
        )
        index = self.store.register_semantic_index(
            collection["collection_id"],
            vectors={cat["file_id"]: [1.0, 0.0], rocket["file_id"]: [0.0, 1.0]},
            embedding={
                "provider": "fixture",
                "model_id": "toy-embedding",
                "revision": "1",
                "dimensions": 2,
            },
            built_at="2026-08-18T07:46:00+09:30",
        )
        results = self.store.search_semantic(collection["collection_id"], [0.1, 0.9])
        self.assertEqual(results[0]["file_id"], rocket["file_id"])
        self.assertEqual(results[0]["index_id"], index["index_id"])
        self.assertEqual(
            results[0]["score_meaning"], "semantic_similarity_not_truth_or_evidence_strength"
        )

    def test_semantic_index_fails_closed_when_collection_snapshot_changes(self):
        alpha = self.put_text("alpha", "alpha.txt")
        beta = self.put_text("beta", "beta.txt")
        collection = self.create_collection()
        self.store.update_collection(
            collection["collection_id"],
            add=[alpha["file_id"]],
            created_at="2026-08-18T07:45:00+09:30",
        )
        self.store.register_semantic_index(
            collection["collection_id"],
            vectors={alpha["file_id"]: [1.0, 0.0]},
            embedding={
                "provider": "fixture",
                "model_id": "toy-embedding",
                "revision": "1",
                "dimensions": 2,
            },
            built_at="2026-08-18T07:46:00+09:30",
        )
        self.store.update_collection(
            collection["collection_id"],
            add=[beta["file_id"]],
            created_at="2026-08-18T07:47:00+09:30",
        )
        with self.assertRaisesRegex(StorageError, "stale"):
            self.store.search_semantic(collection["collection_id"], [1.0, 0.0])

    def test_verify_and_fingerprint_cover_canonical_state(self):
        alpha = self.put_text("alpha", "alpha.txt")
        collection = self.create_collection()
        self.store.update_collection(
            collection["collection_id"],
            add=[alpha["file_id"]],
            created_at="2026-08-18T07:45:00+09:30",
        )
        first = self.store.fingerprint()
        second = self.store.fingerprint()
        report = self.store.verify()
        self.assertEqual(first, second)
        self.assertEqual(report["status"], "valid")
        self.assertEqual(report["files"], 1)
        self.assertEqual(report["collections"], 1)
        self.assertEqual(report["snapshots"], 2)
        self.assertEqual(report["fingerprint"], first["fingerprint"])

    def test_corrupted_object_is_detected(self):
        record = self.put_text("uncorrupted", "example.txt")
        object_path = self.store._object_path(record["object_id"])
        object_path.write_bytes(b"tampered")
        with self.assertRaisesRegex(StorageError, "verification"):
            self.store.read_file(record["file_id"])


if __name__ == "__main__":
    unittest.main()
