import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from storage.control_store import canonical_json_bytes, sha256_ref
from storage.replay_store import ReplayError
from webui.common import WebUIConfig, WebUIError
from webui.runtime import ControlWebUIRuntime


class ReplayCodexRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = ControlWebUIRuntime(WebUIConfig(control_root=self.root, port=0))

    def tearDown(self):
        self.temp.cleanup()

    def test_full_council_member_descriptor_changes_are_configuration_drift(self):
        original_members = (
            {
                "member_id": "WHITE",
                "model_id": "fixture-model",
                "adapter_id": "fixture-adapter",
                "profile": "careful-v1",
            },
        )
        original_runtime = ControlWebUIRuntime(
            WebUIConfig(
                control_root=self.root,
                port=0,
                default_council_members=original_members,
            )
        )
        result = original_runtime.ask(
            {
                "question": "Does the full Council configuration survive?",
                "mode": "council",
            }
        )
        basis = original_runtime._basis_for_run(result["run_id"])
        self.assertEqual(
            basis["request_configuration"]["council_member_descriptors"][0]["profile"],
            "careful-v1",
        )
        changed_runtime = ControlWebUIRuntime(
            WebUIConfig(
                control_root=self.root,
                port=0,
                nexus_command=("fixture-nexus",),
                default_council_members=(
                    {
                        "member_id": "WHITE",
                        "model_id": "fixture-model",
                        "adapter_id": "fixture-adapter",
                        "profile": "careful-v2",
                    },
                ),
            )
        )
        classification = changed_runtime.replay_classify(result["run_id"])
        self.assertTrue(classification["council_roster_changed"])
        self.assertEqual(classification["classification"], "changed_configuration_rerun")

    def test_invalid_replay_basis_input_creates_no_run(self):
        before = list((self.root / "records" / "runs").glob("*.json"))
        with self.assertRaises(WebUIError):
            self.runtime.ask(
                {
                    "question": "Reject before persistence",
                    "mode": "evidence_only",
                    "suggested_searches": "not-an-array",
                }
            )
        after = list((self.root / "records" / "runs").glob("*.json"))
        self.assertEqual(after, before)

    def test_hash_valid_authority_escalating_replay_record_is_rejected_on_read(self):
        original = self.runtime.ask(
            {"question": "Semantic replay read validation", "mode": "evidence_only"}
        )
        replay = self.runtime.replay_execute(original["run_id"])
        forged = copy.deepcopy(replay["replay"])
        forged.pop("replay_id")
        forged["exact_replay_claimed"] = True
        forged_id = sha256_ref(canonical_json_bytes(forged))
        forged_record = {"replay_id": forged_id, **forged}
        path = self.root / "records" / "replays" / f"{forged_id[7:]}.json"
        path.write_bytes(canonical_json_bytes(forged_record))
        with self.assertRaises(ReplayError):
            self.runtime.replays.get_replay(forged_id)

    def test_replay_classification_bounds_model_state_expansion(self):
        original = self.runtime.ask(
            {"question": "Bound model metadata", "mode": "evidence_only"}
        )
        fake_states = []
        for index in range(101):
            fake_states.append(
                {
                    "state_id": "sha256:" + f"{index:064x}",
                    "model": {
                        "provider": "local",
                        "runtime": "fixture",
                        "runtime_version": "1",
                        "model_id": "m",
                        "revision": str(index),
                        "quantization": None,
                    },
                    "execution": {
                        "council_seat": None,
                        "stochastic": False,
                        "seed": 1,
                        "sampling": {},
                    },
                }
            )
        with mock.patch.object(self.runtime.models, "list_states", return_value=fake_states):
            classification = self.runtime.replay_classify(original["run_id"])
        self.assertEqual(len(classification["model_states"]), 100)
        self.assertEqual(classification["model_state_total"], 101)
        self.assertTrue(classification["model_states_truncated"])

    def test_missing_bound_file_is_not_advertised_as_executable(self):
        file_record = self.runtime.upload_file(
            {
                "filename": "bound.txt",
                "media_type": "text/plain",
                "content_base64": "Ym91bmQ=",
            }
        )["file"]
        original = self.runtime.ask(
            {
                "question": "Can missing context execute?",
                "mode": "evidence_only",
                "file_ids": [file_record["file_id"]],
            }
        )
        self.runtime.store._object_path(file_record["object_id"]).unlink()
        classification = self.runtime.replay_classify(original["run_id"])
        self.assertFalse(classification["can_execute"])
        self.assertEqual(classification["classification"], "unavailable_original_context")
        self.assertEqual(classification["unavailable_file_ids"], [file_record["file_id"]])

    def test_timeline_uses_absolute_time_and_ignores_per_run_state_ids(self):
        earlier = self.runtime.interactions.create_run(
            question="Offset ordering",
            mode="evidence_only",
            requester_kind="human",
            created_at="2026-01-01T01:00:00+01:00",
            evidence_state="unknown",
            replayability="R3",
        )
        later = self.runtime.interactions.create_run(
            question="Offset ordering",
            mode="evidence_only",
            requester_kind="human",
            created_at="2026-01-01T00:30:00Z",
            evidence_state="unknown",
            replayability="R3",
        )
        base_model = {
            "provider": "local",
            "runtime": "fixture",
            "runtime_version": "1",
            "model_id": "same-model",
            "revision": "same-revision",
            "quantization": None,
        }
        base_execution = {
            "council_seat": None,
            "stochastic": False,
            "seed": 7,
            "sampling": {"temperature": 0},
        }
        states = [
            {
                "state_id": "sha256:" + "1" * 64,
                "model": copy.deepcopy(base_model),
                "execution": copy.deepcopy(base_execution),
                "system": {"control_run_id": earlier["run_id"]},
            },
            {
                "state_id": "sha256:" + "2" * 64,
                "model": copy.deepcopy(base_model),
                "execution": copy.deepcopy(base_execution),
                "system": {"control_run_id": later["run_id"]},
            },
        ]
        with mock.patch.object(self.runtime.models, "list_states", return_value=states) as listing:
            timeline = self.runtime.research_timeline(earlier["run_id"])
        self.assertEqual(listing.call_count, 1)
        self.assertEqual(
            [row["run_id"] for row in timeline["runs"]],
            [earlier["run_id"], later["run_id"]],
        )
        self.assertFalse(timeline["transitions"][0]["model_state_changed"])

    def test_webui_and_bootstrap_contracts_report_additive_phase7(self):
        webui_contract = json.loads(
            (Path(__file__).resolve().parents[1] / "ai" / "webui-contract.json").read_text(
                encoding="utf-8"
            )
        )
        bootstrap = json.loads(
            (Path(__file__).resolve().parents[1] / "README4AI.md").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(
            webui_contract["replay_compare"]["phase7_replay_execution_implemented"]
        )
        self.assertFalse(webui_contract["replay_compare"]["comparison_is_replay_execution"])
        self.assertEqual(bootstrap["agent_api"]["status"], "implemented_phase6")
        self.assertTrue(bootstrap["agent_api"]["phase7_replay_execution"])


if __name__ == "__main__":
    unittest.main()
