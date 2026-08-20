from __future__ import annotations

import http.client
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from adapters.consensus import (
    ConsensusAdapterError,
    ExternalConsensusAdapter,
    build_intent,
    validate_receipt,
)
from api.remote_http import (
    REMOTE_REQUEST_PROTOCOL,
    RemoteGatewayConfig,
    RemoteGatewayError,
    RemotePrincipal,
    build_server,
    load_gateway_config,
    token_digest,
)
from storage.control_store import ControlStore
from webui.common import WebUIConfig

ROOT = Path(__file__).resolve().parents[1]
REMOTE_TOKEN = "fixture-token-01234567890123456789"
EMPTY_ACCESS = {
    "max_privacy_class": "INTERNAL",
    "file_ids": [],
    "collection_ids": [],
    "run_ids": [],
    "model_state_ids": [],
    "replay_ids": [],
}


class RemoteGatewayTests(unittest.TestCase):
    def test_non_loopback_requires_explicit_tls(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "gateway.json"
            value = {
                "protocol": "qsol-control-remote-gateway/1",
                "bind": "0.0.0.0",
                "port": 9443,
                "allow_non_loopback": True,
                "allowed_hosts": ["control.example"],
                "tls": {
                    "enabled": False,
                    "cert_file": None,
                    "key_file": None,
                    "minimum_version": "TLSv1.2",
                },
                "principals": [
                    {
                        "principal_id": "fixture",
                        "token_sha256": token_digest(REMOTE_TOKEN),
                        "caller_kind": "human",
                        "caller_id": "fixture",
                        "allowed_operations": ["control.health"],
                        "record_access": EMPTY_ACCESS,
                    }
                ],
            }
            path.write_text(json.dumps(value), encoding="utf-8")
            path.chmod(0o600)
            with self.assertRaisesRegex(RemoteGatewayError, "requires TLS"):
                load_gateway_config(path)

    def test_remote_gateway_authenticates_and_does_not_accept_self_asserted_caller(self):
        with tempfile.TemporaryDirectory() as temp:
            principal = RemotePrincipal(
                principal_id="mobile",
                token_sha256=token_digest(REMOTE_TOKEN),
                caller_kind="human",
                caller_id="mobile",
                allowed_operations=frozenset({"control.health"}),
            )
            gateway = RemoteGatewayConfig(
                bind="127.0.0.1",
                port=0,
                allowed_hosts=frozenset({"127.0.0.1", "localhost"}),
                principals=(principal,),
                tls_enabled=False,
                tls_cert_file=None,
                tls_key_file=None,
                allow_non_loopback=False,
            )
            server = build_server(gateway, WebUIConfig(control_root=Path(temp) / "store"))
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                body = json.dumps(
                    {
                        "protocol": REMOTE_REQUEST_PROTOCOL,
                        "request_id": "remote-1",
                        "operation": "control.health",
                        "params": {},
                    }
                )
                connection.request(
                    "POST",
                    "/v1/agent",
                    body=body,
                    headers={"Authorization": f"Bearer {REMOTE_TOKEN}", "Content-Type": "application/json"},
                )
                response = connection.getresponse()
                payload = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["protocol"], "qsol-control-agent-response/1")

                spoofed = json.dumps(
                    {
                        "protocol": REMOTE_REQUEST_PROTOCOL,
                        "request_id": "remote-2",
                        "operation": "control.health",
                        "params": {},
                        "caller": {"kind": "ai", "id": "self-awarded"},
                    }
                )
                connection.request(
                    "POST",
                    "/v1/agent",
                    body=spoofed,
                    headers={"Authorization": f"Bearer {REMOTE_TOKEN}", "Content-Type": "application/json"},
                )
                rejected = connection.getresponse()
                rejected.read()
                self.assertEqual(rejected.status, 400)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_short_bearer_token_is_rejected_even_if_digest_is_configured(self):
        with tempfile.TemporaryDirectory() as temp:
            short = "short-token"
            principal = RemotePrincipal(
                principal_id="short",
                token_sha256=token_digest(short),
                caller_kind="human",
                caller_id="short",
                allowed_operations=frozenset({"control.health"}),
            )
            gateway = RemoteGatewayConfig(
                bind="127.0.0.1",
                port=0,
                allowed_hosts=frozenset({"127.0.0.1"}),
                principals=(principal,),
                tls_enabled=False,
                tls_cert_file=None,
                tls_key_file=None,
                allow_non_loopback=False,
            )
            server = build_server(gateway, WebUIConfig(control_root=Path(temp) / "store"))
            self.assertIsNone(server.authenticate(f"Bearer {short}"))
            server.server_close()


class ConsensusExtensionTests(unittest.TestCase):
    def test_external_consensus_receipt_is_exact_intent_bound_and_coordination_only(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ControlStore(Path(temp) / "store")
            fingerprint = store.fingerprint()["fingerprint"]
            intent = build_intent(
                operation="control.collection.create",
                params={"name": "fixture"},
                expected_store_fingerprint=fingerprint,
            )
            adapter = ExternalConsensusAdapter(
                [sys.executable, str(ROOT / "tests" / "fixtures" / "fake_consensus_provider.py")]
            )
            health = adapter.health()
            self.assertFalse(health["consensus_algorithm_owned_by_control"])
            receipt = adapter.propose(intent)
            self.assertEqual(receipt["intent_id"], intent["intent_id"])
            self.assertEqual(receipt["authority"], "coordination-only")
            self.assertFalse(receipt["semantic_authority_claimed"])
            self.assertEqual(adapter.verify(receipt), receipt)

    def test_unsatisfied_quorum_and_authority_escalation_fail_closed(self):
        receipt = {
            "protocol": "qsol-control-consensus-receipt/1",
            "intent_id": "sha256:" + "1" * 64,
            "cluster_id": "fixture",
            "epoch": 1,
            "commit_index": 2,
            "member_set_id": "sha256:" + "2" * 64,
            "quorum": {"required": 3, "observed": 2},
            "state_fingerprint": "sha256:" + "3" * 64,
            "provider_protocol": "fixture/1",
            "verified": True,
            "authority": "coordination-only",
            "semantic_authority_claimed": False,
        }
        with self.assertRaisesRegex(ConsensusAdapterError, "quorum"):
            validate_receipt(receipt)
        receipt["quorum"] = {"required": 2, "observed": 2}
        receipt["authority"] = "truth"
        with self.assertRaisesRegex(ConsensusAdapterError, "authority"):
            validate_receipt(receipt)


class MobileAndPermanentBoundaryTests(unittest.TestCase):
    def test_native_reference_clients_are_thin_https_remote_clients(self):
        ios = (ROOT / "mobile" / "ios" / "QSOLControl" / "ControlClient.swift").read_text(encoding="utf-8")
        android = (ROOT / "mobile" / "android" / "app" / "src" / "main" / "java" / "org" / "qsol" / "control" / "ControlClient.kt").read_text(encoding="utf-8")
        manifest = (ROOT / "mobile" / "android" / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
        for text in (ios, android):
            self.assertIn("qsol-control-remote-request/1", text)
            self.assertIn("/v1/agent", text)
            self.assertIn("Bearer", text)
            self.assertNotIn("truth_score", text)
            self.assertNotIn("chain_of_thought", text)
        self.assertIn("usesCleartextTraffic=\"false\"", manifest)

    def test_permanent_nongoals_are_forbidden_not_deferred_features(self):
        value = json.loads((ROOT / "ai" / "permanent-nongoals.json").read_text(encoding="utf-8"))
        self.assertEqual(value["status"], "permanent")
        self.assertEqual(
            set(value["items"]),
            {
                "automatic_truth_scoring",
                "hidden_chain_of_thought_capture",
                "literal_geometric_cognition_claims",
                "biological_claims_from_dna_codec",
                "phi_traversal_physical_optimality_claims",
            },
        )
        for row in value["items"].values():
            self.assertFalse(row["implemented"])
            self.assertTrue(row["forbidden"])


if __name__ == "__main__":
    unittest.main()
