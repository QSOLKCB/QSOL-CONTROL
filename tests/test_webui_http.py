import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from webui.server import ControlWebUIServer, WebUIConfig


class WebUIHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = ControlWebUIServer(WebUIConfig(control_root=Path(self.temp.name), port=0))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address[:2]
        self.base = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, path, *, method="GET", body=None, token=None, extra_headers=None):
        data = None
        headers = {"Accept": "application/json"}
        headers.update(extra_headers or {})
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token:
            headers["X-QSOL-Control-Token"] = token
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, dict(response.headers), json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), json.loads(exc.read())

    def test_session_bootstrap_then_token_required_for_api_reads_and_writes(self):
        status, headers, session = self.request("/api/session")
        self.assertEqual(status, 200)
        self.assertIn("session_token", session)
        self.assertIn("Content-Security-Policy", headers)
        status, _, error = self.request("/api/collections")
        self.assertEqual(status, 400)
        self.assertIn("session token", error["error"])
        token = session["session_token"]
        status, _, payload = self.request("/api/collections", token=token)
        self.assertEqual(status, 200)
        self.assertEqual(payload["collections"], [])
        status, _, error = self.request("/api/collections", method="POST", body={"name": "Blocked"})
        self.assertEqual(status, 400)
        self.assertIn("session token", error["error"])
        status, _, created = self.request("/api/collections", method="POST", token=token, body={"name": "Allowed"})
        self.assertEqual(status, 201)
        self.assertEqual(created["name"], "Allowed")

    def test_dns_rebinding_host_and_cross_origin_mutations_are_rejected(self):
        status, _, error = self.request("/api/session", extra_headers={"Host": "attacker.example"})
        self.assertEqual(status, 400)
        self.assertIn("loopback Host", error["error"])
        status, _, session = self.request("/api/session")
        self.assertEqual(status, 200)
        token = session["session_token"]
        status, _, error = self.request("/api/collections", method="POST", token=token, body={"name": "Cross origin"}, extra_headers={"Origin": "http://attacker.example"})
        self.assertEqual(status, 400)
        self.assertIn("Origin must be loopback", error["error"])

    def test_static_app_uses_strict_security_headers(self):
        req = urllib.request.Request(self.base + "/", method="GET")
        with urllib.request.urlopen(req, timeout=5) as response:
            body = response.read().decode("utf-8")
            self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            self.assertIn("MODEL_STATE ≠ MODEL_MIND", body)


if __name__ == "__main__":
    unittest.main()
