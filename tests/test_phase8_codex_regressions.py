import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from storage import ark_repository_bundle as recovery
from storage.ark_repository_bundle import ArkRepositoryBundleError
from storage.control_store import ControlStore, canonical_json_bytes, sha256_ref
from storage.replay_store import ReplayError, ReplayStore
from webui.common import WebUIConfig
from webui.runtime import ControlWebUIRuntime

ROOT = Path(__file__).resolve().parents[1]
TIME = "2026-08-20T20:00:00+09:30"


class Phase8CodexRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.store_root = self.base / "store"
        self.store = ControlStore(self.store_root)

    def tearDown(self):
        self.temp.cleanup()

    def _file(self, *, privacy="INTERNAL", content=b"phase8"):
        return self.store.put_file(
            content,
            filename="fixture.bin",
            media_type="application/octet-stream",
            created_at=TIME,
            privacy_class=privacy,
            retention_class="ARCHIVE",
        )

    @staticmethod
    def _rewrite_bootstrap(package: Path, mutate):
        path = package / recovery.BOOTSTRAP_NAME
        value = json.loads(path.read_text(encoding="utf-8"))
        mutate(value)
        basis = {key: item for key, item in value.items() if key != "package_id"}
        value["package_id"] = sha256_ref(canonical_json_bytes(basis))
        path.write_bytes(canonical_json_bytes(value))

    def test_missing_source_root_fails_without_creating_it(self):
        missing = self.base / "typo-store"
        with self.assertRaises(ArkRepositoryBundleError):
            recovery.build_repository_recovery_package(
                missing, self.base / "package", repository_root=ROOT
            )
        self.assertFalse(missing.exists())

    def test_rehashed_privacy_downgrade_is_rejected(self):
        self._file(privacy="RESTRICTED")
        package = self.base / "package"
        recovery.build_repository_recovery_package(
            self.store_root, package, repository_root=ROOT
        )
        self._rewrite_bootstrap(
            package, lambda value: value.__setitem__("privacy_class", "INTERNAL")
        )
        with self.assertRaises(ArkRepositoryBundleError):
            recovery.verify_repository_recovery_package(package)

    def test_authority_escalating_replay_report_lane_is_rejected(self):
        runtime = ControlWebUIRuntime(WebUIConfig(control_root=self.store_root, port=0))
        original = runtime.ask({"question": "Replay authority?", "mode": "evidence_only"})
        replay = runtime.replay_execute(original["run_id"])
        report = dict(replay["report"])
        report.pop("report_id")
        report["council"] = dict(report["council"])
        report["council"]["consensus_is_truth"] = True
        report_id = sha256_ref(canonical_json_bytes(report))
        forged = {"report_id": report_id, **report}
        path = self.store_root / "records" / "replay-reports" / f"{report_id[7:]}.json"
        path.write_bytes(canonical_json_bytes(forged))
        with self.assertRaises(ReplayError):
            ReplayStore(self.store_root).get_report(report_id)

    def test_orphan_replay_report_is_rejected_before_export(self):
        self._file()
        report_root = self.store_root / "records" / "replay-reports"
        report_root.mkdir(parents=True, exist_ok=True)
        payload = canonical_json_bytes({})
        digest = sha256_ref(payload)
        (report_root / f"{digest[7:]}.json").write_bytes(payload)
        with self.assertRaises(ArkRepositoryBundleError):
            recovery.build_repository_recovery_package(
                self.store_root, self.base / "package", repository_root=ROOT
            )

    def test_invalid_support_schema_and_lattice_are_rejected(self):
        bootstrap = {"schema_count": 1}
        invalid_schema = {
            "schemas/bad.json": {"data": canonical_json_bytes({"$schema": "wrong"})},
            "lattice/profile.json": {"data": canonical_json_bytes(recovery.LATTICE_DESCRIPTOR)},
        }
        with self.assertRaises(ArkRepositoryBundleError):
            recovery._validate_support_entries(invalid_schema, bootstrap)
        invalid_lattice = {
            "schemas/good.json": {"data": canonical_json_bytes({"$schema": recovery.JSON_SCHEMA_DRAFT})},
            "lattice/profile.json": {"data": canonical_json_bytes({"authority": "truth"})},
        }
        with self.assertRaises(ArkRepositoryBundleError):
            recovery._validate_support_entries(invalid_lattice, bootstrap)

    def test_oversized_capsule_is_rejected_by_stat_before_read(self):
        self._file()
        package = self.base / "package"
        recovery.build_repository_recovery_package(
            self.store_root, package, repository_root=ROOT
        )
        capsule = next((package / "capsules").glob("*.dat"))
        with capsule.open("wb") as handle:
            handle.truncate(recovery.MAX_CAPSULE_FILE_BYTES + 1)
        with mock.patch.object(
            recovery, "_read_regular", wraps=recovery._read_regular
        ) as reader:
            with self.assertRaises(ArkRepositoryBundleError):
                recovery.verify_repository_recovery_package(package)
            capsule_reads = [
                call for call in reader.call_args_list
                if call.args and Path(call.args[0]) == capsule
            ]
            self.assertEqual(capsule_reads, [])

    def test_raw_objects_are_streamed_not_loaded_by_read_regular(self):
        self._file(content=b"0123456789abcdef" * 16)
        package = self.base / "package"
        original = recovery._read_regular

        def guarded(path, label, **kwargs):
            if label == "raw object":
                raise AssertionError("raw object was materialized through _read_regular")
            return original(path, label, **kwargs)

        with mock.patch.object(recovery, "LARGE_OBJECT_CHUNK_BYTES", 32), mock.patch.object(
            recovery, "_read_regular", side_effect=guarded
        ):
            recovery.build_repository_recovery_package(
                self.store_root, package, repository_root=ROOT
            )
        self.assertTrue(any((package / "capsules").glob("*.dat")))


if __name__ == "__main__":
    unittest.main()
