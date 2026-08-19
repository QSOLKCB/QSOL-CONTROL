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

    def adapter(self, *, tamper=None, log=None, runtime_version=None):
        command = [sys.executable, str(self.fake)]
        if tamper is not None:
            command += ["--tamper", tamper]
        if log is not None:
            command += ["--log", str(log)]
        if runtime_version is not None:
            command += ["--runtime-version", runtime_version]
        return NexusCouncilAdapter.from_command(command, timeout_seconds=10)

    def council_run(self, adapter, **kwargs):
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

    def test_semver_prerelease_and_build_runtime_versions_are_accepted(self):
        with self.adapter(runtime_version="2.0.0-rc.1+build.7") as adapter:
            discovery = adapter.discover()
        self.assertEqual(discovery["nexus_runtime_version"], "2.0.0-rc.1+build.7")

    def test_transport_close_closes_stdout_pipe(self):
        adapter = self.adapter()
        adapter.discover()
        process = adapter._transport._process
        self.assertIsNotNone(process)
        stdout = process.stdout
        self.assertIsNotNone(stdout)
        adapter.close()
        self.assertTrue(stdout.closed)

    def test_council_render_preserves_roster_phases_sealed_ballot_and_minority(self):
        with self.adapter() as adapter:
            result = self.council_run(adapter)
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
        self.assertTrue(result["consensus"]["threshold_met"])
        self.assertEqual(result["consensus"]["consensus_outcome"], "ACCEPT")
        self.assertEqual(result["consensus"]["tally"], {"ACCEPT": 2, "TEST_FURTHER": 1})
        self.assertEqual(
            result["minority_reports"],
            [{"member_id": "C", "choice": "TEST_FURTHER", "rationale": "needs more evidence"}],
        )
        self.assertFalse(result["hidden_chain_of_thought_captured"])
        self.assertFalse(result["governance"]["control_ballot_override"])
        self.assertFalse(result["governance"]["control_threshold_override"])
        self.assertFalse(result["governance"]["control_vote_weight_override"])

    def test_below_threshold_plurality_is_rendered_as_no_consensus(self):
        members = [
            *self.members,
            {"member_id": "D", "model_id": "mock-d", "profile": "balanced"},
        ]
        with self.adapter(tamper="below_threshold") as adapter:
            result = adapter.run_council(
                question="Does the admitted evidence support the proposition?",
                members=members,
                evidence_refs=[EVIDENCE_REF],
                evidence_state="known",
                mode="analytical",
            )
        self.assertEqual(result["consensus"]["disposition"], "ACCEPT")
        self.assertFalse(result["consensus"]["threshold_met"])
        self.assertEqual(result["consensus"]["consensus_outcome"], "NO_CONSENSUS")
        self.assertEqual(result["consensus"]["consensus_label"], "NO_CONSENSUS")

    def test_false_consensus_label_below_threshold_fails_closed(self):
        members = [
            *self.members,
            {"member_id": "D", "model_id": "mock-d", "profile": "balanced"},
        ]
        with self.adapter(tamper="false_consensus") as adapter:
            with self.assertRaisesRegex(NexusAdapterError, "consensus label"):
                adapter.run_council(
                    question="Does the admitted evidence support the proposition?",
                    members=members,
                    evidence_refs=[EVIDENCE_REF],
                    evidence_state="known",
                    mode="analytical",
                )

    def test_adapter_never_uses_world_create_or_stenographer_operations(self):
        log = self.root / "operations.log"
        with self.adapter(log=log) as adapter:
            self.council_run(adapter)
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

    def test_hidden_reasoning_member_field_is_rejected_before_submission(self):
        log = self.root / "hidden-request.log"
        members = [dict(item) for item in self.members]
        members[0]["capability_metadata"] = {"chain_of_thought": True}
        with self.adapter(log=log) as adapter:
            with self.assertRaisesRegex(NexusAdapterError, "hidden-reasoning"):
                adapter.run_council(
                    question="test",
                    members=members,
                    evidence_refs=[EVIDENCE_REF],
                    evidence_state="known",
                )
        operations = log.read_text(encoding="utf-8").splitlines()
        self.assertNotIn("council.run", operations)

    def test_credential_labelled_member_field_is_rejected_before_submission(self):
        log = self.root / "credential-request.log"
        members = [dict(item) for item in self.members]
        members[0]["deployment_metadata"] = {"api_key": "secret-with-no-known-prefix"}
        with self.adapter(log=log) as adapter:
            with self.assertRaisesRegex(NexusAdapterError, "credential-labelled field"):
                adapter.run_council(
                    question="test",
                    members=members,
                    evidence_refs=[EVIDENCE_REF],
                    evidence_state="known",
                )
        operations = log.read_text(encoding="utf-8").splitlines()
        self.assertNotIn("council.run", operations)

    def test_credential_labelled_parent_output_is_rejected(self):
        with self.adapter(tamper="credential_output") as adapter:
            with self.assertRaisesRegex(NexusAdapterError, "credential-labelled field"):
                self.council_run(adapter)

    def test_committed_question_must_match_submitted_question(self):
        with self.adapter(tamper="question_binding") as adapter:
            with self.assertRaisesRegex(NexusAdapterError, "committed question differs"):
                self.council_run(adapter)

    def test_committed_mode_must_match_submitted_mode(self):
        with self.adapter(tamper="mode_binding") as adapter:
            with self.assertRaisesRegex(NexusAdapterError, "mode differs"):
                self.council_run(adapter)

    def test_tampered_threshold_fails_closed(self):
        with self.adapter(tamper="threshold") as adapter:
            with self.assertRaisesRegex(NexusAdapterError, "consensus threshold"):
                self.council_run(adapter)

    def test_tampered_ballot_commitment_fails_closed(self):
        with self.adapter(tamper="commitment") as adapter:
            with self.assertRaisesRegex(NexusAdapterError, "commitment"):
                self.council_run(adapter)

    def test_phase_join_order_tampering_fails_closed(self):
        with self.adapter(tamper="phase_order") as adapter:
            with self.assertRaisesRegex(NexusAdapterError, "canonical roster join order"):
                self.council_run(adapter)

    def test_roster_schema_fields_are_required(self):
        with self.adapter(tamper="roster_missing_model") as adapter:
            with self.assertRaisesRegex(NexusAdapterError, "roster model_id"):
                self.council_run(adapter)
        with self.adapter(tamper="roster_bad_adapter") as adapter:
            with self.assertRaisesRegex(NexusAdapterError, "roster adapter_id"):
                self.council_run(adapter)

    def test_hidden_reasoning_field_is_rejected(self):
        with self.adapter(tamper="hidden_reasoning") as adapter:
            with self.assertRaisesRegex(NexusAdapterError, "hidden-reasoning"):
                self.council_run(adapter)

    def test_additional_vote_creation_is_rejected(self):
        with self.adapter(tamper="extra_votes") as adapter:
            with self.assertRaisesRegex(NexusAdapterError, "additional votes"):
                self.council_run(adapter)

    def test_failed_receipt_verification_is_rejected(self):
        with self.adapter(tamper="receipt_missing") as adapter:
            with self.assertRaises(NexusAdapterError):
                self.council_run(adapter)

    def test_verified_artifacts_persist_to_control_and_link_interaction(self):
        control_root = self.root / "control"
        interaction = InteractionStore(control_root)
        run = interaction.create_run(
            question="Does the admitted evidence support the proposition?",
            mode="council",
            requester_kind="human",
            created_at=FIXED_TIME,
            evidence_state="known",
            oracle_refs=["oracle:fixture:known"],
            replayability="R3",
        )
        with self.adapter() as adapter:
            result = self.council_run(
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

    def test_target_run_inputs_must_match_before_artifact_persistence(self):
        cases = [
            {
                "question": "different CONTROL question",
                "mode": "council",
                "evidence_state": "known",
                "oracle_refs": ["oracle:fixture:known"],
                "error": "question does not match",
            },
            {
                "question": "Does the admitted evidence support the proposition?",
                "mode": "evidence_only",
                "evidence_state": "known",
                "oracle_refs": ["oracle:fixture:known"],
                "error": "not a council-mode",
            },
            {
                "question": "Does the admitted evidence support the proposition?",
                "mode": "council",
                "evidence_state": "unknown",
                "oracle_refs": [],
                "error": "evidence_state does not match",
            },
        ]
        for index, case in enumerate(cases):
            with self.subTest(case=index):
                control_root = self.root / f"mismatch-{index}"
                interaction = InteractionStore(control_root)
                run = interaction.create_run(
                    question=case["question"],
                    mode=case["mode"],
                    requester_kind="human",
                    created_at=FIXED_TIME,
                    evidence_state=case["evidence_state"],
                    oracle_refs=case["oracle_refs"],
                    replayability="R3",
                )
                with self.adapter() as adapter:
                    with self.assertRaisesRegex(NexusAdapterError, case["error"]):
                        self.council_run(
                            adapter,
                            control_root=control_root,
                            control_run_id=run["run_id"],
                            created_at=FIXED_TIME,
                        )
                files_dir = control_root / "records" / "files"
                self.assertFalse(files_dir.exists() and any(files_dir.iterdir()))
                self.assertEqual(interaction.list_events(run["run_id"]), [])

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
