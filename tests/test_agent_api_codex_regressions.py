import tempfile
import unittest
from pathlib import Path

from api.common import (
    MAX_MUTATIONS_PER_PROCESS,
    MAX_REQUESTS_PER_PROCESS,
    MAX_RESPONSE_BYTES,
    AgentAPIError,
    QuotaState,
    canonical_json_bytes,
    error_envelope,
)
from api.dispatcher import AgentAPIDispatcher
from api.stdio import process_line
from webui.common import WebUIConfig


class AgentAPICodexRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.dispatcher = AgentAPIDispatcher(WebUIConfig(control_root=self.root, port=0))
        self.counter = 0

    def tearDown(self):
        self.temp.cleanup()

    def request(self, operation, params=None, *, caller_id="agent-a", dispatcher=None):
        self.counter += 1
        target = dispatcher or self.dispatcher
        return target.handle(
            {
                "protocol": "qsol-control-agent-request/1",
                "request_id": f"codex-{self.counter}",
                "caller": {"kind": "ai", "id": caller_id},
                "operation": operation,
                "params": params or {},
            }
        )

    def test_process_request_quota_cannot_be_bypassed_by_rotating_caller_id(self):
        self.dispatcher._process_quota = QuotaState(
            requests=MAX_REQUESTS_PER_PROCESS - 1,
            mutations=0,
        )
        first = self.request("control.health", caller_id="rotating-a")
        second = self.request("control.health", caller_id="rotating-b")
        self.assertTrue(first["ok"])
        self.assertFalse(second["ok"])
        self.assertEqual(second["error"]["code"], "QUOTA_EXCEEDED")
        self.assertEqual(second["error"]["details"]["kind"], "process_requests")

    def test_process_mutation_quota_blocks_new_spoofed_caller(self):
        self.dispatcher._process_quota = QuotaState(
            requests=0,
            mutations=MAX_MUTATIONS_PER_PROCESS,
        )
        response = self.request(
            "control.file.put",
            {
                "filename": "blocked.txt",
                "content_base64": "eA==",
            },
            caller_id="brand-new-id",
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "QUOTA_EXCEEDED")
        self.assertEqual(response["error"]["details"]["kind"], "process_mutations")

    def test_invalid_council_members_do_not_create_a_run(self):
        configured = AgentAPIDispatcher(
            WebUIConfig(
                control_root=self.root,
                port=0,
                nexus_command=("this-command-must-never-run",),
            )
        )
        before = configured.runtime.control._list_run_ids()
        response = self.request(
            "control.ask",
            {
                "question": "Reject before persistence",
                "mode": "council",
                "members": [],
            },
            dispatcher=configured,
        )
        after = configured.runtime.control._list_run_ids()
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "INVALID_REQUEST")
        self.assertEqual(before, after)

    def test_unknown_ask_parameter_is_rejected_before_persistence(self):
        before = self.dispatcher.runtime.control._list_run_ids()
        response = self.request(
            "control.ask",
            {
                "question": "Typo should not execute",
                "mode": "council",
                "nexus_evidence_ref": [],
            },
        )
        after = self.dispatcher.runtime.control._list_run_ids()
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "INVALID_REQUEST")
        self.assertEqual(before, after)

    def test_error_envelope_never_exceeds_response_byte_limit(self):
        response = error_envelope(
            "bounded-error",
            "control.health",
            AgentAPIError("INVALID_REQUEST", "x" * (MAX_RESPONSE_BYTES + 4096)),
        )
        self.assertLessEqual(len(canonical_json_bytes(response)), MAX_RESPONSE_BYTES)
        self.assertEqual(response["error"]["code"], "RESOURCE_LIMIT")

    def test_falsy_memory_run_id_is_invalid_not_global_scope(self):
        seeded = self.request(
            "control.ask",
            {"question": "Seed one run", "mode": "evidence_only"},
        )
        self.assertTrue(seeded["ok"])
        response = self.request(
            "control.memory.get",
            {"run_id": "", "max_records": 10},
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "INVALID_REQUEST")

    def test_nan_in_jsonl_is_rejected_as_invalid_json(self):
        raw = (
            b'{"protocol":"qsol-control-agent-request/1",'
            b'"request_id":"nan-test",'
            b'"caller":{"kind":"ai","id":"agent"},'
            b'"operation":"control.ask",'
            b'"params":{"question":"x","mode":"evidence_only","noise":NaN}}\n'
        )
        response = process_line(self.dispatcher, raw)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "INVALID_JSON")

    def test_capabilities_advertise_non_spoofable_process_ceiling(self):
        response = self.request("control.capabilities")
        self.assertTrue(response["ok"])
        limits = response["result"]["limits"]
        self.assertEqual(limits["max_requests_per_process"], MAX_REQUESTS_PER_PROCESS)
        self.assertEqual(limits["max_mutations_per_process"], MAX_MUTATIONS_PER_PROCESS)
        self.assertFalse(limits["caller_id_is_trusted_quota_identity"])


if __name__ == "__main__":
    unittest.main()
