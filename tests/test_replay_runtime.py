import base64
import tempfile
import unittest
from pathlib import Path

from webui.common import WebUIConfig
from webui.runtime import ControlWebUIRuntime


class ReplayRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = ControlWebUIRuntime(WebUIConfig(control_root=self.root, port=0))

    def tearDown(self):
        self.temp.cleanup()

    def upload(self, content: bytes, name: str):
        return self.runtime.upload_file(
            {
                "filename": name,
                "media_type": "text/plain",
                "privacy_class": "INTERNAL",
                "retention_class": "SESSION",
                "content_base64": base64.b64encode(content).decode("ascii"),
            }
        )["file"]

    def add(self, collection_id: str, file_ids: list[str]):
        current = self.runtime.collection_detail(collection_id)["snapshot"]
        return self.runtime.update_collection(
            collection_id,
            {
                "add": file_ids,
                "remove": [],
                "expected_head_snapshot_id": current["snapshot_id"],
            },
        )

    def test_new_run_captures_replay_basis_without_claiming_unused_index(self):
        result = self.runtime.ask(
            {"question": "What survives?", "mode": "evidence_only"}
        )
        run_id = result["run_id"]
        basis_events = [
            event
            for event in self.runtime.interactions.list_events(run_id)
            if event["kind"] == "receipt"
            and event["payload"].get("protocol") == "qsol-control-replay-basis/1"
        ]
        self.assertEqual(len(basis_events), 1)
        basis = basis_events[0]["payload"]
        self.assertEqual(basis["retrieval_index"]["status"], "not_used")
        self.assertIsNone(basis["retrieval_index"]["index_id"])
        classification = self.runtime.replay_classify(run_id)
        self.assertEqual(classification["classification"], "current_evidence_rerun")
        self.assertTrue(classification["can_execute"])
        self.assertFalse(classification["exact_replay_claimed"])

    def test_legacy_run_reports_unrecorded_index_basis_without_invention(self):
        run = self.runtime.interactions.create_run(
            question="Legacy question",
            mode="evidence_only",
            requester_kind="human",
            created_at="2026-08-20T00:00:00Z",
            evidence_state="unknown",
            replayability="R3",
        )
        classification = self.runtime.replay_classify(run["run_id"])
        self.assertEqual(classification["basis_status"], "legacy_incomplete")
        self.assertEqual(classification["retrieval_index_status"], "not_recorded")
        self.assertEqual(
            classification["classification"], "legacy_current_evidence_rerun"
        )
        self.assertFalse(classification["exact_replay_claimed"])

    def test_replay_pins_original_snapshot_and_reports_current_membership_drift(self):
        first = self.upload(b"first", "first.txt")
        second = self.upload(b"second", "second.txt")
        collection = self.runtime.create_collection({"name": "Replay collection"})
        snapshot_one = self.add(collection["collection_id"], [first["file_id"]])
        original = self.runtime.ask(
            {
                "question": "Recurring collection question",
                "mode": "evidence_only",
                "collection_id": collection["collection_id"],
            }
        )
        original_run = original["run_view"]["run"]
        self.assertEqual(
            original_run["collection_ref"]["snapshot_id"], snapshot_one["snapshot_id"]
        )

        snapshot_two = self.add(collection["collection_id"], [second["file_id"]])
        classification = self.runtime.replay_classify(original["run_id"])
        self.assertTrue(classification["collection_membership_drift"])
        self.assertEqual(
            classification["current_collection_head_snapshot_id"],
            snapshot_two["snapshot_id"],
        )

        replay = self.runtime.replay_execute(original["run_id"])
        replay_run = replay["replay_run_view"]["run"]
        self.assertEqual(replay_run["collection_ref"], original_run["collection_ref"])
        self.assertTrue(replay["original_result_immutable"])
        self.assertTrue(replay["report"]["original_result"]["immutable"])
        self.assertEqual(
            replay["report"]["collection"]["original_snapshot_id"],
            snapshot_one["snapshot_id"],
        )
        self.assertEqual(
            replay["report"]["collection"]["current_head_snapshot_id"],
            snapshot_two["snapshot_id"],
        )
        self.assertEqual(
            replay["report"]["collection"]["added_since_original"],
            [second["file_id"]],
        )
        self.assertTrue(
            replay["report"]["collection"]["replay_bound_to_original_snapshot"]
        )
        self.assertFalse(replay["replay"]["exact_replay_claimed"])
        self.assertFalse(
            replay["report"]["evidence"]["current_evidence_is_original_evidence"]
        )

    def test_original_run_bytes_and_event_chain_are_unchanged_by_replay(self):
        original = self.runtime.ask(
            {"question": "Immutable original", "mode": "evidence_only"}
        )
        run_id = original["run_id"]
        before_run = self.runtime.interactions._run_path(run_id).read_bytes()
        before_events = [
            self.runtime.interactions._event_path(event["event_id"]).read_bytes()
            for event in self.runtime.interactions.list_events(run_id)
        ]
        replay = self.runtime.replay_execute(run_id)
        self.assertEqual(self.runtime.interactions._run_path(run_id).read_bytes(), before_run)
        after_events = [
            self.runtime.interactions._event_path(event["event_id"]).read_bytes()
            for event in self.runtime.interactions.list_events(run_id)
        ]
        self.assertEqual(after_events, before_events)
        self.assertEqual(
            replay["report"]["original_result"]["fingerprint_before"],
            replay["report"]["original_result"]["fingerprint_after"],
        )

    def test_replay_report_is_content_addressed_and_retrievable(self):
        original = self.runtime.ask(
            {"question": "Deterministic report", "mode": "evidence_only"}
        )
        replay = self.runtime.replay_execute(original["run_id"])
        stored = self.runtime.replay_get(replay["replay"]["replay_id"])
        self.assertEqual(stored["report"], replay["report"])
        rewritten = self.runtime.replays.write_report(
            {
                key: value
                for key, value in replay["report"].items()
                if key != "report_id"
            }
        )
        self.assertEqual(rewritten["report_id"], replay["report"]["report_id"])

    def test_recurring_question_timeline_links_replay_and_transitions(self):
        original = self.runtime.ask(
            {"question": "Ask this again", "mode": "evidence_only"}
        )
        replay = self.runtime.replay_execute(original["run_id"])
        timeline = self.runtime.research_timeline(original["run_id"])
        self.assertEqual(timeline["total_matching_runs"], 2)
        self.assertEqual(len(timeline["runs"]), 2)
        self.assertEqual(len(timeline["transitions"]), 1)
        replay_row = next(
            row
            for row in timeline["runs"]
            if row["run_id"] == replay["replay"]["replay_run_id"]
        )
        self.assertEqual(replay_row["replay_of"], original["run_id"])
        self.assertFalse(timeline["timeline_is_truth"])
        self.assertEqual(timeline["authority"], "longitudinal-comparison-only")


if __name__ == "__main__":
    unittest.main()
