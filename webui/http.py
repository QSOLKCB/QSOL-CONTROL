from __future__ import annotations

import json
import mimetypes
import secrets
import socket
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse, urlsplit

from adapters.nexus import NexusAdapterError
from adapters.oracle import OracleAdapterError
from storage.control_store import StorageError
from storage.dna_lattice import DnaLatticeError
from storage.model_state import ModelStateError

from .common import MAX_JSON_BODY_BYTES, WebUIConfig, WebUIError, _reject_truth_fields
from .runtime import ControlWebUIRuntime

class ControlWebUIHandler(BaseHTTPRequestHandler):
    """HTTP boundary for ControlWebUIRuntime."""

    server_version = "QSOL-CONTROL-WebUI/1"

    @property
    def runtime(self) -> ControlWebUIRuntime:
        return self.server.runtime  # type: ignore[attr-defined]

    @property
    def session_token(self) -> str:
        return self.server.session_token  # type: ignore[attr-defined]

    @property
    def static_root(self) -> Path:
        return self.server.static_root  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        super().log_message(fmt, *args)

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        )

    def _json(self, status: int, value: Any) -> None:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _error(self, status: int, message: str) -> None:
        self._json(
            status,
            {
                "protocol": "qsol-control-webui-error/1",
                "status": status,
                "error": message,
                "authority": "none",
            },
        )

    def _read_json(self) -> dict[str, Any]:
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("application/json"):
            raise WebUIError("state-changing requests require application/json")
        length_header = self.headers.get("Content-Length")
        if length_header is None:
            raise WebUIError("Content-Length is required")
        try:
            length = int(length_header)
        except ValueError as exc:
            raise WebUIError("Content-Length must be an integer") from exc
        if length < 0 or length > MAX_JSON_BODY_BYTES:
            raise WebUIError(f"request body exceeds {MAX_JSON_BODY_BYTES} bytes")
        raw = self.rfile.read(length)
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise WebUIError("request body must be valid UTF-8 JSON") from exc
        if not isinstance(value, dict):
            raise WebUIError("request body must contain a JSON object")
        _reject_truth_fields(value)
        return value

    def _require_session_token(self) -> None:
        supplied = self.headers.get("X-QSOL-Control-Token")
        if not supplied or not secrets.compare_digest(supplied, self.session_token):
            raise WebUIError("missing or invalid local WebUI session token")

    def _require_local_host(self) -> None:
        host = self.headers.get("Host")
        if not host:
            raise WebUIError("Host header is required")
        try:
            parsed = urlsplit("//" + host)
            hostname = (parsed.hostname or "").casefold()
        except ValueError as exc:
            raise WebUIError("Host header is invalid") from exc
        if hostname not in {"127.0.0.1", "::1", "localhost"}:
            raise WebUIError("WebUI rejects non-loopback Host headers")

    def _require_same_origin_mutation(self) -> None:
        origin = self.headers.get("Origin")
        if origin is None:
            return
        host = self.headers.get("Host") or ""
        try:
            parsed = urlsplit(origin)
            host_parsed = urlsplit("//" + host)
        except ValueError as exc:
            raise WebUIError("Origin or Host header is invalid") from exc
        if parsed.scheme != "http":
            raise WebUIError("state-changing Origin must match the local HTTP WebUI")
        origin_host = (parsed.hostname or "").casefold()
        request_host = (host_parsed.hostname or "").casefold()
        if origin_host not in {"127.0.0.1", "::1", "localhost"}:
            raise WebUIError("state-changing request Origin must be loopback")
        server_port = int(self.server.server_address[1])
        origin_port = parsed.port if parsed.port is not None else 80
        request_port = host_parsed.port if host_parsed.port is not None else server_port
        if origin_host != request_host or origin_port != request_port:
            raise WebUIError("state-changing request Origin must match WebUI Host and port")

    def _serve_static(self, relative: str) -> None:
        name = "index.html" if relative in {"", "/"} else unquote(relative.lstrip("/"))
        if "/" in name or "\\" in name or name in {"", ".", ".."}:
            self._error(HTTPStatus.NOT_FOUND, "static resource not found")
            return
        path = self.static_root / name
        if not path.is_file() or path.is_symlink():
            self._error(HTTPStatus.NOT_FOUND, "static resource not found")
            return
        data = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix == ".js":
            content_type = "text/javascript"
        self.send_response(HTTPStatus.OK)
        self._security_headers()
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        try:
            self._require_local_host()
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query, keep_blank_values=False)
            if path == "/api/session":
                payload = self.runtime.session_contract()
                payload["session_token"] = self.session_token
                self._json(HTTPStatus.OK, payload)
                return
            if path.startswith("/api/"):
                self._require_session_token()
            if path == "/api/health":
                self._json(HTTPStatus.OK, self.runtime.health())
                return
            if path == "/api/oracle/timelock":
                self._json(HTTPStatus.OK, self.runtime.oracle_timelock())
                return
            if path == "/api/collections":
                self._json(HTTPStatus.OK, {"collections": self.runtime.list_collections()})
                return
            if path.startswith("/api/collections/"):
                collection_id = path.removeprefix("/api/collections/")
                self._json(HTTPStatus.OK, self.runtime.collection_detail(collection_id))
                return
            if path == "/api/search":
                collection_id = _single_query(query, "collection_id")
                text = _single_query(query, "q")
                limit = int(_single_query(query, "limit", default="20"))
                self._json(
                    HTTPStatus.OK,
                    self.runtime.search_collection(collection_id, text, limit=limit),
                )
                return
            if path == "/api/runs":
                self._json(HTTPStatus.OK, {"runs": self.runtime.list_runs()})
                return
            if path.startswith("/api/runs/"):
                run_id = path.removeprefix("/api/runs/")
                self._json(HTTPStatus.OK, self.runtime.run_detail(run_id))
                return
            if path == "/api/model-states":
                run_id = _single_query(query, "run_id", default=None)
                self._json(
                    HTTPStatus.OK,
                    {"states": self.runtime.list_model_states(run_id=run_id)},
                )
                return
            if path == "/api/model-states/compare":
                left = _single_query(query, "left")
                right = _single_query(query, "right")
                self._json(HTTPStatus.OK, self.runtime.compare_model_states(left, right))
                return
            if path.startswith("/api/model-states/"):
                state_id = path.removeprefix("/api/model-states/")
                self._json(HTTPStatus.OK, self.runtime.model_state(state_id))
                return
            if path == "/api/lattice":
                run_id = _single_query(query, "run_id", default=None)
                self._json(HTTPStatus.OK, self.runtime.lattice_view(run_id=run_id))
                return
            if path == "/api/replay-compare":
                left = _single_query(query, "left_run_id")
                right = _single_query(query, "right_run_id")
                self._json(HTTPStatus.OK, self.runtime.compare_runs(left, right))
                return
            if path.startswith("/api/"):
                self._error(HTTPStatus.NOT_FOUND, "API route not found")
                return
            self._serve_static(path)
        except (WebUIError, StorageError, OracleAdapterError, NexusAdapterError,
                ModelStateError, DnaLatticeError, OSError, ValueError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))

    def do_POST(self) -> None:  # noqa: N802
        try:
            self._require_local_host()
            self._require_same_origin_mutation()
            self._require_session_token()
            parsed = urlparse(self.path)
            path = parsed.path
            request = self._read_json()
            if path == "/api/files":
                self._json(HTTPStatus.CREATED, self.runtime.upload_file(request))
                return
            if path == "/api/collections":
                self._json(HTTPStatus.CREATED, self.runtime.create_collection(request))
                return
            if path.startswith("/api/collections/") and path.endswith("/members"):
                collection_id = path[len("/api/collections/") : -len("/members")].rstrip("/")
                self._json(
                    HTTPStatus.OK,
                    self.runtime.update_collection(collection_id, request),
                )
                return
            if path == "/api/ask":
                self._json(HTTPStatus.OK, self.runtime.ask(request))
                return
            if path == "/api/dna/inspect":
                self._json(HTTPStatus.OK, self.runtime.dna_inspect(request))
                return
            if path == "/api/dna/export":
                self._json(HTTPStatus.OK, self.runtime.dna_export(request))
                return
            self._error(HTTPStatus.NOT_FOUND, "API route not found")
        except (WebUIError, StorageError, OracleAdapterError, NexusAdapterError,
                ModelStateError, DnaLatticeError, OSError, ValueError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))


def _single_query(
    query: dict[str, list[str]], name: str, *, default: str | None = ...
) -> str | None:
    values = query.get(name)
    if not values:
        if default is ...:
            raise WebUIError(f"missing query parameter: {name}")
        return default
    if len(values) != 1:
        raise WebUIError(f"query parameter {name} must appear exactly once")
    return values[0]


class ControlWebUIServer(ThreadingHTTPServer):
    """Threaded local server carrying immutable configuration/runtime state."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, config: WebUIConfig):
        if config.bind not in {"127.0.0.1", "::1", "localhost"}:
            raise WebUIError(
                "Phase 5 WebUI binds to loopback only; remote deployment is not implemented"
            )
        self.config = config
        self.runtime = ControlWebUIRuntime(config)
        self.session_token = secrets.token_urlsafe(32)
        self.static_root = Path(__file__).resolve().parent / "static"
        self.address_family = socket.AF_INET6 if config.bind == "::1" else socket.AF_INET
        if not self.static_root.is_dir():
            raise WebUIError("WebUI static asset directory is missing")
        super().__init__((config.bind, config.port), ControlWebUIHandler)


def serve(config: WebUIConfig) -> None:
    server = ControlWebUIServer(config)
    actual_port = int(server.server_address[1])
    print(
        f"QSOL-CONTROL WebUI listening on http://{config.bind}:{actual_port} "
        "(loopback-only)"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
