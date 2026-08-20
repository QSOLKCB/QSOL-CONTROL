from __future__ import annotations

import http.client
import json
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from adapters.consensus import (
    MAX_RESPONSE_BYTES,
    ConsensusAdapterError,
    ExternalConsensusAdapter,
    build_intent,
    canonical_json_bytes,
    sha256_ref,
)
from api.common import MAX_REQUESTS_PER_PROCESS
from api.remote_http import (
    MAX_CONNECTIONS,
    QUOTA_WINDOW_SECONDS,
    REMOTE_REQUEST_PROTOCOL,
    RemoteGatewayConfig,
    RemoteGatewayError,
    RemotePrincipal,
    RemoteRecordAccess,
    build_server,
    token_digest,
)
from storage.control_store import ControlStore
from webui.common import WebUIConfig

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "codex-regression-token-012345678901234567890"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def principal(
    *,
    operations: set[str],
    max_privacy: str = "INTERNAL",
    file_ids: frozenset[str] = frozenset(),
) -> RemotePrincipal:
    return RemotePrincipal(
        principal_id="codex-principal",
        token_sha256=token_digest(TOKEN),
        caller_kind="human",
        caller_id="codex-caller",
        allowed_operations=frozenset(operations),
        record_access=RemoteRecordAccess(
            max_privacy_class=max_privacy,
            file_ids=file_ids,
            collection_ids=frozenset(),
            run_ids=frozenset(),
            model_state_ids=frozenset(),
            replay_ids=frozenset(),
        ),
    )


def gateway_for(principal_value: RemotePrincipal, *, bind: str = "127.0.0.1") -> RemoteGatewayConfig:
    return RemoteGatewayConfig(
        bind=bind,
        port=free_port(),
        allowed_hosts=frozenset({"127.0.0.1"}),
        principals=(principal_value,),
        tls_enabled=False,
        tls_cert_file=None,
        tls_key_file=None,
        allow_non_loopback=False,
    )


class RemoteGatewayCodexRegressions(unittest.TestCase):
    def test_long_running_gateway_renews_agent_api_quota_window(self):
        with tempfile.TemporaryDirectory() as temp:
            server = build_server(
                gateway_for(principal(operations={"control.health"})),
                WebUIConfig(control_root=Path(temp) / "store"),
            )
            try:
                server.dispatcher._process_quota.requests = MAX_REQUESTS_PER_PROCESS
                server._quota_window_started -= QUOTA_WINDOW_SECONDS + 1.0
                response = server.dispatch_local(
                    {
                        "protocol": "qsol-control-agent-request/1",
                        "request_id": "quota-renewal",
                        "caller": {"kind": "human", "id": "codex-caller"},
                        "operation": "control.health",
                        "params": {},
                    }
                )
                self.assertTrue(response["ok"])
            finally:
                server.server_close()

    def test_restricted_file_requires_explicit_record_acl(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "store"
            record = ControlStore(root).put_file(
                b"restricted",
                filename="restricted.txt",
                privacy_class="RESTRICTED",
                retention_class="ARCHIVE",
                created_at="2026-08-20T14:00:00+00:00",
            )
            denied_server = build_server(
                gateway_for(
                    principal(
                        operations={"control.file.get"},
                        max_privacy="RESTRICTED",
                    )
                ),
                WebUIConfig(control_root=root),
            )
            try:
                with self.assertRaisesRegex(RemoteGatewayError, "not authorized"):
                    denied_server.authorize(
                        denied_server.gateway_config.principals[0],
                        "control.file.get",
                        {"file_id": record["file_id"], "include_content": True},
                    )
            finally:
                denied_server.server_close()

            allowed_server = build_server(
                gateway_for(
                    principal(
                        operations={"control.file.get"},
                        max_privacy="RESTRICTED",
                        file_ids=frozenset({record["file_id"]}),
                    )
                ),
                WebUIConfig(control_root=root),
            )
            try:
                allowed_server.authorize(
                    allowed_server.gateway_config.principals[0],
                    "control.file.get",
                    {"file_id": record["file_id"], "include_content": True},
                )
            finally:
                allowed_server.server_close()

    def test_authenticated_principal_is_persisted_without_bearer_material(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "store"
            server = build_server(
                gateway_for(principal(operations={"control.health"})),
                WebUIConfig(control_root=root),
            )
            thread = threading.Thread(
                target=server.serve_forever,
                kwargs={"poll_interval": 0.01},
                daemon=True,
            )
            thread.start()
            try:
                connection = http.client.HTTPConnection(
                    "127.0.0.1", server.server_port, timeout=3
                )
                connection.request(
                    "POST",
                    "/v1/agent",
                    body=json.dumps(
                        {
                            "protocol": REMOTE_REQUEST_PROTOCOL,
                            "request_id": "audit-1",
                            "operation": "control.health",
                            "params": {},
                        }
                    ),
                    headers={
                        "Authorization": f"Bearer {TOKEN}",
                        "Content-Type": "application/json",
                    },
                )
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 200)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

            audit_files = sorted((root / "records" / "remote-audit").glob("*.json"))
            self.assertGreaterEqual(len(audit_files), 2)
            joined = "\n".join(path.read_text(encoding="utf-8") for path in audit_files)
            self.assertIn('"principal_id":"codex-principal"', joined)
            self.assertIn('"operation":"control.health"', joined)
            self.assertNotIn(TOKEN, joined)
            self.assertIn('"credential_material_captured":false', joined)

    def test_connection_slots_are_bounded_before_authentication(self):
        with tempfile.TemporaryDirectory() as temp:
            server = build_server(
                gateway_for(principal(operations={"control.health"})),
                WebUIConfig(control_root=Path(temp) / "store"),
            )
            acquired = 0
            try:
                for _ in range(MAX_CONNECTIONS):
                    self.assertTrue(server._connection_slots.acquire(blocking=False))
                    acquired += 1
                self.assertFalse(server._connection_slots.acquire(blocking=False))
            finally:
                for _ in range(acquired):
                    server._connection_slots.release()
                server.server_close()

    def test_build_server_revalidates_plaintext_non_loopback_programmatic_config(self):
        invalid = RemoteGatewayConfig(
            bind="0.0.0.0",
            port=free_port(),
            allowed_hosts=frozenset({"control.example"}),
            principals=(principal(operations={"control.health"}),),
            tls_enabled=False,
            tls_cert_file=None,
            tls_key_file=None,
            allow_non_loopback=True,
        )
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RemoteGatewayError, "requires TLS"):
                build_server(invalid, WebUIConfig(control_root=Path(temp) / "store"))


class ConsensusCodexRegressions(unittest.TestCase):
    def test_handcrafted_rehashed_intent_is_fully_revalidated_before_provider(self):
        valid = build_intent(
            operation="control.collection.create",
            params={"name": "fixture"},
            expected_store_fingerprint="sha256:" + "1" * 64,
        )
        hostile = dict(valid)
        hostile["operation"] = "control.unknown-mutation"
        payload = {key: value for key, value in hostile.items() if key != "intent_id"}
        hostile["intent_id"] = sha256_ref(canonical_json_bytes(payload))
        adapter = ExternalConsensusAdapter(
            [sys.executable, str(ROOT / "tests" / "fixtures" / "fake_consensus_provider.py")]
        )
        with self.assertRaisesRegex(ConsensusAdapterError, "known CONTROL mutation"):
            adapter.propose(hostile)

    def test_provider_stdout_is_capped_while_child_is_running(self):
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / "overflow.py"
            script.write_text(
                "import sys\n"
                f"sys.stdout.buffer.write(b'x' * {MAX_RESPONSE_BYTES + 65536})\n"
                "sys.stdout.flush()\n",
                encoding="utf-8",
            )
            adapter = ExternalConsensusAdapter([sys.executable, str(script)], timeout_seconds=5)
            with self.assertRaisesRegex(ConsensusAdapterError, "stdout exceeds byte limit"):
                adapter.health()


if __name__ == "__main__":
    unittest.main()
