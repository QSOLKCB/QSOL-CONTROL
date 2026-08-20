import base64
import tempfile
import unittest
from pathlib import Path

from api.common import MAX_REQUESTS_PER_CALLER, QuotaState
from api.dispatcher import AgentAPIDispatcher
from api.stdio import process_line
from webui.common import WebUIConfig


class AgentAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.dispatcher = AgentAPIDispatcher(WebUIConfig(control_root=self.root, port=0))
        self.counter = 0

    def tearDown(self):
        self.temp.cleanup()

    def request(self, operation, params=None, *, kind="ai", caller_id="agent-test"):
        self.counter += 1
        return self.dispatcher.handle(
            {
                "protocol": "qsol-control-agent-request/1",
                "request_id": f"req-{self.counter}",
                "caller": {"kind": kind, "id": caller_id},
                "operation": operation,
                "params": params or {},
            }
        )

    def put_file(self, content=b"alpha quantum beta", name="alpha.txt"):
        response = self.request(
            "control.file.put",
            {
                "filename": name,
                "media_type": "text/plain",
                "content_base64": base64.b64encode(content).decode("ascii"),
            },
        )
        self.assertTrue(response["ok"])
        return response["result"]["file"]

    def test_capabilities_freeze_equal_authority_and_no_parent_backdoors(self):
        response = self.request("control.capabilities")
        self.assertTrue(response["ok"])
        result = response["result"]
        self.assertTrue(result["human_ai_epistemic_authority_equal"])
        self.assertEqual(result["oracle_write_operations"], [])
        self.assertFalse(result["nexus_arbitrary_operation_passthrough"])
        self.assertFalse(result["nexus_governance_overrides"])
        self.assertFalse(result["truth_percentage_available"])
        self.assertFalse(result["hidden_chain_of_thought_available"])

    def test_ai_and_human_ask_share_runtime_but_preserve_requester_kind(self):
        ai = self.request(
            "control.ask", {"question": "AI question", "mode": "evidence_only"}
        )
        human = self.request(
            "control.ask",
            {"question": "Human question", "mode": "evidence_only"},
            kind="human",
            caller_id="human-test",
        )
        self.assertEqual(ai["result"]["run_view"]["run"]["requester_kind"], "ai")
        self.assertEqual(human["result"]["run_view"]["run"]["requester_kind"], "human")
        self.assertEqual(ai["authority"], human["authority"])
        self.assertEqual(ai["result"]["oracle"]["state"], "unknown")
        self.assertEqual(human["result"]["oracle"]["state"], "unknown")

    def test_file_collection_snapshot_and_search_round_trip(self):
        file_record = self.put_file()
        created = self.request(
            "control.collection.create",
            {"name": "Agent research", "file_ids": [file_record["file_id"]]},
        )
        collection_id = created["result"]["collection"]["collection_id"]
        snapshot_id = created["result"]["snapshot"]["snapshot_id"]
        self.assertEqual(created["result"]["snapshot"]["members"], [file_record["file_id"]])

        snapshot = self.request(
            "control.collection.snapshot",
            {"collection_id": collection_id, "snapshot_id": snapshot_id},
        )
        self.assertEqual(snapshot["result"]["snapshot"]["snapshot_id"], snapshot_id)
        self.assertFalse(snapshot["result"]["membership_is_endorsement"])

        search = self.request(
            "control.collection.search",
            {"collection_id": collection_id, "query": "quantum", "limit": 10},
        )
        self.assertEqual(search["result"]["snapshot_id"], snapshot_id)
        self.assertEqual(search["result"]["results"][0]["file_id"], file_record["file_id"])
        self.assertIn("not_truth", search["result"]["score_meaning"])

        fetched = self.request(
            "control.file.get",
            {"file_id": file_record["file_id"], "include_content": True},
        )
        self.assertEqual(base64.b64decode(fetched["result"]["content_base64"]), b"alpha quantum beta")
        self.assertTrue(fetched["result"]["raw_bytes_canonical"])

    def test_run_evidence_council_models_and_compare_are_separate_views(self):
        left = self.request(
            "control.ask", {"question": "Left", "mode": "evidence_only"}
        )["result"]
        right = self.request(
            "control.ask", {"question": "Right", "mode": "council"}
        )["result"]

        run = self.request("control.run.get", {"run_id": left["run_id"]})
        self.assertEqual(run["result"]["run"]["run_id"], left["run_id"])

        evidence = self.request("control.evidence.get", {"run_id": left["run_id"]})
        self.assertEqual(evidence["result"]["evidence_state"], "unknown")
        self.assertFalse(evidence["result"]["vote_is_evidence"])

        council = self.request("control.council.get", {"run_id": right["run_id"]})
        self.assertFalse(council["result"]["consensus_is_truth"])
        self.assertFalse(council["result"]["hidden_chain_of_thought_available"])

        models = self.request("control.models.get", {"run_id": left["run_id"]})
        self.assertEqual(models["result"]["states"], [])
        self.assertFalse(models["result"]["model_state_is_model_mind"])

        comparison = self.request(
            "control.run.compare",
            {"left_run_id": left["run_id"], "right_run_id": right["run_id"]},
        )
        self.assertFalse(comparison["result"]["comparison_is_replay_execution"])
        self.assertFalse(comparison["result"]["phase7_replay_execution_implemented"])

    def test_lattice_get_and_trace_are_bounded_and_non_authoritative(self):
        run_id = self.request(
            "control.ask", {"question": "Trace me", "mode": "evidence_only"}
        )["result"]["run_id"]
        memory = self.request(
            "control.memory.get", {"run_id": run_id, "max_records": 1}
        )["result"]
        self.assertEqual(memory["returned_records"], 1)
        self.assertFalse(memory["geometry_is_truth"])

        trace = self.request(
            "control.memory.trace",
            {
                "run_id": run_id,
                "address_prefix": "L[0,1,0]",
                "max_runs": 1,
                "max_records": 1,
            },
        )["result"]
        self.assertEqual(trace["records"][0]["kind"], "run-question")
        self.assertFalse(trace["lattice_address_is_truth"])

    def test_authority_escalation_fields_fail_closed(self):
        response = self.request(
            "control.ask",
            {
                "question": "Cheat",
                "mode": "evidence_only",
                "epistemic_privilege": "superuser",
            },
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "AUTHORITY_ESCALATION")

    def test_caller_quota_fails_closed(self):
        self.dispatcher._quota["ai:agent-test"] = QuotaState(
            requests=MAX_REQUESTS_PER_CALLER,
            mutations=0,
        )
        response = self.request("control.health")
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "QUOTA_EXCEEDED")

    def test_duplicate_json_members_are_rejected(self):
        raw = (
            b'{"protocol":"qsol-control-agent-request/1","request_id":"dup",'
            b'"caller":{"kind":"ai","id":"a"},"operation":"control.health",'
            b'"params":{},"params":{}}\n'
        )
        response = process_line(self.dispatcher, raw)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "INVALID_JSON")


if __name__ == "__main__":
    unittest.main()
