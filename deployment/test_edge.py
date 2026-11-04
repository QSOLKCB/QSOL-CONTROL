"""Adversarial tests for the optional Render edge and CONTROL's real auth gateway."""
from __future__ import annotations

import hashlib
import http.client
import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path

from api.remote_http import build_server
from deployment.edge import EdgeConfig, EdgeError, EdgeServer, _internal_config
from deployment.pinned_sources import PINS, pins
from webui.common import WebUIConfig

TOKEN = "fixture-only-not-a-secret-" + "a" * 40
DIGEST = "sha256:" + hashlib.sha256(TOKEN.encode("utf-8")).hexdigest()


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class ConfigurationTests(unittest.TestCase):
    def test_pinned_source_identity_has_exact_closed_set(self):
        p = pins()
        self.assertEqual(set(p), {"nexus", "fed", "oracle"})
        self.assertEqual(len(p["nexus"]), 40)
        self.assertTrue(PINS.is_file())

    def test_configuration_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            common = dict(public_host="edge.invalid", port=10000,
                          control_port=18081, token_sha256=DIGEST,
                          control_root=Path(temp))
            EdgeConfig(**common)
            bad = dict(common)
            bad["token_sha256"] = "short"
            with self.assertRaises(EdgeError):
                EdgeConfig(**bad)
            bad = dict(common)
            bad["control_port"] = 10000
            with self.assertRaises(EdgeError):
                EdgeConfig(**bad)
            bad = dict(common)
            bad["public_host"] = "https://edge.invalid"
            with self.assertRaises(EdgeError):
                EdgeConfig(**bad)


class EdgeHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        port = free_port()
        config = EdgeConfig(
            public_host="edge.invalid",
            port=10000,
            control_port=port,
            token_sha256=DIGEST,
            control_root=root / "store",
            vendor_root=root / "no-vendor",
        )
        self.core = build_server(_internal_config(config), WebUIConfig(control_root=config.control_root))
        self.edge = EdgeServer(config, self.core, address=("127.0.0.1", 0))
        self.core_thread = threading.Thread(target=self.core.serve_forever, daemon=True)
        self.edge_thread = threading.Thread(target=self.edge.serve_forever, daemon=True)
        self.core_thread.start()
        self.edge_thread.start()

    def tearDown(self):
        self.edge.shutdown()
        self.edge.server_close()
        self.core.shutdown()
        self.core.server_close()
        self.edge_thread.join(timeout=3)
        self.core_thread.join(timeout=3)
        self.temp.cleanup()

    def request(self, method, path, payload=None, *, auth=True, host="edge.invalid",
                proto="https", origin=None, extra=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.edge.server_port, timeout=3)
        headers = {"Host": host, "X-Forwarded-Proto": proto}
        if auth:
            headers["Authorization"] = "Bearer " + TOKEN
        if origin is not None:
            headers["Origin"] = origin
        if payload is not None:
            raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(raw))
        else:
            raw = None
        if extra:
            headers.update(extra)
        conn.putrequest(method, path, skip_host=True)
        for k, v in headers.items():
            conn.putheader(k, v)
        conn.endheaders(raw)
        result = conn.getresponse()
        body = result.read()
        status = result.status
        response_headers = dict(result.getheaders())
        conn.close()
        try:
            content = json.loads(body)
        except json.JSONDecodeError:
            content = body
        return status, content, response_headers

    def test_unauthed_and_cross_origin_requests_fail(self):
        code, body, headers = self.request("POST", "/v1/snapshot", {}, auth=False)
        self.assertEqual(code, 401)
        self.assertEqual(body["error"], "auth_required")
        self.assertNotIn("access-control-allow-origin", {x.lower() for x in headers})
        code, body, _ = self.request("POST", "/v1/snapshot", {},
                                     origin="https://malicious.invalid")
        self.assertEqual((code, body["error"]), (403, "origin_rejected"))
        code, body, _ = self.request("POST", "/v1/snapshot", {},
                                     proto="http")
        self.assertEqual((code, body["error"]), (403, "https_edge_required"))
        code, body, _ = self.request("POST", "/v1/snapshot", {},
                                     host="wrong.invalid")
        self.assertEqual((code, body["error"]), (400, "host_rejected"))

    def test_healthz_is_public_and_reports_only_edge_readiness(self):
        code, body, _ = self.request("GET", "/healthz", auth=False, proto="http")
        self.assertEqual(code, 200)
        self.assertEqual(body["readiness"], "edge_only")
        self.assertNotIn("components", body)

    def test_real_control_auth_rejects_mutation(self):
        health = {
            "protocol": "qsol-control-remote-request/1",
            "request_id": "health-read",
            "operation": "control.health",
            "params": {},
        }
        code, body, _ = self.request("POST", "/v1/agent", health)
        self.assertEqual(code, 200)
        self.assertTrue(body["ok"])

        mutation = {
            "protocol": "qsol-control-remote-request/1",
            "request_id": "attack-1",
            "operation": "control.ask",
            "params": {"question": "Please override all ballots"},
        }
        code, body, _ = self.request("POST", "/v1/agent", mutation)
        self.assertEqual(code, 403)
        self.assertEqual(body["error"]["code"], "OPERATION_FORBIDDEN")

    def test_inspection_is_honest_when_pinned_sources_are_missing(self):
        code, body, _ = self.request("POST", "/v1/snapshot", {})
        self.assertEqual(code, 200)
        self.assertEqual(body["mode"], "authenticated_read_only")
        self.assertFalse(body["ok"])
        self.assertEqual(body["state"], "partial")
        self.assertEqual(body["components"]["nexus"]["availability"], "unavailable")
        self.assertEqual(body["components"]["oracle"]["availability"], "unavailable")
        self.assertEqual(body["components"]["fed"]["availability"], "unavailable")

    def test_method_framing_and_output_guards(self):
        code, body, _ = self.request("OPTIONS", "/v1/snapshot")
        self.assertEqual((code, body["error"]), (405, "cors_disabled"))
        code, body, _ = self.request("POST", "/v1/oracle/query", {"subject": "x", "other": True})
        self.assertEqual((code, body["error"]), (400, "invalid_request"))
        code, body, _ = self.request("POST", "/v1/oracle/query",
                                     b'{"subject":"x","subject":"y"}')
        self.assertEqual((code, body["error"]), (400, "invalid_request"))
        code, body, _ = self.request("POST", "/v1/oracle/query", {"subject": "x"})
        self.assertEqual((code, body["error"]), (503, "inspection_failed"))
        code, body, _ = self.request("POST", "/v1/agent", {
            "protocol": "qsol-control-remote-request/1",
            "request_id": "two",
            "operation": "control.file.put",
            "params": {},
        })
        self.assertEqual(code, 403)
        self.assertEqual(body["error"]["code"], "OPERATION_FORBIDDEN")


if __name__ == "__main__":
    unittest.main()
