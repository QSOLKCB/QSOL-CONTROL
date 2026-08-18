import json
import sys
import tempfile
import unittest
from pathlib import Path

from adapters.nexus import NexusAdapterError, NexusCouncilAdapter
from storage.control_store import ControlStore
from storage.interaction_store import InteractionStore

FIXED_TIME = "2026-08-19T09:20:00+09:30"
EVIDENCE_REF = "object:" + "a" * 64


class NexusCouncilAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fake = Path(__file__).with_name("nexus_fake_runtime.py")
        self.members = [
            {"member_id": "A", "model_id": "mock-a", "profile": "balanced"},
            {"member_id": "B", "model_id": "mock-b", "profile": "skeptical"},
            {"member_id": "C", "model_id": "mock-c", "profile": "exploratory"},
        ]

    def tearDown(self):
        self.temp.cleanup()

    def adapter(self, *, tamper=None, log=None):
        command = [sys.executable, str(self.fake)]
        if tamper is not None:
            command += ["--tamper", tamper]
        if log is not None:
            command += ["--log", str(log)]
        return NexusCouncilAdapter.from_command(command, timeout_seconds=10)

    def run_council(self, adapter, **kwargs):
        return adapter.run_council(
            question="Does the admitted evidence support the proposition?",
            members=self.members,
            evidence_refs=[EVIDENCE_REF],
            evidence_state="known",
            mode="analytical",
            **kwargs,
        )

    def test_discovery_uses_health_and_operations(self):
        with self.adapter() as adapter:
            discovery = adapter.discover()
        self.assertEqual(discovery["availability"], "available")
        self.assertEqual(discovery["nexus_protocol"], "nexus/0.14")
        self.assertEqual(discovery["control_transport"], "jsonl_stdio")
        self.assertIn("council.run", discovery["operations"])
        self.assertIn("receipt.verify", discovery["operations"])
        self.assertEqual(discovery["adapter_mutation_operations"], ["council.run"])
        self.assertFalse(discovery["direct_worldstore_mutation_exposed"])
        self.assertEqual(discovery["governance_override_operations"], [])
        self.assertFalse(discovery["hidden_chain_of_thought_capture"])

    def test_council_render_preserves_roster_phases_sealed_ballot_and_minority(self):
        with self.adapter() as adapter:
            result = self.run_council(adapter)
        self.assertEqual([row["member_id"] for row in result["roster"]], ["A", "B", "C"])
        self.assertEqual(
            result["phase_order"],
            ["WHITE", "RED", "BLACK", "YELLOW", "GREEN", "BLUE"],
        )
        self.assertEqual([phase["phase"] for phase in result["phases"]], result["phase_order"])
        for phase in result["phases"]:
            self.assertEqual(
                [row["member_id"] for row in phase["submissions"]],
                ["A", "B", "C"],
            )
        ballot = result["sealed_ballot"]
        self.assertEqual(ballot["stage"], "SEALED_BALLOT")
        self.assertTrue(ballot["sealed_before_reveal"])
        self.assertTrue(ballot["commitments_verified"])
        self.assertEqual(len(ballot["commitments"]), 3)
        self.assertEqual(len(ballot["revealed_ballots"]), 3)
        self.assertEqual(
            result["consensus"]["consensus_threshold"],
            {"numerator": 2, "denominator": 3},
        )
        self.assertEqual(result["consensus"]["tally"], {"ACCEPT": 2, "TEST_FURTHER": 1})
        self.assertEqual(
            result["minority_reports"],
            [{"member_id": "C", "choice": "TEST_FURTHER", "rationale": "needs more evidence"}],
        )
        self.assertFalse(result["hidden_chain_of_thought_captured"])
        self.assertFalse(result["governance"]["control_ballot_override"])
        self.assertFalse(result["governance"]["control_threshold_override"])
        self.assertFalse(result["governance"]["control_vote_weight_override"])

    def test_adapter_never_uses_world_create_or_stenographer_operations(self):
        log = self.root / "operations.log"
        with self.adapter(log=log) as adapter:
            self.run_council(adapter)
        operations = log.read_text(encoding="utf-8").splitlines()
        self.assertIn("council.run", operations)
        self.assertIn("world.inspect", operations)
        self.assertIn("receipt.verify", operations)
        self.assertNotIn("world.create", operations)
        self.assertFalse(any(operation.startswith("stenographer.") for operation in operations))
        allowed = {
            "system.health",
            "system.operations",
            "council.run",
            "world.inspect",
            "receipt.verify",
        }
        self.assertTrue(set(operations).issubset(allowed))

    def test_control_rejects_governance_knobs_before_council_submission(self):
        cases = [
            {"vote_weight": 2},
            {"epistemic_privilege": "special"},
            {"consensus_threshold": {"numerator": 1, "denominator": 2}},
            {"ballot": "ACCEPT"},
            {"world_state": {"rewrite": True}},
        ]
        for extra in cases:
            with self.subTest(extra=extra):
                members = [dict(item) for item in self.members]
                members[0].update(extra)
                with self.adapter() as adapter:
                    with self.assertRaisesRegex(NexusAdapterError, "does not expose NEXUS governance field"):
                        adapter.run_council(
                            question="test",
                            members=members,
                            evidence_refs=[EVIDENCE_REF],
                            evidence_state="known",
                        )

    def test_tampered_threshold_fails_closed(self):
        with self.adapter(tamper="threshold") as adapter:
            with self.assertRaisesRegex(NexusAdapterError, "consensus threshold"):
                self.run_council(adapter)

    def test_tampered_ballot_commitment_fails_closed(self):
        with self.adapter(tamper="commitment") as adapter:
            with self.assertRaisesRegex(NexusAdapterError, "commitment"):
                self.run_council(adapter)

    def test_phase_join_order_tampering_fails_closed(self):
        with self.adapter(tamper="phase_order") as adapter:
            with self.assertRaisesRegex(NexusAdapterError, "canonical roster join order"):
                self.run_council(adapter)

    def test_hidden_reasoning_field_is_rejected(self):
        with self.adapter(tamper="hidden_reasoning") as adapter:
            with self.assertRaisesRegex(NexusAdapterError, "hidden-reasoning"):
                self.run_council(adapter)

    def test_additional_vote_creation_is_rejected(self):
        with self.adapter(tamper="extra_votes") as adapter:
            with self.assertRaisesRegex(NexusAdapterError, "additional votes"):
                self.run_council(adapter)

    def test_failed_receipt_verification_is_rejected(self):
        with self.adapter(tamper="receipt_missing") as adapter:
            with self.assertRaises(NexusAdapterError):
                self.run_council(adapter)

    def test_verified_artifacts_persist_to_control_and_link_interaction(self):
        control_root = self.root / "control"
        interaction = InteractionStore(control_root)
        run = interaction.create_run(
            question="CONTROL parent question",
            mode="council",
            requester_kind="human",
            created_at=FIXED_TIME,
            evidence_state="unknown",
            replayability="R3",
        )
        with self.adapter() as adapter:
            result = self.run_council(
                adapter,
                control_root=control_root,
                control_run_id=run["run_id"],
                created_at=FIXED_TIME,
            )
        storage = result["storage"]
        self.assertEqual(storage["authority"], "reference-only")
        self.assertFalse(storage["hidden_chain_of_thought_captured"])
        self.assertGreaterEqual(len(storage["file_ids"]), 5)
        self.assertEqual(len(storage["interaction_event_ids"]), 2)

        store = ControlStore(control_root)
        for file_id in storage["file_ids"]:
            record = store.get_file_record(file_id)
            self.assertEqual(record["metadata"]["authority"], "reference-only")
            self.assertFalse(record["metadata"]["copied_governance_authority"])
            self.assertFalse(record["metadata"]["hidden_chain_of_thought_captured"])
            json.loads(store.read_file(file_id).decode("utf-8"))

        events = interaction.list_events(run["run_id"])
        self.assertEqual([event["kind"] for event in events[-2:]], ["receipt", "response"])
        self.assertEqual(events[-1]["payload"]["session_ref"], result["session_ref"])
        self.assertFalse(events[-1]["payload"]["hidden_chain_of_thought_captured"])

    def test_admitted_evidence_reference_order_is_preserved(self):
        refs = ["object:" + "a" * 64, "object:" + "b" * 64]
        with self.adapter() as adapter:
            result = adapter.run_council(
                question="evidence order",
                members=self.members,
                evidence_refs=refs,
                evidence_state="known",
            )
        self.assertEqual(result["admitted_evidence_refs"], refs)

    def test_duplicate_evidence_references_fail_before_nexus_mutation(self):
        with self.adapter() as adapter:
            with self.assertRaisesRegex(NexusAdapterError, "must be unique"):
                adapter.run_council(
                    question="duplicates",
                    members=self.members,
                    evidence_refs=[EVIDENCE_REF, EVIDENCE_REF],
                    evidence_state="known",
                )


if __name__ == "__main__":
    unittest.main()
