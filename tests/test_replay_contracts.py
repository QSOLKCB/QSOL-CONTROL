import json
import unittest
from pathlib import Path

from api.common import MUTATION_OPERATIONS, OPERATIONS
from storage.replay_store import (
    REPLAY_RECORD_PROTOCOL,
    REPLAY_REPORT_PROTOCOL,
    RESEARCH_TIMELINE_PROTOCOL,
)

ROOT = Path(__file__).resolve().parents[1]


class ReplayContractTests(unittest.TestCase):
    def load(self, relative):
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_replay_contract_pins_immutability_and_legacy_honesty(self):
        contract = self.load("ai/replay-contract.json")
        self.assertEqual(contract["protocol"], "qsol-control-replay/1")
        self.assertFalse(contract["exactness_policy"]["exact_replay_claimed_by_phase7"])
        self.assertEqual(
            contract["exactness_policy"]["legacy_missing_index_descriptor"],
            "not_recorded",
        )
        self.assertEqual(
            contract["exactness_policy"]["current_control_ask_index_descriptor"],
            "not_used",
        )
        self.assertTrue(
            contract["original_result_policy"][
                "before_after_integrity_fingerprint_required"
            ]
        )
        self.assertFalse(
            contract["original_result_policy"]["original_run_record_rewritten"]
        )
        self.assertFalse(
            contract["original_result_policy"]["original_event_chain_rewritten"]
        )
        self.assertIn("LEGACY_MISSING_INDEX != INVENTED_INDEX", contract["invariants"])
        self.assertIn("CURRENT_EVIDENCE != ORIGINAL_EVIDENCE", contract["invariants"])

    def test_replay_schemas_pin_nonclaims(self):
        replay = self.load("schema/replay-record.schema.json")
        report = self.load("schema/replay-report.schema.json")
        timeline = self.load("schema/research-timeline.schema.json")
        self.assertEqual(
            replay["properties"]["protocol"]["const"], REPLAY_RECORD_PROTOCOL
        )
        self.assertFalse(replay["properties"]["exact_replay_claimed"]["const"])
        self.assertTrue(replay["properties"]["original_result_immutable"]["const"])
        self.assertEqual(
            report["properties"]["protocol"]["const"], REPLAY_REPORT_PROTOCOL
        )
        self.assertFalse(report["properties"]["comparison_is_truth"]["const"])
        self.assertFalse(
            report["properties"]["model_state_comparison_is_mind_comparison"][
                "const"
            ]
        )
        self.assertEqual(
            timeline["properties"]["protocol"]["const"], RESEARCH_TIMELINE_PROTOCOL
        )
        self.assertFalse(timeline["properties"]["timeline_is_truth"]["const"])

    def test_agent_api_exposes_replay_without_privilege_lane(self):
        expected = {
            "control.replay.classify",
            "control.replay.execute",
            "control.replay.get",
            "control.research.timeline",
        }
        self.assertTrue(expected.issubset(set(OPERATIONS)))
        self.assertIn("control.replay.execute", MUTATION_OPERATIONS)
        contract = self.load("ai/agent-api-contract.json")
        names = {item["name"] for item in contract["operations"]}
        self.assertTrue(expected.issubset(names))
        self.assertTrue(contract["phase7"]["implemented"])
        self.assertTrue(contract["caller_authority"]["equal_epistemic_privilege"])

    def test_phase7_roadmap_remains_complete_after_phase8(self):
        roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
        phase7 = roadmap.split("## Phase 7 — Replay and longitudinal research", 1)[
            1
        ].split("## Phase 8 — ARK recovery bridge", 1)[0]
        self.assertNotIn("- [ ]", phase7)
        self.assertIn("LEGACY_MISSING_INDEX != INVENTED_INDEX", phase7)

    def test_webui_exposes_classify_execute_and_timeline_without_innerhtml(self):
        html = (ROOT / "webui" / "static" / "index.html").read_text(
            encoding="utf-8"
        )
        app = (ROOT / "webui" / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        for marker in (
            'id="replay-classify"',
            'id="replay-execute"',
            'id="research-timeline"',
            "CLASSIFY BEFORE EXECUTE",
        ):
            self.assertIn(marker, html)
        self.assertIn("/api/replay/classify", app)
        self.assertIn('api("/api/replay"', app)
        self.assertIn("/api/research-timeline", app)
        self.assertNotIn("innerHTML", app)

    def test_manifest_and_bootstrap_preserve_phase7_after_later_phases(self):
        manifest = self.load("manifest.json")
        bootstrap = self.load("README4AI.md")
        self.assertEqual(manifest["replay_contract"], "ai/replay-contract.json")
        self.assertEqual(manifest["replay_document"], "docs/REPLAY.md")
        self.assertGreaterEqual(
            manifest["status"]["completed_through_roadmap_phase"], 7
        )
        self.assertEqual(manifest["status"]["replay"], "implemented-phase-7")
        self.assertEqual(bootstrap["replay"]["status"], "implemented_phase7")
        self.assertFalse(bootstrap["replay"]["exact_replay_claimed"])


if __name__ == "__main__":
    unittest.main()
