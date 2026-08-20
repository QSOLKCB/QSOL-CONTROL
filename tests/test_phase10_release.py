import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "qsol_control_release_bundle", ROOT / "tools" / "release_bundle.py"
)
release = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(release)


class Phase10ReleaseTests(unittest.TestCase):
    def test_two_builds_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as temp:
            left = Path(temp) / "left.zip"
            right = Path(temp) / "right.zip"
            kwargs = {
                "source_root": ROOT,
                "release_version": "1.0.0",
                "source_commit": "0" * 40,
            }
            first = release.build_release(output=left, **kwargs)
            second = release.build_release(output=right, **kwargs)
            self.assertEqual(left.read_bytes(), right.read_bytes())
            self.assertEqual(first["archive_sha256"], second["archive_sha256"])
            self.assertEqual(first["release_id"], second["release_id"])
            self.assertEqual(first["source_tree_sha256"], second["source_tree_sha256"])
            verified = release.verify_release(left)
            self.assertFalse(verified["decompression_performed"])

    def test_release_members_are_stored_and_fixed_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "release.zip"
            release.build_release(
                source_root=ROOT,
                output=archive,
                release_version="1.0.0",
                source_commit="1" * 40,
            )
            with zipfile.ZipFile(archive, "r") as zf:
                infos = zf.infolist()
                self.assertTrue(infos)
                self.assertEqual(zf.comment, b"")
                names = [info.filename for info in infos]
                self.assertEqual(names, sorted(names, key=lambda value: value.encode("utf-8")))
                for info in infos:
                    self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                    self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                    self.assertEqual(info.create_system, 3)
                    self.assertEqual((info.external_attr >> 16) & 0xFFFF, 0o100644)
                    self.assertEqual(info.extra, b"")
                    self.assertEqual(info.comment, b"")

    def test_verifier_rejects_repacked_noncanonical_zip_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            original = Path(temp) / "release.zip"
            repacked = Path(temp) / "repacked.zip"
            release.build_release(
                source_root=ROOT,
                output=original,
                release_version="1.0.0",
                source_commit="3" * 40,
            )
            with zipfile.ZipFile(original, "r") as source:
                payloads = [(name, source.read(name)) for name in source.namelist()]
            with zipfile.ZipFile(repacked, "w", compression=zipfile.ZIP_STORED) as target:
                target.comment = b"not-canonical"
                for name, data in reversed(payloads):
                    info = zipfile.ZipInfo(name, date_time=(2026, 8, 20, 12, 0, 0))
                    info.create_system = 3
                    info.compress_type = zipfile.ZIP_STORED
                    info.external_attr = (0o100777 & 0xFFFF) << 16
                    info.extra = b"\x01\x00\x00\x00"
                    info.comment = b"member-comment"
                    target.writestr(info, data)
            with self.assertRaisesRegex(release.ReleaseError, "canonical|comment|order|metadata"):
                release.verify_release(repacked)

    def test_release_inventory_reserves_archive_overhead(self):
        inventory = json.loads(
            (ROOT / "release" / "release-inventory.json").read_text(encoding="utf-8")
        )
        contract = json.loads(
            (ROOT / "ai" / "release-contract.json").read_text(encoding="utf-8")
        )
        self.assertLess(inventory["max_total_bytes"], contract["bounds"]["archive_bytes"])
        self.assertEqual(
            contract["bounds"]["archive_bytes"] - inventory["max_total_bytes"],
            contract["bounds"]["archive_headroom_bytes"],
        )
        self.assertEqual(contract["bounds"]["source_inventory_bytes"], inventory["max_total_bytes"])

    def test_manifest_rejects_semantic_authority_escalation(self):
        files = [{"path": "README.md", "size_bytes": 1, "sha256": "0" * 64}]
        manifest = release.build_manifest(
            release_version="1.0.0", source_commit="2" * 40, files=files
        )
        manifest["semantic_authority_claimed"] = True
        with self.assertRaisesRegex(release.ReleaseError, "authority"):
            release.validate_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
