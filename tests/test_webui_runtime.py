import base64
import tempfile
import unittest
from pathlib import Path

from storage.dna_lattice import decode_projection
from webui.server import (
    MODEL_STATE_LABELS,
    UI_INVARIANTS,
    ControlWebUIRuntime,
    WebUIConfig,
    WebUIError,
)


class WebUIRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = ControlWebUIRuntime(WebUIConfig(control_root=self.root, port=0))

    def tearDown(self):
        self.temp.cleanup()

    def upload(self, content=b"alpha quantum beta", *, name="alpha.txt", privacy="INTERNAL"):
        return self.runtime.upload_file(
            {
                "filename": name,
                "media_type": "text/plain",
                "privacy_class": privacy,
                "retention_class": "SESSION",
                "content_base64": base64.b64encode(content).decode("ascii"),
            }
        )["file"]

    def add_files(self, collection_id, file_ids):
        detail = self.runtime.collection_detail(collection_id)
        return self.runtime.update_collection(
            collection_id,
            {
                "add": list(file_ids),
                "remove": [],
                "expected_head_snapshot_id": detail["snapshot"]["snapshot_id"],
            },
        )

    def test_session_contract_pins_model_state_labels_and_no_truth_percentage(self):
        session = self.runtime.session_contract()
        self.assertEqual(session["model_state_labels"], MODEL_STATE_LABELS)
        self.assertEqual(session["max_question_characters"], 2048)
        self.assertIn("MODEL_STATE != MODEL_MIND", UI_INVARIANTS)
        self.assertIn("PROVIDER_REPORTED != LOCALLY_VERIFIED", UI_INVARIANTS)
        self.assertFalse(session["truth_percentage_available"])
        self.assertFalse(session["hidden_chain_of_thought_available"])
        self.assertFalse(session["model_mind_available"])

    def test_question_limit_matches_oracle_contract(self):
        self.runtime.ask({"question": "x" * 2048, "mode": "evidence_only"})
        with self.assertRaisesRegex(WebUIError, "2048"):
            self.runtime.ask({"question": "x" * 2049, "mode": "evidence_only"})

    def test_file_collection_and_search_are_bound_to_exact_snapshot(self):
        file_record = self.upload()
        collection = self.runtime.create_collection({"name": "Research"})
        snapshot = self.add_files(collection["collection_id"], [file_record["file_id"]])

        original = self.runtime.store.search_lexical

        def guarded_search(collection_id, query, *, limit=10):
            lock = self.runtime.store._lock_path(f"collection-head:{collection_id}")
            self.assertTrue(lock.is_file())
            return original(collection_id, query, limit=limit)

        self.runtime.store.search_lexical = guarded_search
        search = self.runtime.search_collection(collection["collection_id"], "quantum")
        self.assertEqual(search["snapshot_id"], snapshot["snapshot_id"])
        self.assertEqual(search["results"][0]["file_id"], file_record["file_id"])
        self.assertEqual(search["results"][0]["snapshot_id"], snapshot["snapshot_id"])
        self.assertIn("not_truth", search["score_meaning"])

    def test_collection_update_requires_expected_head_snapshot(self):
        collection = self.runtime.create_collection({"name": "CAS required"})
        with self.assertRaisesRegex(WebUIError, "expected_head_snapshot_id is required"):
            self.runtime.update_collection(
                collection["collection_id"], {"add": [], "remove": []}
            )

    def test_evidence_only_question_records_unknown_when_oracle_unconfigured(self):
        file_record = self.upload()
        result = self.runtime.ask(
            {
                "question": "What evidence exists?",
                "mode": "evidence_only",
                "file_ids": [file_record["file_id"]],
            }
        )
        self.assertEqual(result["oracle"]["availability"], "unconfigured")
        self.assertEqual(result["run_view"]["run"]["evidence_state"], "unknown")
        self.assertFalse(result["truth_percentage_available"])
        self.assertEqual(
            result["run_view"]["evidence_events"][-1]["epistemic_role"], "unresolved"
        )

    def test_unconfigured_council_outcome_is_immutable_run_history(self):
        result = self.runtime.ask(
            {"question": "Ask the unavailable Council", "mode": "council"}
        )
        self.assertEqual(result["council"]["availability"], "unconfigured")
        refreshed = self.runtime.run_detail(result["run_id"])
        response = refreshed["response_events"][-1]
        self.assertEqual(response["payload"]["protocol"], "qsol-control-webui-council-status/1")
        self.assertEqual(response["payload"]["availability"], "unconfigured")
        self.assertEqual(response["epistemic_role"], "unresolved")

    def test_run_preserves_historical_collection_snapshot_after_head_moves(self):
        first = self.upload(b"first", name="first.txt")
        second = self.upload(b"second", name="second.txt")
        collection = self.runtime.create_collection({"name": "Snapshot test"})
        snapshot_one = self.add_files(collection["collection_id"], [first["file_id"]])
        result = self.runtime.ask(
            {
                "question": "Freeze this collection state.",
                "mode": "evidence_only",
                "collection_id": collection["collection_id"],
            }
        )
        self.add_files(collection["collection_id"], [second["file_id"]])
        view = self.runtime.run_detail(result["run_id"])
        self.assertEqual(
            view["collection_snapshot"]["snapshot_id"], snapshot_one["snapshot_id"]
        )
        self.assertEqual(view["collection_snapshot"]["members"], [first["file_id"]])

    def test_lattice_view_has_exactly_27_top_level_cells(self):
        result = self.runtime.ask({"question": "Remember this.", "mode": "evidence_only"})
        lattice = self.runtime.lattice_view(result["run_id"])
        self.assertEqual(len(lattice["cells"]), 27)
        self.assertFalse(lattice["geometry_is_truth"])
        self.assertGreater(sum(cell["count"] for cell in lattice["cells"]), 0)

    def test_dna_inspection_and_export_remain_derived(self):
        file_record = self.upload(b"DNA fixture")
        inspection = self.runtime.dna_inspect({"file_id": file_record["file_id"]})
        self.assertTrue(inspection["derived"])
        self.assertEqual(inspection["authority"], "none")
        self.assertFalse(inspection["codon_frequency_is_evidence"])
        projection = self.runtime.dna_export({"file_id": file_record["file_id"]})
        self.assertEqual(decode_projection(projection), b"DNA fixture")

    def test_restricted_dna_export_requires_acknowledgement_and_actor(self):
        file_record = self.upload(b"restricted", privacy="RESTRICTED")
        with self.assertRaisesRegex(WebUIError, "allow_restricted"):
            self.runtime.dna_export({"file_id": file_record["file_id"]})
        with self.assertRaisesRegex(WebUIError, "actor attribution"):
            self.runtime.dna_export(
                {
                    "file_id": file_record["file_id"],
                    "allow_restricted": True,
                    "acknowledge_reversible_sensitive_export": True,
                }
            )
        projection = self.runtime.dna_export(
            {
                "file_id": file_record["file_id"],
                "allow_restricted": True,
                "acknowledge_reversible_sensitive_export": True,
                "actor": "review-test-operator",
            }
        )
        self.assertEqual(decode_projection(projection), b"restricted")
        self.assertEqual(
            self.runtime.store.list_audit_events()[-1]["actor"], "review-test-operator"
        )

    def test_run_compare_uses_nexus_refs_from_immutable_events(self):
        left = self.runtime.ask({"question": "Left Council", "mode": "council"})
        right = self.runtime.ask({"question": "Right Council", "mode": "council"})
        left_session = "object:" + "1" * 64
        left_receipt = "object:" + "2" * 64
        right_session = "object:" + "3" * 64
        right_receipt = "object:" + "4" * 64
        self.runtime.interactions.append_event(
            left["run_id"],
            kind="receipt",
            payload={
                "nexus_session_ref": left_session,
                "nexus_receipt_ref": left_receipt,
            },
            occurred_at="2026-08-19T03:00:00Z",
            record_refs=[left_session, left_receipt],
        )
        self.runtime.interactions.append_event(
            right["run_id"],
            kind="receipt",
            payload={
                "nexus_session_ref": right_session,
                "nexus_receipt_ref": right_receipt,
            },
            occurred_at="2026-08-19T03:00:01Z",
            record_refs=[right_session, right_receipt],
        )
        comparison = self.runtime.compare_runs(left["run_id"], right["run_id"])
        self.assertEqual(comparison["left_nexus_refs"], [left_session, left_receipt])
        self.assertEqual(comparison["right_nexus_refs"], [right_session, right_receipt])
        self.assertIn(
            "nexus_event_refs",
            [item["field"] for item in comparison["changed_run_fields"]],
        )
        self.assertFalse(comparison["comparison_is_replay_execution"])

    def test_non_loopback_configuration_is_rejected_by_server_boundary(self):
        from webui.server import ControlWebUIServer

        with self.assertRaisesRegex(WebUIError, "loopback only"):
            ControlWebUIServer(WebUIConfig(control_root=self.root, bind="0.0.0.0", port=0))


if __name__ == "__main__":
    unittest.main()
