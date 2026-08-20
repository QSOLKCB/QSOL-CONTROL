from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import re
import ssl
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from api.common import MAX_REQUEST_BYTES, OPERATIONS, REQUEST_ID_RE
from api.dispatcher import AgentAPIDispatcher
from webui.common import WebUIConfig

REMOTE_GATEWAY_PROTOCOL = "qsol-control-remote-gateway/1"
REMOTE_REQUEST_PROTOCOL = "qsol-control-remote-request/1"
MAX_CONFIG_BYTES = 1024 * 1024
MAX_PRINCIPALS = 1000
MAX_ALLOWED_HOSTS = 100
MIN_BEARER_TOKEN_CHARS = 32
MAX_BEARER_TOKEN_CHARS = 4096
SHA256_REF_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
BEARER_RE = re.compile(r"^Bearer[ \t]+([^ \t\r\n]+)$", re.IGNORECASE)


class RemoteGatewayError(ValueError):
    """Raised when the optional remote transport violates its security contract."""


@dataclass(frozen=True)
class RemotePrincipal:
    principal_id: str
    token_sha256: str
    caller_kind: str
    caller_id: str
    allowed_operations: frozenset[str]


@dataclass(frozen=True)
class RemoteGatewayConfig:
    bind: str
    port: int
    allowed_hosts: frozenset[str]
    principals: tuple[RemotePrincipal, ...]
    tls_enabled: bool
    tls_cert_file: Path | None
    tls_key_file: Path | None
    allow_non_loopback: bool


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise RemoteGatewayError(f"duplicate JSON member: {key}")
        out[key] = value
    return out


def _reject_constant(value: str) -> None:
    raise RemoteGatewayError(f"non-finite JSON number rejected: {value}")


def _load_json(path: Path, *, maximum: int = MAX_CONFIG_BYTES) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RemoteGatewayError("remote gateway config must be a regular non-symlink file")
    if path.stat().st_size > maximum:
        raise RemoteGatewayError("remote gateway config exceeds byte limit")
    if os.name == "posix" and path.stat().st_mode & 0o077:
        raise RemoteGatewayError("remote gateway config must not be group/world accessible")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except RemoteGatewayError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise RemoteGatewayError("invalid remote gateway config JSON") from exc
    if not isinstance(value, dict):
        raise RemoteGatewayError("remote gateway config root must be an object")
    return value


def _is_loopback(value: str) -> bool:
    if value.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _canonical_host(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 253:
        raise RemoteGatewayError("allowed host must be bounded non-empty text")
    lowered = value.casefold().rstrip(".")
    if any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789.-:" for ch in lowered):
        raise RemoteGatewayError("allowed host contains unsupported characters")
    return lowered


def _host_without_port(value: str) -> str:
    candidate = value.strip().casefold().rstrip(".")
    if candidate.startswith("["):
        end = candidate.find("]")
        return candidate[1:end] if end > 0 else candidate
    if candidate.count(":") == 1:
        host, port = candidate.rsplit(":", 1)
        if port.isdigit():
            return host
    return candidate


def _validate_principal(row: Any, seen_ids: set[str], seen_tokens: set[str]) -> RemotePrincipal:
    if not isinstance(row, dict):
        raise RemoteGatewayError("principal must be an object")
    required = {"principal_id", "token_sha256", "caller_kind", "caller_id", "allowed_operations"}
    if set(row) != required:
        raise RemoteGatewayError("principal field set mismatch")
    principal_id = row["principal_id"]
    caller_id = row["caller_id"]
    if not isinstance(principal_id, str) or not REQUEST_ID_RE.fullmatch(principal_id):
        raise RemoteGatewayError("principal_id is invalid")
    if principal_id in seen_ids:
        raise RemoteGatewayError("duplicate principal_id")
    seen_ids.add(principal_id)
    token_sha256 = row["token_sha256"]
    if not isinstance(token_sha256, str) or SHA256_REF_RE.fullmatch(token_sha256) is None:
        raise RemoteGatewayError("principal token_sha256 must be a sha256: reference")
    if token_sha256 in seen_tokens:
        raise RemoteGatewayError("token digest must not be shared by principals")
    seen_tokens.add(token_sha256)
    caller_kind = row["caller_kind"]
    if caller_kind not in {"human", "ai"}:
        raise RemoteGatewayError("principal caller_kind must be human or ai")
    if not isinstance(caller_id, str) or not caller_id or len(caller_id) > 256:
        raise RemoteGatewayError("principal caller_id is invalid")
    operations = row["allowed_operations"]
    if not isinstance(operations, list) or not operations:
        raise RemoteGatewayError("principal allowed_operations must be non-empty")
    if len(operations) != len(set(operations)):
        raise RemoteGatewayError("principal allowed_operations must not contain duplicates")
    if any(operation not in OPERATIONS for operation in operations):
        raise RemoteGatewayError("principal contains unknown operation")
    return RemotePrincipal(
        principal_id=principal_id,
        token_sha256=token_sha256,
        caller_kind=caller_kind,
        caller_id=caller_id,
        allowed_operations=frozenset(operations),
    )


def _validate_tls_files(cert: Path, key: Path) -> tuple[Path, Path]:
    try:
        cert_resolved = cert.resolve(strict=True)
        key_resolved = key.resolve(strict=True)
    except OSError as exc:
        raise RemoteGatewayError("TLS certificate/key file is unavailable") from exc
    if not cert_resolved.is_file() or not key_resolved.is_file():
        raise RemoteGatewayError("TLS certificate/key must resolve to regular files")
    if os.name == "posix" and key_resolved.stat().st_mode & 0o077:
        raise RemoteGatewayError("TLS private key must not be group/world accessible")
    return cert_resolved, key_resolved


def load_gateway_config(path: str | Path) -> RemoteGatewayConfig:
    value = _load_json(Path(path))
    required = {
        "protocol",
        "bind",
        "port",
        "allow_non_loopback",
        "allowed_hosts",
        "tls",
        "principals",
    }
    if set(value) != required or value.get("protocol") != REMOTE_GATEWAY_PROTOCOL:
        raise RemoteGatewayError("remote gateway config protocol/field set mismatch")
    bind = value["bind"]
    if not isinstance(bind, str) or not bind or len(bind) > 253:
        raise RemoteGatewayError("bind must be bounded non-empty text")
    port = value["port"]
    if type(port) is not int or not 1 <= port <= 65535:
        raise RemoteGatewayError("port must be 1..65535")
    allow_non_loopback = value["allow_non_loopback"]
    if type(allow_non_loopback) is not bool:
        raise RemoteGatewayError("allow_non_loopback must be boolean")
    hosts = value["allowed_hosts"]
    if not isinstance(hosts, list) or not hosts or len(hosts) > MAX_ALLOWED_HOSTS:
        raise RemoteGatewayError("allowed_hosts must be a bounded non-empty array")
    allowed_hosts = frozenset(_canonical_host(host) for host in hosts)
    if len(allowed_hosts) != len(hosts):
        raise RemoteGatewayError("allowed_hosts must not contain duplicates")
    tls = value["tls"]
    if not isinstance(tls, dict) or set(tls) != {"enabled", "cert_file", "key_file", "minimum_version"}:
        raise RemoteGatewayError("tls config field set mismatch")
    if type(tls["enabled"]) is not bool or tls["minimum_version"] != "TLSv1.2":
        raise RemoteGatewayError("tls config must explicitly use TLSv1.2 minimum")
    cert = Path(tls["cert_file"]) if isinstance(tls["cert_file"], str) and tls["cert_file"] else None
    key = Path(tls["key_file"]) if isinstance(tls["key_file"], str) and tls["key_file"] else None
    if tls["enabled"] and (cert is None or key is None):
        raise RemoteGatewayError("TLS enabled requires cert_file and key_file")
    if not tls["enabled"] and (cert is not None or key is not None):
        raise RemoteGatewayError("TLS disabled must not carry cert/key paths")
    if tls["enabled"]:
        assert cert is not None and key is not None
        cert, key = _validate_tls_files(cert, key)
    if not _is_loopback(bind):
        if not allow_non_loopback:
            raise RemoteGatewayError("non-loopback bind requires allow_non_loopback=true")
        if not tls["enabled"]:
            raise RemoteGatewayError("non-loopback bind requires TLS")
    principals = value["principals"]
    if not isinstance(principals, list) or not principals or len(principals) > MAX_PRINCIPALS:
        raise RemoteGatewayError("principals must be a bounded non-empty array")
    seen_ids: set[str] = set()
    seen_tokens: set[str] = set()
    parsed = tuple(_validate_principal(row, seen_ids, seen_tokens) for row in principals)
    return RemoteGatewayConfig(
        bind=bind,
        port=port,
        allowed_hosts=allowed_hosts,
        principals=parsed,
        tls_enabled=tls["enabled"],
        tls_cert_file=cert,
        tls_key_file=key,
        allow_non_loopback=allow_non_loopback,
    )


def token_digest(token: str) -> str:
    return "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


class RemoteGatewayServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        gateway_config: RemoteGatewayConfig,
        dispatcher: AgentAPIDispatcher,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.gateway_config = gateway_config
        self.dispatcher = dispatcher
        self.dispatch_lock = threading.Lock()

    def authenticate(self, authorization: str | None) -> RemotePrincipal | None:
        if not isinstance(authorization, str):
            return None
        match = BEARER_RE.fullmatch(authorization.strip())
        if match is None:
            return None
        token = match.group(1)
        if not MIN_BEARER_TOKEN_CHARS <= len(token) <= MAX_BEARER_TOKEN_CHARS:
            return None
        presented = token_digest(token)
        for principal in self.gateway_config.principals:
            if hmac.compare_digest(principal.token_sha256, presented):
                return principal
        return None


class RemoteGatewayHandler(BaseHTTPRequestHandler):
    server: RemoteGatewayServer
    server_version = "QSOLControlRemote/1"
    sys_version = ""

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def _headers(self, status: int, *, content_length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(content_length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        self.end_headers()

    def _emit(self, status: int, value: dict[str, Any]) -> None:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self._headers(status, content_length=len(raw))
        self.wfile.write(raw)

    def _reject(self, status: int, code: str, message: str) -> None:
        self._emit(status, {"protocol": REMOTE_GATEWAY_PROTOCOL, "ok": False, "error": {"code": code, "message": message}, "authority": "none"})

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._reject(HTTPStatus.METHOD_NOT_ALLOWED, "METHOD_NOT_ALLOWED", "CORS/preflight is not enabled")

    def do_GET(self) -> None:  # noqa: N802
        self._reject(HTTPStatus.METHOD_NOT_ALLOWED, "METHOD_NOT_ALLOWED", "remote gateway accepts POST /v1/agent only")

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/agent":
            self._reject(HTTPStatus.NOT_FOUND, "NOT_FOUND", "unknown remote gateway path")
            return
        host = self.headers.get("Host")
        if not isinstance(host, str) or _host_without_port(host) not in self.server.gateway_config.allowed_hosts:
            self._reject(HTTPStatus.BAD_REQUEST, "HOST_REJECTED", "Host is not on the configured allowlist")
            return
        principal = self.server.authenticate(self.headers.get("Authorization"))
        if principal is None:
            self._reject(HTTPStatus.UNAUTHORIZED, "AUTH_REQUIRED", "valid bearer credential required")
            return
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().casefold()
        if content_type != "application/json":
            self._reject(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "CONTENT_TYPE", "application/json required")
            return
        length_text = self.headers.get("Content-Length")
        try:
            length = int(length_text) if length_text is not None else -1
        except ValueError:
            length = -1
        if length < 0 or length > MAX_REQUEST_BYTES:
            self._reject(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "RESOURCE_LIMIT", "request body exceeds remote gateway limit")
            return
        raw = self.rfile.read(length)
        try:
            request = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_reject_constant)
        except (UnicodeDecodeError, json.JSONDecodeError, RemoteGatewayError, RecursionError):
            self._reject(HTTPStatus.BAD_REQUEST, "INVALID_JSON", "invalid UTF-8 JSON request")
            return
        if not isinstance(request, dict) or set(request) != {"protocol", "request_id", "operation", "params"}:
            self._reject(HTTPStatus.BAD_REQUEST, "INVALID_REQUEST", "remote request field set mismatch")
            return
        if request.get("protocol") != REMOTE_REQUEST_PROTOCOL:
            self._reject(HTTPStatus.BAD_REQUEST, "UNSUPPORTED_PROTOCOL", "remote request protocol mismatch")
            return
        request_id = request.get("request_id")
        operation = request.get("operation")
        params = request.get("params")
        if not isinstance(request_id, str) or REQUEST_ID_RE.fullmatch(request_id) is None:
            self._reject(HTTPStatus.BAD_REQUEST, "INVALID_REQUEST", "request_id is invalid")
            return
        if operation not in principal.allowed_operations:
            self._reject(HTTPStatus.FORBIDDEN, "OPERATION_FORBIDDEN", "principal is not permitted to call this operation")
            return
        if not isinstance(params, dict):
            self._reject(HTTPStatus.BAD_REQUEST, "INVALID_REQUEST", "params must be an object")
            return
        local_request = {
            "protocol": "qsol-control-agent-request/1",
            "request_id": request_id,
            "caller": {"kind": principal.caller_kind, "id": principal.caller_id},
            "operation": operation,
            "params": params,
        }
        with self.server.dispatch_lock:
            response = self.server.dispatcher.handle(local_request)
        self._emit(HTTPStatus.OK, response)


def build_server(gateway: RemoteGatewayConfig, control: WebUIConfig) -> RemoteGatewayServer:
    dispatcher = AgentAPIDispatcher(control)
    server = RemoteGatewayServer(
        (gateway.bind, gateway.port),
        RemoteGatewayHandler,
        gateway_config=gateway,
        dispatcher=dispatcher,
    )
    if gateway.tls_enabled:
        assert gateway.tls_cert_file is not None and gateway.tls_key_file is not None
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(str(gateway.tls_cert_file), str(gateway.tls_key_file))
        server.socket = context.wrap_socket(server.socket, server_side=True)
    return server
