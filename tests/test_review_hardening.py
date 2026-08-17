import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from storage.control_store import (
    COLLATION_ID,
    TOKENIZER_ID,
    UNICODE_DATABASE_VERSION,
    ControlStore,
    StorageError,
    canonical_text,
    tokenize_text,
)
from storage.dna_lattice import (
    LEXICOGRAPHIC_TRAVERSAL,
    PHI_GATED_TRAVERSAL,
    PHI_STRIDE,
    decode_projection,
    encode_projection,
)

FIXED_TIME = "2026-08-18T08:30:00+09:30"
ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "storage_cli.py"


class DeterminismHardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = ControlStore(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def put(self, text: str, name: str, privacy: str = "INTERNAL"):
        return self.store.put_file(
            text,
            filename=name,
            created_at=FIXED_TIME,
            privacy_class=privacy,
            retention_class="ARCHIVE",
        )

    def collection(self, name="review", privacy="INTERNAL"):
        return self.store.create_collection(
            name=name,
            created_at=FIXED_TIME,
            privacy_class=privacy,
        )

    def test_unicode_tokenization_contract_is_named_and_canonical(self):
        self.assertEqual(canonical_text("ＡLPHA Straße"), "alpha strasse")
        self.assertEqual(
            tokenize_text("ＡLPHA—Straße café_42;東京"),
            ("alpha", "strasse", "café_42", "東京"),
        )
        record = self.put("ＡLPHA Straße", "unicode.txt")
        collection = self.collection()
        self.store.update_collection(
            collection["collection_id"],
            add=[record["file_id"]],
            created_at="2026-08-18T08:31:00+09:30",
        )
        index = self.store.build_lexical_index(
            collection["collection_id"],
            built_at="2026-08-18T08:32:00+09:30",
        )
        self.assertEqual(index["tokenizer"]["id"], TOKENIZER_ID)
        self.assertEqual(index["tokenizer"]["unicode_database_version"], UNICODE_DATABASE_VERSION)
        self.assertEqual(index["collation"], COLLATION_ID)
        self.assertEqual(
            self.store.search_lexical(collection["collection_id"], "alpha STRASSE")[0]["file_id"],
            record["file_id"],
        )

    def test_equal_scores_tie_break_on_ascii_sha_reference(self):
        left = self.put("same token", "left.txt")
        right = self.put("same token", "right.txt")
        collection = self.collection()
        self.store.update_collection(
            collection["collection_id"],
            add=[right["file_id"], left["file_id"]],
            created_at="2026-08-18T08:31:00+09:30",
        )
        results = self.store.search_lexical(collection["collection_id"], "same token")
        self.assertEqual(
            [row["file_id"] for row in results],
            sorted([left["file_id"], right["file_id"]], key=lambda x: x.encode("ascii")),
        )

    def test_semantic_index_has_explicit_fingerprints_and_verifies_them(self):
        a = self.put("a", "a.txt")
        b = self.put("b", "b.txt")
        collection = self.collection()
        self.store.update_collection(
            collection["collection_id"],
            add=[a["file_id"], b["file_id"]],
            created_at="2026-08-18T08:31:00+09:30",
        )
        index = self.store.register_semantic_index(
            collection["collection_id"],
            vectors={a["file_id"]: [1.0, 0.0], b["file_id"]: [0.0, 1.0]},
            embedding={"provider": "fixture", "model_id": "toy", "revision": "1", "dimensions": 2},
            built_at="2026-08-18T08:32:00+09:30",
        )
        self.assertRegex(index["vectors_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(index["embedding_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(self.store.get_index(index["index_id"]), index)
        path = self.store._index_path(index["index_id"])
        tampered = json.loads(path.read_text(encoding="utf-8"))
        tampered["vectors"][a["file_id"]] = [0.5, 0.5]
        path.write_text(json.dumps(tampered), encoding="utf-8")
        with self.assertRaisesRegex(StorageError, "identity|fingerprint"):
            self.store.get_index(index["index_id"])

    def test_stale_compare_and_swap_update_fails_closed(self):
        item = self.put("x", "x.txt")
        collection = self.collection()
        old_head = collection["head_snapshot_id"]
        first = self.store.update_collection(
            collection["collection_id"],
            add=[item["file_id"]],
            expected_head_snapshot_id=old_head,
            created_at="2026-08-18T08:31:00+09:30",
        )
        self.assertNotEqual(first["snapshot_id"], old_head)
        with self.assertRaisesRegex(StorageError, "HEAD changed"):
            self.store.update_collection(
                collection["collection_id"],
                expected_head_snapshot_id=old_head,
                created_at="2026-08-18T08:32:00+09:30",
            )

    def test_existing_writer_lock_fails_closed(self):
        item = self.put("x", "x.txt")
        collection = self.collection()
        lock = self.store._lock_path(f"collection-head:{collection['collection_id']}")
        lock.write_text("simulated competing writer\n", encoding="utf-8")
        with self.assertRaisesRegex(StorageError, "writer lock"):
            self.store.update_collection(collection["collection_id"], add=[item["file_id"]])

    def test_preview_collection_update_writes_nothing(self):
        item = self.put("x", "x.txt")
        collection = self.collection()
        before = self.store.fingerprint()
        preview = self.store.preview_collection_update(
            collection["collection_id"], add=[item["file_id"]]
        )
        after = self.store.fingerprint()
        self.assertTrue(preview["dry_run"])
        self.assertTrue(preview["changed"])
        self.assertEqual(before, after)

    def test_embedding_descriptor_rejects_obvious_secret_marker(self):
        item = self.put("x", "x.txt")
        collection = self.collection()
        self.store.update_collection(collection["collection_id"], add=[item["file_id"]])
        with self.assertRaisesRegex(StorageError, "credential"):
            self.store.register_semantic_index(
                collection["collection_id"],
                vectors={item["file_id"]: [1.0]},
                embedding={
                    "provider": "fixture",
                    "model_id": "Bearer definitely-a-secret",
                    "revision": "1",
                    "dimensions": 1,
                },
            )


class DnaHardeningTests(unittest.TestCase):
    def test_deterministic_pseudorandom_binary_round_trips_both_paths(self):
        payload = b"".join(hashlib.sha256(f"fixture:{i}".encode()).digest() for i in range(64))
        for traversal in (LEXICOGRAPHIC_TRAVERSAL, PHI_GATED_TRAVERSAL):
            with self.subTest(traversal=traversal):
                projection = encode_projection(payload, traversal_id=traversal)
                decoded = decode_projection(projection)
                self.assertEqual(decoded, payload)
                self.assertEqual(projection["content_sha256"], hashlib.sha256(payload).hexdigest())

    def test_real_repository_file_round_trip(self):
        payload = Path(__file__).read_bytes()
        projection = encode_projection(payload, traversal_id=PHI_GATED_TRAVERSAL)
        self.assertEqual(decode_projection(projection), payload)
        self.assertEqual(projection["traversal_parameters"]["stride"], PHI_STRIDE)
        self.assertEqual(projection["traversal_parameters"]["modulus"], 27)
        self.assertEqual(projection["traversal_parameters"]["rule"], "cell_index(n)=(17*n) mod 27")

    def test_tampered_traversal_parameters_fail_even_with_rehashed_identity(self):
        projection = encode_projection(b"parameter contract")
        projection["traversal_parameters"]["stride"] = 16
        identity_payload = {k: v for k, v in projection.items() if k != "projection_id"}
        raw = json.dumps(identity_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        projection["projection_id"] = "sha256:" + hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(Exception, "traversal parameters"):
            decode_projection(projection)


class CliHardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "store"
        self.work = Path(self.temp.name) / "work"
        self.work.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args: str, expect: int = 0):
        result = subprocess.run(
            [sys.executable, str(CLI), "--root", str(self.root), *args],
            cwd=self.work,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, expect, msg=result.stderr + result.stdout)
        return result

    def test_end_to_end_restricted_dna_export_requires_double_ack_and_is_audited(self):
        source = self.work / "restricted.txt"
        source.write_text("restricted fixture", encoding="utf-8")
        put = self.run_cli(
            "put-file", str(source), "--privacy", "RESTRICTED", "--created-at", FIXED_TIME
        )
        file_id = json.loads(put.stdout)["file_id"]

        denied = self.run_cli("dna-export", file_id, expect=2)
        self.assertIn("--allow-restricted", denied.stderr)

        denied_ack = self.run_cli("dna-export", file_id, "--allow-restricted", expect=2)
        self.assertIn("acknowledge", denied_ack.stderr)

        denied_actor = self.run_cli(
            "dna-export",
            file_id,
            "--allow-restricted",
            "--acknowledge-reversible-sensitive-export",
            expect=2,
        )
        self.assertIn("--actor", denied_actor.stderr)

        preview = self.run_cli(
            "dna-export",
            file_id,
            "--allow-restricted",
            "--acknowledge-reversible-sensitive-export",
            "--actor",
            "reviewer",
            "--dry-run",
        )
        self.assertTrue(json.loads(preview.stdout)["dry_run"])
        self.assertEqual(self.run_cli("audit").stdout.strip(), "[]")

        projection = self.work / "restricted.dna.json"
        self.run_cli(
            "dna-export",
            file_id,
            "--allow-restricted",
            "--acknowledge-reversible-sensitive-export",
            "--actor",
            "reviewer",
            "--output",
            str(projection),
        )
        self.assertTrue(projection.is_file())
        events = json.loads(self.run_cli("audit").stdout)
        self.assertEqual(events[-1]["operation"], "dna-export")
        self.assertEqual(events[-1]["actor"], "reviewer")
        self.assertTrue(events[-1]["details"]["restricted_authorized"])

    def test_update_collection_dry_run_and_fingerprint_audit(self):
        source = self.work / "a.txt"
        source.write_text("alpha", encoding="utf-8")
        file_id = json.loads(
            self.run_cli("put-file", str(source), "--created-at", FIXED_TIME).stdout
        )["file_id"]
        collection = json.loads(
            self.run_cli("create-collection", "demo", "--created-at", FIXED_TIME).stdout
        )
        collection_id = collection["collection_id"]
        preview = json.loads(
            self.run_cli("update-collection", collection_id, "--add", file_id, "--dry-run").stdout
        )
        self.assertTrue(preview["dry_run"])
        self.assertEqual(preview["current_head_snapshot_id"], collection["head_snapshot_id"])
        result = json.loads(
            self.run_cli(
                "update-collection",
                collection_id,
                "--add",
                file_id,
                "--expect-head",
                collection["head_snapshot_id"],
                "--created-at",
                "2026-08-18T08:31:00+09:30",
            ).stdout
        )
        self.assertEqual(result["revision"], 1)
        fingerprint = json.loads(self.run_cli("fingerprint", "--actor", "reviewer").stdout)
        self.assertRegex(fingerprint["fingerprint"], r"^sha256:[0-9a-f]{64}$")
        events = json.loads(self.run_cli("audit").stdout)
        self.assertEqual([event["operation"] for event in events], ["collection-update", "fingerprint"])


if __name__ == "__main__":
    unittest.main()
