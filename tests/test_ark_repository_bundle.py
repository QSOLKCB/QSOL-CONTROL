import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from storage import ark_repository_bundle as repository_recovery
from storage.ark_repository_bundle import (
    ArkRepositoryBundleError,
    build_repository_recovery_package,
    restore_repository_recovery_package,
    verify_repository_recovery_package,
)
from storage.control_store import ControlStore
from storage.interaction_store import InteractionStore
from storage.model_state_registry import ModelStateRegistry
from storage.replay_store import (
    REPLAY_RECORD_PROTOCOL,
    REPLAY_REPORT_PROTOCOL,
    ReplayStore,
)

ROOT = Path(__file__).resolve().parents[1]
TIME_A = "2026-08-20T18:00:00+09:30"
TIME_B = "2026-08-20T18:01:00+09:30"


class ArkRepositoryRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "source"
        self.store = ControlStore(self.root)
        self.interactions = InteractionStore(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def build_specimen(self, *, with_index=True, with_model=True, with_replay=True):
        file_record = self.store.put_file(
            b"alpha evidence beta",
            filename="alpha.txt",
            media_type="text/plain",
            created_at=TIME_A,
            privacy_class="INTERNAL",
            retention_class="ARCHIVE",
        )
        collection = self.store.create_collection(
            name="Recovery research",
            created_at=TIME_A,
            privacy_class="INTERNAL",
            retention_class="ARCHIVE",
        )
        snapshot = self.store.update_collection(
            collection["collection_id"],
            add=[file_record["file_id"]],
            created_at=TIME_A,
            expected_head_snapshot_id=collection["head_snapshot_id"],
        )
        if with_index:
            self.store.build_lexical_index(collection["collection_id"], built_at=TIME_A)

        run_a = self.interactions.create_run(
            question="What changed?",
            mode="evidence_only",
            requester_kind="human",
            created_at=TIME_A,
            evidence_state="unknown",
            collection_id=collection["collection_id"],
            snapshot_id=snapshot["snapshot_id"],
            replayability="R3",
        )
        self.interactions.append_event(
            run_a["run_id"],
            kind="evidence",
            payload={"availability": "unconfigured", "state": "unknown", "evidence_refs": []},
            occurred_at=TIME_A,
            epistemic_role="unresolved",
            temporal_role="current",
            record_refs=["oracle:unconfigured"],
        )

        if with_model:
            registry = ModelStateRegistry(self.root)
            registry.capture(
                captured_at=TIME_A,
                model={
                    "provider": "local",
                    "runtime": "fixture-runtime",
                    "runtime_version": "1.0.0",
                    "model_id": "fixture-model",
                    "revision": "r1",
                    "model_hash": None,
                    "weight_hash": None,
                    "tokenizer_identity": "fixture-tokenizer",
                    "tokenizer_hash": None,
                    "quantization": "none",
                },
                execution={
                    "council_seat": None,
                    "mode": "analytical",
                    "stochastic": False,
                    "seed": 1,
                    "context_limit": 4096,
                    "sampling": {},
                    "tool_permissions": [],
                    "tool_permission_envelope": {
                        "filesystem": "none",
                        "network": "none",
                        "tools": [],
                        "mcp_plugins": [],
                        "external_execution": False,
                    },
                },
                system={
                    "control_run_id": run_a["run_id"],
                    "control_manifest_identity": "manifest:fixture",
                    "nexus_identity": None,
                    "oracle_refs": [],
                    "substrate_identity": None,
                    "ark_identity": None,
                    "int_identity": None,
                    "collection_snapshot_id": snapshot["snapshot_id"],
                    "evidence_snapshot_ref": None,
                    "hardware_runtime_metadata": {},
                },
                field_provenance={},
                privacy_class="INTERNAL",
                link_run_event=False,
            )

        run_b = self.interactions.create_run(
            question="What changed?",
            mode="evidence_only",
            requester_kind="system",
            created_at=TIME_B,
            evidence_state="unknown",
            collection_id=collection["collection_id"],
            snapshot_id=snapshot["snapshot_id"],
            replayability="R3",
        )
        if with_replay:
            replays = ReplayStore(self.root)
            report = replays.write_report(
                {
                    "protocol": REPLAY_REPORT_PROTOCOL,
                    "original_run_id": run_a["run_id"],
                    "replay_run_id": run_b["run_id"],
                    "authority": "comparison-only",
                }
            )
            replays.write_replay(
                {
                    "protocol": REPLAY_RECORD_PROTOCOL,
                    "original_run_id": run_a["run_id"],
                    "replay_run_id": run_b["run_id"],
                    "report_id": report["report_id"],
                    "executed_at": TIME_B,
                    "authority": "orchestration-and-comparison-only",
                }
            )
        return {
            "file": file_record,
            "collection": collection,
            "snapshot": snapshot,
            "run_a": run_a,
            "run_b": run_b,
        }

    @staticmethod
    def package_bytes(root):
        rows = []
        for path in sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.relative_to(root).as_posix().encode("utf-8")):
            rows.append((path.relative_to(root).as_posix(), path.read_bytes()))
        return rows

    def test_repository_package_is_byte_deterministic(self):
        self.build_specimen()
        first = Path(self.temp.name) / "package-a"
        second = Path(self.temp.name) / "package-b"
        report_a = build_repository_recovery_package(
            self.root, first, repository_root=ROOT, include_indexes=True, include_dna=True
        )
        report_b = build_repository_recovery_package(
            self.root, second, repository_root=ROOT, include_indexes=True, include_dna=True
        )
        self.assertEqual(report_a["package_id"], report_b["package_id"])
        self.assertEqual(self.package_bytes(first), self.package_bytes(second))

    def test_restore_preserves_canonical_state_model_and_replay_without_indexes(self):
        specimen = self.build_specimen()
        package = Path(self.temp.name) / "package"
        build_repository_recovery_package(
            self.root, package, repository_root=ROOT, include_indexes=True, include_dna=True
        )
        target = Path(self.temp.name) / "restored"
        report = restore_repository_recovery_package(package, target)
        self.assertEqual(report["status"], "restored")
        restored = ControlStore(target / "store")
        self.assertEqual(restored.read_file(specimen["file"]["file_id"]), b"alpha evidence beta")
        self.assertEqual(
            restored.get_collection(specimen["collection"]["collection_id"])["head_snapshot_id"],
            specimen["snapshot"]["snapshot_id"],
        )
        interactions = InteractionStore(target / "store")
        interactions.verify_run(specimen["run_a"]["run_id"])
        self.assertEqual(len(ModelStateRegistry(target / "store").list_states()), 1)
        self.assertEqual(len(ReplayStore(target / "store").list_replays()), 1)
        index_root = target / "store" / "records" / "indexes"
        self.assertFalse(index_root.exists() and any(index_root.iterdir()))
        self.assertTrue(any((target / "optional" / "index-descriptors").glob("*.json")))
        self.assertTrue(any((target / "optional" / "dna").glob("*.json")))
        self.assertTrue((target / "RECOVERY-MAP.txt").is_file())
        self.assertTrue(any((target / "schemas").glob("*.json")))

    def test_large_raw_object_is_chunked_and_reassembled(self):
        raw = b"0123456789abcdef" * 8
        record = self.store.put_file(
            raw,
            filename="large.bin",
            created_at=TIME_A,
            privacy_class="INTERNAL",
            retention_class="ARCHIVE",
        )
        package = Path(self.temp.name) / "package"
        with mock.patch.object(repository_recovery, "LARGE_OBJECT_CHUNK_BYTES", 32):
            build_repository_recovery_package(self.root, package, repository_root=ROOT)
            target = Path(self.temp.name) / "restored"
            restore_repository_recovery_package(package, target)
        self.assertEqual(ControlStore(target / "store").read_file(record["file_id"]), raw)

    def test_capsule_tamper_is_rejected(self):
        self.build_specimen(with_index=False)
        package = Path(self.temp.name) / "package"
        build_repository_recovery_package(self.root, package, repository_root=ROOT)
        capsule = sorted((package / "capsules").glob("*.dat"))[0]
        raw = bytearray(capsule.read_bytes())
        raw[-1] ^= 0x01
        capsule.write_bytes(raw)
        with self.assertRaises(ArkRepositoryBundleError):
            verify_repository_recovery_package(package)

    def test_constrained_fixture_recovers_without_webui_or_search_engine(self):
        fixture = json.loads(
            (ROOT / "examples" / "recovery" / "constrained-store.fixture.json").read_text(
                encoding="utf-8"
            )
        )
        file_record = self.store.put_file(
            fixture["file"]["content"].encode("utf-8"),
            filename=fixture["file"]["filename"],
            media_type=fixture["file"]["media_type"],
            created_at=TIME_A,
            privacy_class="INTERNAL",
            retention_class="ARCHIVE",
        )
        collection = self.store.create_collection(
            name=fixture["collection"]["name"],
            created_at=TIME_A,
            privacy_class="INTERNAL",
            retention_class="ARCHIVE",
        )
        snapshot = self.store.update_collection(
            collection["collection_id"],
            add=[file_record["file_id"]],
            created_at=TIME_A,
            expected_head_snapshot_id=collection["head_snapshot_id"],
        )
        self.interactions.create_run(
            question=fixture["question"],
            mode="evidence_only",
            requester_kind="human",
            created_at=TIME_A,
            evidence_state="unknown",
            collection_id=collection["collection_id"],
            snapshot_id=snapshot["snapshot_id"],
            replayability="R3",
        )
        package = Path(self.temp.name) / "package"
        build_repository_recovery_package(self.root, package, repository_root=ROOT)
        with mock.patch.dict("sys.modules", {"webui": None}):
            report = verify_repository_recovery_package(package)
        self.assertTrue(report["offline_round_trip"])
        self.assertFalse(report["webui_required"])
        self.assertFalse(report["search_engine_required"])

    def test_restricted_source_is_classified_before_export_policy(self):
        self.store.put_file(
            b"restricted",
            filename="private.txt",
            created_at=TIME_A,
            privacy_class="RESTRICTED",
            retention_class="ARCHIVE",
        )
        self.assertEqual(repository_recovery.source_privacy_class(self.root), "RESTRICTED")


if __name__ == "__main__":
    unittest.main()
