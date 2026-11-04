"""Adversarial tests for the optional Render edge and CONTROL's real auth gateway."""
from __future__ import annotations

import hashlib
import http.client
import json
import socket
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from deployment import pinned_sources
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

    def test_pins_reject_modified_shadow_and_ignored_files(self):
        """Use local Git fixtures; no network calls and no trusted clean-index assumption."""
        with tempfile.TemporaryDirectory() as temp:
            tmp = Path(temp)
            checkout = tmp / "donors" / "nexus"
            checkout.mkdir(parents=True)
            origin = "https://github.com/QSOLKCB/QSOL-NEXUS.git"

            def git(*args):
                return subprocess.run(
                    ["git", "-C", str(checkout), *args],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True,
                ).stdout.strip()

            git("init", "-q")
            source = checkout / "module.py"
            original = "VALUE = 1\n"
            source.write_text(original, encoding="utf-8")
            (checkout / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
            git("add", "module.py", ".gitignore")
            git("-c", "user.name=Fixture", "-c", "user.email=fixture@invalid",
                "commit", "-qm", "Pinned source fixture")
            git("remote", "add", "origin", origin)
            sha = git("rev-parse", "HEAD")
            pinfile = tmp / "pins.json"
            pinfile.write_text(json.dumps({
                "protocol": "qsol-edge-pinned-sources/1",
                "commits": {"nexus": sha},
            }), encoding="utf-8")

            with (patch.object(pinned_sources, "REPOS", {"nexus": origin}),
                  patch.object(pinned_sources, "VENDOR", checkout.parent),
                  patch.object(pinned_sources, "PINS", pinfile)):
                self.assertEqual(pinned_sources.verify_sources(), {"nexus": sha})

                # Even an assume-unchanged index flag may not mask content drift.
                git("update-index", "--assume-unchanged", "module.py")
                source.write_text("VALUE = 999\n", encoding="utf-8")
                with self.assertRaises(pinned_sources.PinError):
                    pinned_sources.verify_sources()
                source.write_text(original, encoding="utf-8")
                git("update-index", "--no-assume-unchanged", "module.py")
                self.assertEqual(pinned_sources.verify_sources(), {"nexus": sha})

                rogue = checkout / "shadow.py"
                rogue.write_text("VALUE = 123\n", encoding="utf-8")
                with self.assertRaises(pinned_sources.PinError):
                    pinned_sources.verify_sources()
                rogue.unlink()

                ignored = checkout / "shadow.pyc"
                ignored.write_bytes(b"malicious-import-bytecode")
                with self.assertRaises(pinned_sources.PinError):
                    pinned_sources.verify_sources()
                ignored.unlink()

                source.unlink()
                source.symlink_to(checkout / ".gitignore")
                with self.assertRaises(pinned_sources.PinError):
                    pinned_sources.verify_sources()

    def test_discovery_documents_are_synchronized(self):
        root = Path(__file__).resolve().parents[1]
        def read(name):
            return json.loads((root / name).read_text(encoding="utf-8"))

        core = read("manifest.json")
        machine = read("README4AI.md")
        extensions = read("extensions/manifest.json")
        extension_bootstrap = read("extensions/README4AI.md")
        remote = read("ai/remote-gateway-contract.json")
        edge = read("deployment/edge-contract.json")
        self.assertEqual(core["interfaces"]["optional_render_readonly_edge"],
                         "deployment/edge.py")
        for path in ("deployment/README.md", "deployment/edge-contract.json",
                     "render.yaml"):
            self.assertIn(path, core["documentation"])
        self.assertEqual(machine["optional_extensions"]["render_readonly_edge"]["protocol"],
                         "qsol-control-render-edge/1")
        self.assertEqual(extensions["extensions"]["render_readonly_edge"]["status"],
                         "implemented-source-not-deployed")
        self.assertIn("render_readonly_authenticated_operator_preview",
                      extension_bootstrap["extension_surfaces"])
        self.assertEqual(remote["render_edge_preview"]["source"],
                         "deployment/edge.py")
        self.assertEqual(edge["status"], "implemented_source_not_deployed")
        self.assertFalse(edge["security"]["durable_multiuser"])
        self.assertEqual(edge["public_endpoints"][2]["operations"],
                         ["control.health", "control.capabilities"])
        self.assertIn("PUBLIC_READONLY_INSPECTION != REMOTE_MUTATION",
                      extension_bootstrap["invariants"])

    def test_nexus_probe_uses_disjoint_temporary_roots(self):
        """Discovery may initialize the Stenographer; donor trees stay read-only."""
        from unittest.mock import MagicMock
        from deployment.edge import _nexus
        with tempfile.TemporaryDirectory() as outer:
            vendor = Path(outer)
            source = vendor / "nexus" / "src" / "nexus_runtime"
            source.mkdir(parents=True)
            (source / "__main__.py").write_text("pass\\n".replace("\\n", "\n"), encoding="utf-8")
            created = []
            adapter = MagicMock()
            adapter.__enter__.return_value.discover.return_value = {
                "nexus_runtime_version": "2.1.1",
                "nexus_protocol": "nexus/0.15",
                "control_transport": "jsonl_stdio",
                "operations": ["system.health", "system.operations"],
                "operations_sha256": "sha256:fixture",
            }
            def factory(command, *, cwd, timeout_seconds):
                self.assertNotEqual(cwd, vendor / "nexus" / "src")
                self.assertEqual(command[1:4], ["-B", "-I", "-c"])
                self.assertEqual(command[5], str((vendor / "nexus" / "src").resolve()))
                self.assertEqual(timeout_seconds, 12.0)
                self.assertEqual(command[6::2],
                                 ["--world", "--auth-root", "--trap-root", "--stenographer-root"])
                for target in command[7::2]:
                    self.assertTrue(Path(target).is_relative_to(cwd))
                    self.assertFalse(Path(target).is_relative_to(vendor / "nexus"))
                # Simulate the real runtime's default Stenographer write.
                (cwd / ".nexus-stenographer").mkdir()
                created.append(cwd)
                return adapter
            with patch("deployment.edge.NexusCouncilAdapter.from_command", side_effect=factory):
                result = _nexus(vendor)
            self.assertEqual(result["availability"], "available")
            self.assertEqual(len(created), 1)
            self.assertFalse(created[0].exists())
            self.assertEqual((source / "__main__.py").read_text(), "pass\\n".replace("\\n", "\n"))
            self.assertEqual([p.name for p in source.iterdir()], ["__main__.py"])

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

    def test_anonymous_requests_cannot_spend_operator_quota(self):
        # Requests arrive on one proxy socket IP, so socket-IP limiting must
        # never let unauthenticated traffic starve a valid operator.
        from deployment.edge import MAX_RATE_PER_MINUTE
        payload = {
            "protocol": "qsol-control-remote-request/1",
            "request_id": "read-health",
            "operation": "control.health",
            "params": {},
        }
        for _ in range(MAX_RATE_PER_MINUTE + 8):
            code, body, _ = self.request("POST", "/v1/agent", payload, auth=False,
                                         extra={"X-Forwarded-For": "203.0.113.100"})
            self.assertEqual((code, body["error"]), (401, "auth_required"))
        for _ in range(MAX_RATE_PER_MINUTE):
            code, body, _ = self.request("POST", "/v1/agent", payload,
                                         extra={"X-Forwarded-For": "203.0.113.100"})
            self.assertEqual(code, 200)
            self.assertTrue(body["ok"])
        code, body, _ = self.request("POST", "/v1/agent", payload)
        self.assertEqual((code, body["error"]), (429, "rate_limited"))
        # Public assets never consume the credential's operation budget.
        code, _, _ = self.request("GET", "/", auth=False)
        self.assertEqual(code, 200)

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
