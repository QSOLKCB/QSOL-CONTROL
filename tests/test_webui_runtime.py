import base64
import tempfile
import unittest
from pathlib import Path

from storage.dna_lattice import decode_projection
from webui.server import MODEL_STATE_LABELS, UI_INVARIANTS, ControlWebUIRuntime, WebUIConfig, WebUIError


class WebUIRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = ControlWebUIRuntime(WebUIConfig(control_root=self.root, port=0))

    def tearDown(self):
        self.temp.cleanup()

    def upload(self, content=b"alpha quantum beta", *, name="alpha.txt", privacy="INTERNAL"):
        return self.runtime.upload_file({"filename": name, "media_type": "text/plain", "privacy_class": privacy, "retention_class": "SESSION", "content_base64": base64.b64encode(content).decode("ascii")})["file"]

    def test_session_contract_pins_model_state_labels_and_no_truth_percentage(self):
        session = self.runtime.session_contract()
        self.assertEqual(session["model_state_labels"], MODEL_STATE_LABELS)
        self.assertIn("MODEL_STATE != MODEL_MIND", UI_INVARIANTS)
        self.assertIn("PROVIDER_REPORTED != LOCALLY_VERIFIED", UI_INVARIANTS)
        self.assertFalse(session["truth_percentage_available"])
        self.assertFalse(session["hidden_chain_of_thought_available"])
        self.assertFalse(session["model_mind_available"])

    def test_file_collection_and_search_are_bound_to_exact_snapshot(self):
        file_record = self.upload()
        collection = self.runtime.create_collection({"name": "Research"})
        before = self.runtime.collection_detail(collection["collection_id"])
        snapshot = self.runtime.update_collection(collection["collection_id"], {"add": [file_record["file_id"]], "remove": [], "expected_head_snapshot_id": before["snapshot"]["snapshot_id"]})
        search = self.runtime.search_collection(collection["collection_id"], "quantum")
        self.assertEqual(search["snapshot_id"], snapshot["snapshot_id"])
        self.assertEqual(search["results"][0]["file_id"], file_record["file_id"])
        self.assertIn("not_truth", search["score_meaning"])

    def test_evidence_only_question_records_unknown_when_oracle_unconfigured(self):
        file_record = self.upload()
        result = self.runtime.ask({"question": "What evidence exists?", "mode": "evidence_only", "file_ids": [file_record["file_id"]]})
        self.assertEqual(result["oracle"]["availability"], "unconfigured")
        self.assertEqual(result["run_view"]["run"]["evidence_state"], "unknown")
        self.assertFalse(result["truth_percentage_available"])
        self.assertEqual(result["run_view"]["evidence_events"][-1]["epistemic_role"], "unresolved")

    def test_run_preserves_historical_collection_snapshot_after_head_moves(self):
        first = self.upload(b"first", name="first.txt")
        second = self.upload(b"second", name="second.txt")
        collection = self.runtime.create_collection({"name": "Snapshot test"})
        snapshot_one = self.runtime.update_collection(collection["collection_id"], {"add": [first["file_id"]], "remove": []})
        result = self.runtime.ask({"question": "Freeze this collection state.", "mode": "evidence_only", "collection_id": collection["collection_id"]})
        self.runtime.update_collection(collection["collection_id"], {"add": [second["file_id"]], "remove": []})
        view = self.runtime.run_detail(result["run_id"])
        self.assertEqual(view["collection_snapshot"]["snapshot_id"], snapshot_one["snapshot_id"])
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

    def test_restricted_dna_export_requires_explicit_reversible_acknowledgement(self):
        file_record = self.upload(b"restricted", privacy="RESTRICTED")
        with self.assertRaisesRegex(WebUIError, "allow_restricted"):
            self.runtime.dna_export({"file_id": file_record["file_id"]})
        projection = self.runtime.dna_export({"file_id": file_record["file_id"], "allow_restricted": True, "acknowledge_reversible_sensitive_export": True})
        self.assertEqual(decode_projection(projection), b"restricted")

    def test_run_compare_is_comparison_not_replay_execution(self):
        left = self.runtime.ask({"question": "First", "mode": "evidence_only"})
        right = self.runtime.ask({"question": "Second", "mode": "evidence_only"})
        comparison = self.runtime.compare_runs(left["run_id"], right["run_id"])
        self.assertFalse(comparison["comparison_is_replay_execution"])
        self.assertFalse(comparison["phase7_replay_execution_implemented"])
        self.assertEqual(comparison["authority"], "comparison-only")

    def test_non_loopback_configuration_is_rejected_by_server_boundary(self):
        from webui.server import ControlWebUIServer
        with self.assertRaisesRegex(WebUIError, "loopback only"):
            ControlWebUIServer(WebUIConfig(control_root=self.root, bind="0.0.0.0", port=0))


if __name__ == "__main__":
    unittest.main()
