from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storage import concap_bundle as bundle
from storage.restore_capsule import parse_capsule


class PortableConcapBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "source"
        self.root.mkdir()
        (self.root / "content").mkdir()
        (self.root / "restore" / "specs").mkdir(parents=True)
        (self.root / "content" / "context.txt").write_bytes(b"approved portable context\n")
        self.pack_path = self.root / "restore" / "specs" / "core.pack.json"
        self.pack = {
            "protocol": "qsol-control-restore-pack-spec/1",
            "capsule": "core.dat",
            "recovery_class": "NEAR_SHELL",
            "entries": [
                {
                    "logical_path": "context.txt",
                    "source_path": "content/context.txt",
                    "kind": "text",
                    "privacy_class": "RESTRICTED",
                    "recovery_class": "NEAR_SHELL",
                    "source_ref": "QSOLKCB/QSOL-CONTEXT:content/context.txt",
                }
            ],
        }
        self._write_json(self.pack_path, self.pack)
        self.export_path = self.root / "restore" / "CONCAP-EXPORT.spec.json"
        self.export = {
            "protocol": bundle.EXPORT_SPEC_PROTOCOL,
            "schema_version": bundle.SCHEMA_VERSION,
            "bundle_id": "synthetic_portable_context",
            "export_class": "RESTRICTED",
            "sensitive_export_acknowledged": True,
            "bindings": [
                {
                    "role_id": "concap.culture.comedy/1",
                    "pack_spec": "restore/specs/core.pack.json",
                },
                {
                    "role_id": "concap.culture.core/1",
                    "pack_spec": "restore/specs/core.pack.json",
                },
                {
                    "role_id": "concap.identity.core/1",
                    "pack_spec": "restore/specs/core.pack.json",
                },
            ],
            "boundaries": list(bundle.EXPORT_BOUNDARIES),
        }
        self._write_json(self.export_path, self.export)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _write_json(path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _build(self, name: str) -> Path:
        output = Path(self.tmp.name) / name
        report = bundle.build_bundle(
            source_root=self.root,
            export_spec_path=self.export_path,
            output_dir=output,
        )
        self.assertEqual(report["status"], "verified")
        return output

    def test_build_is_byte_deterministic(self):
        first = self._build("bundle-a")
        second = self._build("bundle-b")
        for relative in ("BOOTSTRAP.json", "OBJECTS.json"):
            self.assertEqual((first / relative).read_bytes(), (second / relative).read_bytes())
        first_index = bundle.load_json(first / "OBJECTS.json")
        second_index = bundle.load_json(second / "OBJECTS.json")
        self.assertEqual(first_index, second_index)
        for item in first_index["objects"]:
            relative = item["path"]
            self.assertEqual((first / relative).read_bytes(), (second / relative).read_bytes())

    def test_deterministic_zip_is_byte_identical(self):
        first = self._build("bundle-zip-a")
        second = self._build("bundle-zip-b")
        zip_a = Path(self.tmp.name) / "a.zip"
        zip_b = Path(self.tmp.name) / "b.zip"
        hash_a = bundle.write_deterministic_zip(first, zip_a)
        hash_b = bundle.write_deterministic_zip(second, zip_b)
        self.assertEqual(hash_a, hash_b)
        self.assertEqual(zip_a.read_bytes(), zip_b.read_bytes())

    def test_same_pack_spec_satisfies_multiple_roles_with_one_object(self):
        output = self._build("bundle-dedup")
        index = bundle.load_json(output / "OBJECTS.json")
        self.assertEqual(len(index["objects"]), 1)
        self.assertEqual(len(index["role_bindings"]), 3)
        self.assertEqual(
            {item["object_id"] for item in index["role_bindings"]},
            {index["objects"][0]["object_id"]},
        )

    def test_private_source_ref_is_stripped_from_portable_manifest(self):
        output = self._build("bundle-redaction")
        index = bundle.load_json(output / "OBJECTS.json")
        raw = (output / index["objects"][0]["path"]).read_bytes()
        manifest, entries = parse_capsule(raw)
        self.assertTrue(entries)
        self.assertTrue(all("source_ref" not in item for item in manifest["entries"]))
        self.assertNotIn(b"QSOLKCB/QSOL-CONTEXT", raw)

    def test_public_export_rejects_restricted_source(self):
        public_spec = copy.deepcopy(self.export)
        public_spec["export_class"] = "PUBLIC"
        public_spec["sensitive_export_acknowledged"] = False
        public_path = self.root / "restore" / "PUBLIC.spec.json"
        self._write_json(public_path, public_spec)
        with self.assertRaisesRegex(bundle.ConcapBundleError, "exceeds export class"):
            bundle.build_bundle(
                source_root=self.root,
                export_spec_path=public_path,
                output_dir=Path(self.tmp.name) / "public-output",
            )

    def test_restricted_export_requires_explicit_acknowledgement(self):
        spec = copy.deepcopy(self.export)
        spec["sensitive_export_acknowledged"] = False
        with self.assertRaisesRegex(bundle.ConcapBundleError, "explicit acknowledgement"):
            bundle.validate_export_spec(spec)

    def test_tampered_object_fails_verification(self):
        output = self._build("bundle-tamper")
        index = bundle.load_json(output / "OBJECTS.json")
        target = output / index["objects"][0]["path"]
        raw = bytearray(target.read_bytes())
        raw[-1] ^= 1
        target.write_bytes(raw)
        with self.assertRaisesRegex(bundle.ConcapBundleError, "object hash mismatch"):
            bundle.verify_bundle(output)

    def test_portable_metadata_contains_no_private_repository_or_pack_path(self):
        output = self._build("bundle-no-private-metadata")
        metadata = (output / "BOOTSTRAP.json").read_bytes() + (output / "OBJECTS.json").read_bytes()
        self.assertNotIn(b"QSOLKCB/QSOL-CONTEXT", metadata)
        self.assertNotIn(b"restore/specs/core.pack.json", metadata)
        self.assertNotIn(b"source_ref", metadata)

    def test_projection_hash_detects_role_binding_tamper(self):
        output = self._build("bundle-projection-tamper")
        index_path = output / "OBJECTS.json"
        index = bundle.load_json(index_path)
        index["role_bindings"][0]["role_id"] = "concap.culture.music/1"
        body = dict(index)
        body.pop("index_id")
        index["index_id"] = bundle.digest(body)
        index_path.write_bytes(bundle.canonical_json_bytes(index) + b"\n")
        bootstrap_path = output / "BOOTSTRAP.json"
        bootstrap = bundle.load_json(bootstrap_path)
        bootstrap["object_index_id"] = index["index_id"]
        bootstrap["object_index_sha256"] = bundle.sha256_ref(index_path.read_bytes())
        bootstrap_path.write_bytes(bundle.canonical_json_bytes(bootstrap) + b"\n")
        with self.assertRaisesRegex(bundle.ConcapBundleError, "projection_sha256 mismatch"):
            bundle.verify_bundle(output)

    def test_unexpected_file_fails_closed(self):
        output = self._build("bundle-extra")
        (output / "surprise.txt").write_text("mystery meat\n", encoding="utf-8")
        with self.assertRaisesRegex(bundle.ConcapBundleError, "bundle file set mismatch"):
            bundle.verify_bundle(output)


if __name__ == "__main__":
    unittest.main()
