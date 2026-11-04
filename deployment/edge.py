#!/usr/bin/env python3
"""Read-only QSOL edge gateway for Render-managed TLS.

Render alone terminates public HTTPS. The established CONTROL remote Agent API
runs on 127.0.0.1 with its existing bearer/ACL/audit guards, never on an
externally reachable socket. The public edge explicitly admits only
read-only status, protocol inspection, and exact-subject ORACLE queries.

NOT a remote NEXUS Council or FED networking deployment. No persistent world.
"""
from __future__ import annotations

import argparse
import hmac
import http.client
import importlib.util
import json
import os
import re
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from adapters.nexus import NexusCouncilAdapter, NexusAdapterError
from adapters.oracle import OracleAdapter, OracleAdapterError
from api.remote_http import (
    RemoteGatewayConfig, RemotePrincipal, RemoteRecordAccess,
    build_server,
)
from webui.common import WebUIConfig
from deployment.pinned_sources import PINS, VENDOR, pins, verify_sources

ROOT = Path(__file__).resolve().parents[1]
EDGE_PROTOCOL = "qsol-control-render-edge/1"
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
HOST_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$")
MAX_BODY = 4096
MAX_AGENT_BODY = 16384
MAX_OUTPUT = 65536
MAX_THREADS = 24
MAX_RATE_PER_MINUTE = 35


class EdgeError(ValueError):
    pass


@dataclass(frozen=True)
class EdgeConfig:
    public_host: str
    port: int
    control_port: int
    token_sha256: str
    control_root: Path
    require_forwarded_https: bool = True
    vendor_root: Path = VENDOR

    def __post_init__(self) -> None:
        if not isinstance(self.public_host, str) or not HOST_RE.fullmatch(self.public_host):
            raise EdgeError("public hostname must be one exact DNS name")
        if self.public_host != self.public_host.lower() or ".." in self.public_host:
            raise EdgeError("public hostname must be canonical")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise EdgeError("public port out of range")
        if type(self.control_port) is not int or not 1 <= self.control_port <= 65535:
            raise EdgeError("loopback port out of range")
        if self.port == self.control_port:
            raise EdgeError("loopback and public port must differ")
        if not isinstance(self.token_sha256, str) or SHA256_RE.fullmatch(self.token_sha256) is None:
            raise EdgeError("operator token SHA-256 digest missing or malformed")
        if type(self.require_forwarded_https) is not bool:
            raise EdgeError("HTTPS edge policy must be explicit")
        if not isinstance(self.control_root, Path) or not self.control_root.is_absolute():
            raise EdgeError("CONTROL root must be absolute")
        if self.control_root.is_symlink():
            raise EdgeError("CONTROL root must not be symlinked")

    @classmethod
    def from_environment(cls) -> "EdgeConfig":
        hostname = os.environ.get("QSOL_EDGE_PUBLIC_HOST") or os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")
        port = int(os.environ.get("PORT", "10000"))
        local_port = int(os.environ.get("QSOL_EDGE_CONTROL_PORT", "18081"))
        return cls(
            public_host=hostname,
            port=port,
            control_port=local_port,
            token_sha256=os.environ.get("QSOL_GATEWAY_TOKEN_SHA256", ""),
            control_root=Path(os.environ.get("QSOL_EDGE_CONTROL_ROOT", "/tmp/qsol-edge-control")),
        )


def _json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _result(state: str, **details: Any) -> dict[str, Any]:
    return {"availability": state, **details, "authority": "none"}


def _nexus(vendor_root: Path) -> dict[str, Any]:
    root = vendor_root / "nexus"
    if not (root / "src" / "nexus_runtime" / "__main__.py").is_file():
        return _result("unavailable", reason="pinned_source_unavailable")
    try:
        # NEXUS creates a default Stenographer store at Path.cwd(), even
        # for system.health/system.operations. Never run it in a pinned tree.
        # Isolate all possible state roots from the donor checkout, and use
        # -I to prevent PYTHONPATH/site injection, -B to avoid bytecode writes.
        with tempfile.TemporaryDirectory(prefix="qsol-edge-nexus-") as scratch:
            workdir = Path(scratch)
            loader = (
                "import sys; "
                "sys.path.insert(0, sys.argv[1]); "
                "from nexus_runtime.__main__ import main; "
                "raise SystemExit(main(sys.argv[2:]))"
            )
            command = [
                sys.executable, "-B", "-I", "-c", loader,
                str((root / "src").resolve(strict=True)),
                "--world", str(workdir / "world"),
                "--auth-root", str(workdir / "auth"),
                "--trap-root", str(workdir / "trap"),
                "--stenographer-root", str(workdir / "stenographer"),
            ]
            with NexusCouncilAdapter.from_command(
                command, cwd=workdir, timeout_seconds=12.0,
            ) as adapter:
                discovery = adapter.discover()
        return _result(
            "available", runtime_version=discovery["nexus_runtime_version"],
            protocol=discovery["nexus_protocol"],
            transport=discovery["control_transport"],
            operations_count=len(discovery["operations"]),
            operations_sha256=discovery["operations_sha256"],
            council_exposed=False, worldstore_mutations_exposed=False,
        )
    except (NexusAdapterError, OSError, ValueError, KeyError):
        return _result("unavailable", reason="discovery_failed")


def _fed(vendor_root: Path) -> dict[str, Any]:
    root = vendor_root / "fed"
    source = root / "sdk" / "python" / "qsol_fed_sdk.py"
    fixture = root / "fixtures" / "phase6" / "conformance.json"
    if not source.is_file() or not fixture.is_file():
        return _result("unavailable", reason="pinned_source_unavailable")
    try:
        spec = importlib.util.spec_from_file_location("_qsol_fed_readonly", source)
        if spec is None or spec.loader is None:
            raise EdgeError("FED SDK unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        value = json.loads(fixture.read_text("utf-8"))
        result = module.conformance_result(value)
        return _result(
            "available", sdk_contract=module.SDK_CONTRACT,
            wire_protocol=module.WIRE_PROTOCOL,
            conformance="fixture_matched",
            receipt_sha256=module.object_id(result),
            federated_network_live=False, remote_execution=False,
        )
    except (ValueError, OSError, KeyError, TypeError, AttributeError, json.JSONDecodeError):
        return _result("unavailable", reason="conformance_failed")


def _oracle(vendor_root: Path) -> dict[str, Any]:
    root = vendor_root / "oracle"
    if not (root / "manifest.json").is_file():
        return _result("unavailable", reason="pinned_source_unavailable")
    try:
        availability = OracleAdapter(root).availability()
        if availability.get("availability") != "available":
            return _result("unavailable", reason="ledger_validation_failed")
        return _result(
            "available", protocol=availability.get("oracle_protocol", "QSOL-ORACLE/1"),
            ledger_events=availability.get("ledger_events"),
            ledger_head=availability.get("ledger_head"),
            ledger_read_only=True, feed_polling_live=False,
        )
    except (OracleAdapterError, OSError, ValueError, KeyError):
        return _result("unavailable", reason="ledger_validation_failed")


def _control(core_server: Any) -> dict[str, Any]:
    # The existing CONTROL dispatcher is the source of truth. No synthetic
    # success is returned if its real read-only health operation fails.
    try:
        request = {
            "protocol": "qsol-control-agent-request/1",
            "request_id": "edge-control-readonly",
            "caller": {"kind": "human", "id": "edge-readonly"},
            "operation": "control.health",
            "params": {},
        }
        response = core_server.dispatch_local(request)
        if response.get("ok") is not True:
            return _result("unavailable", reason="control_health_failed")
        return _result("available", protocol="QSOL-CONTROL/0.1",
                       operation="control.health", mutations_exposed=False)
    except (ValueError, OSError, KeyError):
        return _result("unavailable", reason="control_health_failed")


def inspect_components(core_server: Any, vendor_root: Path) -> dict[str, Any]:
    # Source hash inspection is local and never fetches from GitHub at runtime.
    components = {
        "control": _control(core_server),
        "nexus": _nexus(vendor_root),
        "fed": _fed(vendor_root),
        "oracle": _oracle(vendor_root),
    }
    all_available = all(item["availability"] == "available" for item in components.values())
    return {
        "protocol": EDGE_PROTOCOL,
        "ok": all_available,
        "mode": "authenticated_read_only",
        "state": "complete" if all_available else "partial",
        "components": components,
        "source_pins": pins(),
        "network_federation": "not_deployed",
        "world_persistence": "not_provided",
        "semantic_authority": "none",
    }


def query_oracle(vendor_root: Path, subject: str) -> dict[str, Any]:
    if not isinstance(subject, str) or not 1 <= len(subject.strip()) <= 256:
        raise EdgeError("exact ORACLE subject must contain 1..256 characters")
    if any(ord(c) < 32 or ord(c) == 127 for c in subject):
        raise EdgeError("control characters forbidden")
    if not (vendor_root / "oracle" / "manifest.json").is_file():
        raise EdgeError("ORACLE pinned source is unavailable")
    data = OracleAdapter(vendor_root / "oracle").query_evidence(subject)
    if len(_json(data)) > MAX_OUTPUT:
        raise EdgeError("ORACLE response exceeds gateway byte limit")
    return {"protocol": EDGE_PROTOCOL, "ok": True,
            "kind": "oracle_exact_subject", "result": data,
            "semantic_authority": "none"}


def _internal_config(config: EdgeConfig) -> RemoteGatewayConfig:
    return RemoteGatewayConfig(
        bind="127.0.0.1", port=config.control_port,
        allowed_hosts=frozenset({"127.0.0.1"}),
        principals=(
            RemotePrincipal(
                principal_id="render-readonly",
                token_sha256=config.token_sha256,
                caller_kind="human",
                caller_id="edge-readonly",
                allowed_operations=frozenset({"control.health", "control.capabilities"}),
                record_access=RemoteRecordAccess(
                    max_privacy_class="PUBLIC",
                    file_ids=frozenset(), collection_ids=frozenset(),
                    run_ids=frozenset(), model_state_ids=frozenset(),
                    replay_ids=frozenset(),
                ),
            ),
        ),
        tls_enabled=False, tls_cert_file=None, tls_key_file=None,
        allow_non_loopback=False,
    )


class EdgeServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = MAX_THREADS

    def __init__(self, config: EdgeConfig, core_server: Any, *,
                 address: tuple[str, int] | None = None):
        super().__init__(address or ("0.0.0.0", config.port), EdgeHandler)
        self.config = config
        self.core_server = core_server
        self._slots = threading.BoundedSemaphore(MAX_THREADS)
        self._quota_lock = threading.Lock()
        self._quotas: dict[str, tuple[float, int]] = {}
        self._inspections = threading.BoundedSemaphore(2)

    def process_request(self, request, client_address) -> None:
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    def admit(self, principal_id: str) -> bool:
        """Quota only authenticated CONTROL principals, never proxy socket IPs.

        No forwarded client-IP header is trusted for identity or rate limits.
        Anonymous requests cannot exhaust a real operator's minute budget.
        """
        with self._quota_lock:
            now = time.monotonic()
            self._quotas = {key: val for key, val in self._quotas.items()
                            if now - val[0] < 60}
            if principal_id not in self._quotas and len(self._quotas) >= 2048:
                return False
            start, count = self._quotas.get(principal_id, (now, 0))
            if count >= MAX_RATE_PER_MINUTE:
                return False
            self._quotas[principal_id] = (start, count + 1)
            return True


class EdgeHandler(BaseHTTPRequestHandler):
    server: EdgeServer
    server_version = "QSOLReadOnlyEdge/1"
    sys_version = ""

    def log_message(self, fmt: str, *args: Any) -> None:
        # Never log request paths/headers/body or bearer credentials.
        return

    def _send(self, status: int, data: bytes, content_type: str) -> None:
        if len(data) > MAX_OUTPUT:
            data = _json({"protocol": EDGE_PROTOCOL, "ok": False,
                          "error": "response_limit"})
            status, content_type = 503, "application/json; charset=utf-8"
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'self'; style-src 'self'; "
                         "connect-src 'self'; base-uri 'none'; form-action 'none'; "
                         "frame-ancestors 'none'; object-src 'none'")
        self.send_header("Strict-Transport-Security", "max-age=31536000")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _reply(self, status: int, result: dict[str, Any]) -> None:
        self._send(status, _json(result), "application/json; charset=utf-8")

    def _error(self, status: int, code: str) -> None:
        self._reply(status, {"protocol": EDGE_PROTOCOL, "ok": False,
                             "error": code, "authority": "none"})

    def _policy(self) -> bool:
        host = self.headers.get_all("Host", [])
        if (len(host) != 1 or not isinstance(host[0], str)
                or host[0] != self.server.config.public_host):
            self._error(HTTPStatus.BAD_REQUEST, "host_rejected")
            return False
        if self.server.config.require_forwarded_https:
            proto = self.headers.get_all("X-Forwarded-Proto", [])
            if len(proto) != 1 or proto[0] != "https":
                self._error(HTTPStatus.FORBIDDEN, "https_edge_required")
                return False
        origin = self.headers.get_all("Origin", [])
        if len(origin) > 1 or (origin and origin[0] !=
                                "https://" + self.server.config.public_host):
            self._error(HTTPStatus.FORBIDDEN, "origin_rejected")
            return False
        return True

    def _principal(self):
        values = self.headers.get_all("Authorization", [])
        if len(values) != 1:
            return None
        return self.server.core_server.authenticate(values[0])

    def _body(self, maximum: int) -> bytes | None:
        if self.headers.get_all("Transfer-Encoding") or self.headers.get_all("Content-Encoding"):
            self._error(HTTPStatus.BAD_REQUEST, "unsupported_framing")
            return None
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
            self._error(HTTPStatus.BAD_REQUEST, "length_required")
            return None
        length = int(lengths[0])
        if length > maximum:
            self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "body_too_large")
            return None
        content_type = self.headers.get_all("Content-Type", [])
        if len(content_type) != 1 or content_type[0] != "application/json":
            self._error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "json_required")
            return None
        try:
            raw = self.rfile.read(length)
        except (TimeoutError, OSError):
            self._error(HTTPStatus.REQUEST_TIMEOUT, "read_timeout")
            return None
        if len(raw) != length:
            self._error(HTTPStatus.BAD_REQUEST, "truncated_body")
            return None
        return raw

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._error(HTTPStatus.METHOD_NOT_ALLOWED, "cors_disabled")

    def do_GET(self) -> None:  # noqa: N802
        # Render's own health probes may use an internal HTTP hop without
        # Forwarded-Proto. This exact fixed response contains no private state.
        if self.path == "/healthz":
            if self.headers.get_all("Host", []) != [self.server.config.public_host]:
                self._error(HTTPStatus.BAD_REQUEST, "host_rejected")
                return
            self._reply(HTTPStatus.OK, {"protocol": EDGE_PROTOCOL,
                                      "ok": True, "readiness": "edge_only",
                                      "authority": "none"})
            return
        if not self._policy():
            return
        paths = {
            "/": ("operator.html", "text/html; charset=utf-8"),
            "/operator.css": ("operator.css", "text/css; charset=utf-8"),
            "/operator.js": ("operator.js", "text/javascript; charset=utf-8"),
        }
        if self.path not in paths:
            self._error(HTTPStatus.NOT_FOUND, "not_found")
            return
        filename, typ = paths[self.path]
        try:
            data = (Path(__file__).parent / filename).read_bytes()
        except OSError:
            self._error(HTTPStatus.SERVICE_UNAVAILABLE, "asset_missing")
            return
        self._send(HTTPStatus.OK, data, typ)

    def do_POST(self) -> None:  # noqa: N802
        if not self._policy():
            return
        if self.path not in {"/v1/agent", "/v1/snapshot", "/v1/oracle/query"}:
            self._error(HTTPStatus.NOT_FOUND, "not_found")
            return
        principal = self._principal()
        if principal is None:
            self._error(HTTPStatus.UNAUTHORIZED, "auth_required")
            return
        # Authenticate with CONTROL before charging this principal's quota.
        # Sharing a Render proxy socket cannot consume other principals' quota.
        if not self.server.admit(principal.principal_id):
            self._error(HTTPStatus.TOO_MANY_REQUESTS, "rate_limited")
            return
        raw = self._body(MAX_AGENT_BODY if self.path == "/v1/agent" else MAX_BODY)
        if raw is None:
            return
        if self.path == "/v1/agent":
            # Existing CONTROL gateway performs a second independent bearer
            # check, operation allowlist, record ACL and audit.
            try:
                conn = http.client.HTTPConnection(
                    "127.0.0.1", self.server.core_server.server_port, timeout=5)
                conn.request(
                    "POST", "/v1/agent", body=raw,
                    headers={"Host": "127.0.0.1", "Content-Type": "application/json",
                             "Authorization": self.headers["Authorization"]},
                )
                response = conn.getresponse()
                payload = response.read(MAX_OUTPUT + 1)
                status = response.status
                conn.close()
                if len(payload) > MAX_OUTPUT or not 200 <= status <= 499:
                    raise EdgeError("invalid CONTROL gateway response")
                self._send(status, payload, "application/json; charset=utf-8")
            except (OSError, TimeoutError, EdgeError, http.client.HTTPException):
                self._error(HTTPStatus.SERVICE_UNAVAILABLE, "control_unavailable")
            return
        try:
            def no_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                row: dict[str, Any] = {}
                for k, v in pairs:
                    if k in row:
                        raise EdgeError("duplicate JSON key")
                    row[k] = v
                return row
            def no_constant(s: str) -> None:
                raise EdgeError("nonfinite JSON forbidden")
            request = json.loads(raw.decode("utf-8"),
                                 object_pairs_hook=no_duplicate,
                                 parse_constant=no_constant)
            if not isinstance(request, dict):
                raise EdgeError("request must be an object")
            if self.path == "/v1/snapshot":
                if request:
                    raise EdgeError("snapshot accepts only {}")
                operation = "edge.snapshot"
            else:
                if set(request) != {"subject"}:
                    raise EdgeError("query requires only subject")
                operation = "edge.oracle.query"
            self.server.core_server.audit(
                principal=principal, request_id=operation,
                operation=operation, stage="started", outcome="pending",
                requested_resources=[],
            )
        except (UnicodeDecodeError, json.JSONDecodeError, EdgeError, ValueError, OSError):
            self._error(HTTPStatus.BAD_REQUEST, "invalid_request")
            return
        if not self.server._inspections.acquire(blocking=False):
            self._error(HTTPStatus.TOO_MANY_REQUESTS, "inspection_busy")
            return
        success = False
        result: dict[str, Any] = {}
        try:
            if operation == "edge.snapshot":
                result = inspect_components(self.server.core_server,
                                            self.server.config.vendor_root)
                success = True  # partial is an honest inspection outcome
            else:
                result = query_oracle(self.server.config.vendor_root,
                                      request["subject"])
                success = True
        except (EdgeError, OracleAdapterError, ValueError, OSError):
            result = {"protocol": EDGE_PROTOCOL, "ok": False,
                      "error": "inspection_failed", "authority": "none"}
        finally:
            self.server._inspections.release()
        try:
            self.server.core_server.audit(
                principal=principal, request_id=operation,
                operation=operation, stage="completed",
                outcome="ok" if success else "error", requested_resources=[],
            )
        except (ValueError, OSError):
            self._error(HTTPStatus.SERVICE_UNAVAILABLE, "audit_unavailable")
            return
        self._reply(HTTPStatus.OK if success else HTTPStatus.SERVICE_UNAVAILABLE, result)


def run() -> None:
    config = EdgeConfig.from_environment()
    # If a pin is missing or drifted, never start an internet-facing listener.
    verify_sources()
    os.umask(0o077)
    config.control_root.mkdir(parents=True, mode=0o700, exist_ok=True)
    control = WebUIConfig(control_root=config.control_root,
                          oracle_root=config.vendor_root / "oracle",
                          nexus_command=None)
    core_server = build_server(_internal_config(config), control)
    edge_server = EdgeServer(config, core_server)
    worker = threading.Thread(target=core_server.serve_forever,
                              kwargs={"poll_interval": 0.2}, daemon=True)
    worker.start()
    try:
        edge_server.serve_forever(poll_interval=0.2)
    finally:
        edge_server.server_close()
        core_server.shutdown()
        core_server.server_close()
        worker.join(timeout=2)


def main(argv: list[str] | None = None) -> int:
    args = argparse.ArgumentParser(description="QSOL default-deny Render edge gateway")
    args.add_argument("--probe", action="store_true",
                      help="offline review of pinned backends; does not listen")
    parsed = args.parse_args(argv)
    if parsed.probe:
        verify_sources()
        class ProbeControl:
            def dispatch_local(self, request: dict[str, Any]) -> dict[str, Any]:
                from api.dispatcher import AgentAPIDispatcher
                from tempfile import TemporaryDirectory
                with TemporaryDirectory() as tmp:
                    return AgentAPIDispatcher(
                        WebUIConfig(control_root=Path(tmp))).handle(request)
        summary = inspect_components(ProbeControl(), VENDOR)
        print(json.dumps(summary, sort_keys=True, indent=2))
        return 0 if summary["ok"] else 2
    try:
        run()
        return 0
    except (EdgeError, OSError, ValueError) as exc:
        # Never emit private config values, tokens or local paths in errors.
        print(f"QSOL edge startup failed: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
