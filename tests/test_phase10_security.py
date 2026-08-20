import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import storage.archive_safety as archive_safety
from storage.archive_safety import ArchiveSafetyError, validate_zip_archive
from storage.control_store import ControlStore, StorageError
from tools.file_metadata_audit import (
    MetadataAuditError,
    audit_store,
    canonical_json_bytes,
    reject_secrets,
    sha256_ref,
)

FIXED_TIME = "2026-08-20T12:00:00+00:00"


class Phase10SecurityTests(unittest.TestCase):
    def test_compressed_untrusted_zip_is_default_deny(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "compressed.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("payload.txt", b"A" * 4096)
            with self.assertRaisesRegex(ArchiveSafetyError, "compressed archive member rejected"):
                validate_zip_archive(archive)

    def test_archive_traversal_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "traversal.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as zf:
                zf.writestr("../escape.txt", b"nope")
            with self.assertRaisesRegex(ArchiveSafetyError, "parent segment"):
                validate_zip_archive(archive)

    def test_member_count_is_bounded_before_zipfile_materializes_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "members.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as zf:
                zf.writestr("a.txt", b"a")
                zf.writestr("b.txt", b"b")
            with mock.patch.object(archive_safety, "MAX_MEMBER_COUNT", 1), mock.patch.object(
                archive_safety.zipfile,
                "ZipFile",
                side_effect=AssertionError("ZipFile must not be constructed before member-count rejection"),
            ):
                with self.assertRaisesRegex(ArchiveSafetyError, "member count exceeds limit"):
                    archive_safety.validate_zip_archive(archive)

    def test_existing_write_time_secret_marker_remains_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ControlStore(Path(temp) / "store")
            with self.assertRaisesRegex(StorageError, "credential marker"):
                store.put_file(
                    b"payload",
                    filename="fixture.txt",
                    created_at=FIXED_TIME,
                    metadata={"note": "ghp_SYNTHETIC_DO_NOT_USE"},
                )

    def test_read_import_audit_rejects_rehashed_credential_labelled_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "store"
            store = ControlStore(root)
            record = store.put_file(
                b"payload",
                filename="fixture.txt",
                created_at=FIXED_TIME,
                metadata={"purpose": "synthetic"},
            )
            hostile = dict(record)
            hostile["metadata"] = {"api_key": "synthetic-not-a-real-secret"}
            payload = {key: value for key, value in hostile.items() if key != "file_id"}
            hostile_id = sha256_ref(canonical_json_bytes(payload))
            hostile["file_id"] = hostile_id
            hostile_path = root / "records" / "files" / f"{hostile_id.split(':', 1)[1]}.json"
            hostile_path.write_bytes(canonical_json_bytes(hostile))
            with self.assertRaisesRegex(MetadataAuditError, "credential-labelled"):
                audit_store(root)

    def test_read_import_audit_rejects_mutated_collection_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "store"
            store = ControlStore(root)
            collection = store.create_collection(
                name="research",
                created_at=FIXED_TIME,
                privacy_class="INTERNAL",
                retention_class="ARCHIVE",
            )
            digest = collection["collection_id"].split(":", 1)[1]
            descriptor_path = root / "records" / "collections" / digest / "collection.json"
            descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
            descriptor["name"] = "tampered-without-new-identity"
            descriptor_path.write_bytes(canonical_json_bytes(descriptor))
            with self.assertRaisesRegex(MetadataAuditError, "Collection descriptor content identity mismatch"):
                audit_store(root)

    def test_metadata_audit_rejects_credential_bearing_locator(self):
        with self.assertRaisesRegex(MetadataAuditError, "credential-bearing"):
            reject_secrets({"locator": "https://example.invalid/?access_token=synthetic"})

    def test_metadata_audit_rejects_bearer_credentials_case_insensitively(self):
        for value in ("bearer synthetic-token", "BEARER synthetic-token", "Bearer synthetic-token"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(MetadataAuditError, "bearer credential"):
                    reject_secrets({"note": value})

    def test_threat_model_keeps_remote_multi_user_out_of_scope(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "docs" / "THREAT-MODEL.md").read_text(encoding="utf-8")
        self.assertIn("REMOTE_MULTI_USER_DEPLOYMENT = false", text)
        self.assertIn("COMPRESSED_UNTRUSTED_INPUT != ACCEPTED_BY_DEFAULT", text)
        self.assertIn("SESSION_TOKEN != MULTI_USER_AUTHORIZATION", text)


if __name__ == "__main__":
    unittest.main()
