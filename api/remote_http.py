from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import re
import socket
import ssl
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from api.common import MAX_REQUEST_BYTES, OPERATIONS, REQUEST_ID_RE
from api.dispatcher import AgentAPIDispatcher
from webui.common import WebUIConfig

REMOTE_GATEWAY_PROTOCOL = "qsol-control-remote-gateway/1"
REMOTE_REQUEST_PROTOCOL = "qsol-control-remote-request/1"
REMOTE_AUDIT_PROTOCOL = "qsol-control-remote-audit/1"
MAX_CONFIG_BYTES = 1024 * 1024
MAX_PRINCIPALS = 1000
MAX_ALLOWED_HOSTS = 100
MAX_ACL_IDS = 10_000
MAX_AUDIT_RECORDS = 100_000
MIN_BEARER_TOKEN_CHARS = 32
MAX_BEARER_TOKEN_CHARS = 4096
MAX_CONNECTIONS = 64
SOCKET_TIMEOUT_SECONDS = 10.0
QUOTA_WINDOW_SECONDS = 60.0
SHA256_REF_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
BEARER_RE = re.compile(r"^Bearer[ \t]+([^ \t\r\n]+)$", re.IGNORECASE)
PRIVACY_RANK = {"PUBLIC": 0, "INTERNAL": 1, "RESTRICTED": 2}


class RemoteGatewayError(ValueError):
    """Raised when the optional remote transport violates its security contract."""


def _empty_acl() -> "RemoteRecordAccess":
    return RemoteRecordAccess(
        max_privacy_class="INTERNAL",
        file_ids=frozenset(),
        collection_ids=frozenset(),
        run_ids=frozenset(),
        model_state_ids=frozenset(),
        replay_ids=frozenset(),
    )


@dataclass(frozen=True)
class RemoteRecordAccess:
    max_privacy_class: str
    file_ids: frozenset[str]
    collection_ids: frozenset[str]
    run_ids: frozenset[str]
    model_state_ids: frozenset[str]
    replay_ids: frozenset[str]


@dataclass(frozen=True)
class RemotePrincipal:
    principal_id: str
    token_sha256: str
    caller_kind: str
    caller_id: str
    allowed_operations: frozenset[str]
    record_access: RemoteRecordAccess = field(default_factory=_empty_acl)


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


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_ref(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def _sha_set(value: Any, field_name: str) -> frozenset[str]:
    if not isinstance(value, list) or len(value) > MAX_ACL_IDS:
        raise RemoteGatewayError(f"{field_name} must be a bounded array")
    if len(value) != len(set(value)):
        raise RemoteGatewayError(f"{field_name} must not contain duplicates")
    if any(not isinstance(item, str) or SHA256_REF_RE.fullmatch(item) is None for item in value):
        raise RemoteGatewayError(f"{field_name} must contain sha256: references")
    return frozenset(value)


def _validate_record_access(value: Any) -> RemoteRecordAccess:
    if not isinstance(value, dict):
        raise RemoteGatewayError("principal record_access must be an object")
    required = {
        "max_privacy_class",
        "file_ids",
        "collection_ids",
        "run_ids",
        "model_state_ids",
        "replay_ids",
    }
    if set(value) != required:
        raise RemoteGatewayError("principal record_access field set mismatch")
    max_privacy = value["max_privacy_class"]
    if max_privacy not in PRIVACY_RANK:
        raise RemoteGatewayError("record_access max_privacy_class is invalid")
    return RemoteRecordAccess(
        max_privacy_class=max_privacy,
        file_ids=_sha_set(value["file_ids"], "record_access.file_ids"),
        collection_ids=_sha_set(value["collection_ids"], "record_access.collection_ids"),
        run_ids=_sha_set(value["run_ids"], "record_access.run_ids"),
        model_state_ids=_sha_set(value["model_state_ids"], "record_access.model_state_ids"),
        replay_ids=_sha_set(value["replay_ids"], "record_access.replay_ids"),
    )


def _validate_principal(
    row: Any, seen_ids: set[str], seen_tokens: set[str]
) -> RemotePrincipal:
    if not isinstance(row, dict):
        raise RemoteGatewayError("principal must be an object")
    required = {
        "principal_id",
        "token_sha256",
        "caller_kind",
        "caller_id",
        "allowed_operations",
        "record_access",
    }
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
        record_access=_validate_record_access(row["record_access"]),
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


def _validate_gateway_object(value: RemoteGatewayConfig) -> RemoteGatewayConfig:
    """Revalidate programmatic configs at the public server-factory boundary."""

    if not isinstance(value, RemoteGatewayConfig):
        raise RemoteGatewayError("gateway config must be RemoteGatewayConfig")
    if not isinstance(value.bind, str) or not value.bind or len(value.bind) > 253:
        raise RemoteGatewayError("bind must be bounded non-empty text")
    if type(value.port) is not int or not 1 <= value.port <= 65535:
        raise RemoteGatewayError("port must be 1..65535")
    if type(value.allow_non_loopback) is not bool:
        raise RemoteGatewayError("allow_non_loopback must be boolean")
    if not value.allowed_hosts or len(value.allowed_hosts) > MAX_ALLOWED_HOSTS:
        raise RemoteGatewayError("allowed_hosts must be bounded and non-empty")
    if any(_canonical_host(host) != host for host in value.allowed_hosts):
        raise RemoteGatewayError("allowed_hosts must already be canonical")
    if not value.principals or len(value.principals) > MAX_PRINCIPALS:
        raise RemoteGatewayError("principals must be bounded and non-empty")
    seen_ids: set[str] = set()
    seen_tokens: set[str] = set()
    for principal in value.principals:
        if not isinstance(principal, RemotePrincipal):
            raise RemoteGatewayError("programmatic principal type is invalid")
        row = {
            "principal_id": principal.principal_id,
            "token_sha256": principal.token_sha256,
            "caller_kind": principal.caller_kind,
            "caller_id": principal.caller_id,
            "allowed_operations": sorted(principal.allowed_operations),
            "record_access": {
                "max_privacy_class": principal.record_access.max_privacy_class,
                "file_ids": sorted(principal.record_access.file_ids),
                "collection_ids": sorted(principal.record_access.collection_ids),
                "run_ids": sorted(principal.record_access.run_ids),
                "model_state_ids": sorted(principal.record_access.model_state_ids),
                "replay_ids": sorted(principal.record_access.replay_ids),
            },
        }
        _validate_principal(row, seen_ids, seen_tokens)
    cert = value.tls_cert_file
    key = value.tls_key_file
    if value.tls_enabled:
        if cert is None or key is None:
            raise RemoteGatewayError("TLS enabled requires cert_file and key_file")
        _validate_tls_files(cert, key)
    elif cert is not None or key is not None:
        raise RemoteGatewayError("TLS disabled must not carry cert/key paths")
    if not _is_loopback(value.bind):
        if not value.allow_non_loopback:
            raise RemoteGatewayError("non-loopback bind requires allow_non_loopback=true")
        if not value.tls_enabled:
            raise RemoteGatewayError("non-loopback bind requires TLS")
    return value


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
    if not isinstance(tls, dict) or set(tls) != {
        "enabled",
        "cert_file",
        "key_file",
        "minimum_version",
    }:
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
    principals = value["principals"]
    if not isinstance(principals, list) or not principals or len(principals) > MAX_PRINCIPALS:
        raise RemoteGatewayError("principals must be a bounded non-empty array")
    seen_ids: set[str] = set()
    seen_tokens: set[str] = set()
    parsed = tuple(_validate_principal(row, seen_ids, seen_tokens) for row in principals)
    config = RemoteGatewayConfig(
        bind=bind,
        port=port,
        allowed_hosts=allowed_hosts,
        principals=parsed,
        tls_enabled=tls["enabled"],
        tls_cert_file=cert,
        tls_key_file=key,
        allow_non_loopback=allow_non_loopback,
    )
    return _validate_gateway_object(config)


def token_digest(token: str) -> str:
    return "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        path.parent.chmod(0o700)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temp = Path(handle.name)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temp, path)
        if os.name == "posix":
            path.chmod(0o600)
    finally:
        if temp.exists():
            temp.unlink()


def _extract_requested_refs(operation: str, params: dict[str, Any]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    mapping = {
        "file_id": "file",
        "collection_id": "collection",
        "run_id": "run",
        "left_run_id": "run",
        "right_run_id": "run",
        "state_id": "model_state",
        "replay_id": "replay",
    }
    for key, kind in mapping.items():
        value = params.get(key)
        if isinstance(value, str) and SHA256_REF_RE.fullmatch(value):
            refs.append({"kind": kind, "id": value})
    for value in params.get("file_ids", []) if isinstance(params.get("file_ids"), list) else []:
        if isinstance(value, str) and SHA256_REF_RE.fullmatch(value):
            refs.append({"kind": "file", "id": value})
    unique = {(row["kind"], row["id"]): row for row in refs}
    return [unique[key] for key in sorted(unique)]


def _find_sha_key(value: Any, key_name: str) -> set[str]:
    found: set[str] = set()
    stack = [value]
    visited = 0
    while stack:
        current = stack.pop()
        visited += 1
        if visited > 100_000:
            break
        if isinstance(current, dict):
            for key, child in current.items():
                if key == key_name and isinstance(child, str) and SHA256_REF_RE.fullmatch(child):
                    found.add(child)
                elif isinstance(child, (dict, list)):
                    stack.append(child)
        elif isinstance(current, list):
            stack.extend(current)
    return found


def _extract_created_refs(operation: str, response: dict[str, Any]) -> list[dict[str, str]]:
    if response.get("ok") is not True:
        return []
    result = response.get("result")
    key_map: dict[str, tuple[str, ...]] = {
        "control.file.put": ("file_id",),
        "control.collection.create": ("collection_id",),
        "control.ask": ("run_id",),
        "control.replay.execute": ("replay_id", "replay_run_id"),
    }
    refs: list[dict[str, str]] = []
    kind_for = {
        "file_id": "file",
        "collection_id": "collection",
        "run_id": "run",
        "replay_run_id": "run",
        "replay_id": "replay",
    }
    for key in key_map.get(operation, ()): 
        for identity in _find_sha_key(result, key):
            refs.append({"kind": kind_for[key], "id": identity})
    unique = {(row["kind"], row["id"]): row for row in refs}
    return [unique[key] for key in sorted(unique)]


class RemoteGatewayServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = MAX_CONNECTIONS

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        gateway_config: RemoteGatewayConfig,
        control_config: WebUIConfig,
    ) -> None:
        _validate_gateway_object(gateway_config)
        super().__init__(server_address, handler_class)
        self.gateway_config = gateway_config
        self.control_config = control_config
        self.dispatcher = AgentAPIDispatcher(control_config)
        self.dispatch_lock = threading.Lock()
        self._quota_window_started = time.monotonic()
        self._connection_slots = threading.BoundedSemaphore(MAX_CONNECTIONS)
        self.audit_dir = Path(control_config.control_root) / "records" / "remote-audit"
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            self.audit_dir.chmod(0o700)
        self._owned_resources: dict[str, set[tuple[str, str]]] = {
            principal.principal_id: set() for principal in gateway_config.principals
        }
        self._load_audit_ownership()

    def get_request(self):
        request, client_address = super().get_request()
        request.settimeout(SOCKET_TIMEOUT_SECONDS)
        return request, client_address

    def process_request(self, request, client_address) -> None:
        if not self._connection_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._connection_slots.release()
            raise

    def process_request_thread(self, request, client_address) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._connection_slots.release()

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

    def dispatch_local(self, request: dict[str, Any]) -> dict[str, Any]:
        """Dispatch with renewable window quotas appropriate for a persistent server."""

        with self.dispatch_lock:
            now = time.monotonic()
            if now - self._quota_window_started >= QUOTA_WINDOW_SECONDS:
                self.dispatcher = AgentAPIDispatcher(self.control_config)
                self._quota_window_started = now
            return self.dispatcher.handle(request)

    def _load_audit_ownership(self) -> None:
        paths = sorted(self.audit_dir.glob("*.json"))
        if len(paths) > MAX_AUDIT_RECORDS:
            raise RemoteGatewayError("remote audit record count exceeds limit")
        for path in paths:
            try:
                raw = path.read_bytes()
                record = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_reject_constant)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, RemoteGatewayError) as exc:
                raise RemoteGatewayError("remote audit history is malformed") from exc
            if not isinstance(record, dict) or record.get("protocol") != REMOTE_AUDIT_PROTOCOL:
                raise RemoteGatewayError("remote audit history protocol mismatch")
            audit_id = record.get("audit_id")
            payload = {key: value for key, value in record.items() if key != "audit_id"}
            if not isinstance(audit_id, str) or audit_id != _sha256_ref(_canonical_json_bytes(payload)):
                raise RemoteGatewayError("remote audit history identity mismatch")
            principal_id = record.get("principal_id")
            if principal_id not in self._owned_resources:
                continue
            if record.get("stage") == "completed" and record.get("outcome") == "ok":
                for ref in record.get("created_resources", []):
                    if (
                        isinstance(ref, dict)
                        and ref.get("kind") in {"file", "collection", "run", "model_state", "replay"}
                        and isinstance(ref.get("id"), str)
                        and SHA256_REF_RE.fullmatch(ref["id"])
                    ):
                        self._owned_resources[principal_id].add((ref["kind"], ref["id"]))

    def audit(
        self,
        *,
        principal: RemotePrincipal,
        request_id: str,
        operation: str,
        stage: str,
        outcome: str,
        requested_resources: list[dict[str, str]],
        created_resources: list[dict[str, str]] | None = None,
        error_code: str | None = None,
    ) -> str:
        if stage not in {"started", "completed"} or outcome not in {"pending", "ok", "error", "denied"}:
            raise RemoteGatewayError("invalid remote audit stage/outcome")
        payload = {
            "protocol": REMOTE_AUDIT_PROTOCOL,
            "occurred_at": _utc_now(),
            "principal_id": principal.principal_id,
            "caller_kind": principal.caller_kind,
            "caller_id": principal.caller_id,
            "request_id": request_id,
            "operation": operation,
            "stage": stage,
            "outcome": outcome,
            "requested_resources": requested_resources,
            "created_resources": created_resources or [],
            "error_code": error_code,
            "credential_material_captured": False,
            "authority": "security-audit-only",
        }
        audit_id = _sha256_ref(_canonical_json_bytes(payload))
        record = {"audit_id": audit_id, **payload}
        _atomic_write(
            self.audit_dir / f"{audit_id.split(':', 1)[1]}.json",
            _canonical_json_bytes(record),
        )
        if stage == "completed" and outcome == "ok":
            for ref in created_resources or []:
                self._owned_resources[principal.principal_id].add((ref["kind"], ref["id"]))
        return audit_id

    def _owned_or_configured(self, principal: RemotePrincipal, kind: str, identity: str) -> bool:
        configured = {
            "file": principal.record_access.file_ids,
            "collection": principal.record_access.collection_ids,
            "run": principal.record_access.run_ids,
            "model_state": principal.record_access.model_state_ids,
            "replay": principal.record_access.replay_ids,
        }[kind]
        return identity in configured or (kind, identity) in self._owned_resources[principal.principal_id]

    def _privacy_allowed(self, principal: RemotePrincipal, privacy_class: str) -> bool:
        return PRIVACY_RANK[privacy_class] <= PRIVACY_RANK[principal.record_access.max_privacy_class]

    def _authorize_file(self, principal: RemotePrincipal, file_id: str) -> None:
        record = self.dispatcher.runtime.control.store.get_file_record(file_id)
        privacy = record["privacy_class"]
        if not self._privacy_allowed(principal, privacy):
            raise RemoteGatewayError("principal privacy ceiling rejects File")
        if privacy != "PUBLIC" and not self._owned_or_configured(principal, "file", file_id):
            raise RemoteGatewayError("principal is not authorized for File")

    def _authorize_collection(self, principal: RemotePrincipal, collection_id: str) -> None:
        record = self.dispatcher.runtime.control.store.get_collection(collection_id)
        privacy = record["privacy_class"]
        if not self._privacy_allowed(principal, privacy):
            raise RemoteGatewayError("principal privacy ceiling rejects Collection")
        if privacy != "PUBLIC" and not self._owned_or_configured(principal, "collection", collection_id):
            raise RemoteGatewayError("principal is not authorized for Collection")

    def _run_privacy(self, run_id: str) -> str:
        run = self.dispatcher.runtime.control.interactions.get_run(run_id)
        rank = PRIVACY_RANK["INTERNAL"]
        for file_id in run.get("file_ids", []):
            record = self.dispatcher.runtime.control.store.get_file_record(file_id)
            rank = max(rank, PRIVACY_RANK[record["privacy_class"]])
        collection_ref = run.get("collection_ref")
        if isinstance(collection_ref, dict):
            collection = self.dispatcher.runtime.control.store.get_collection(
                collection_ref["collection_id"]
            )
            rank = max(rank, PRIVACY_RANK[collection["privacy_class"]])
        return next(name for name, value in PRIVACY_RANK.items() if value == rank)

    def _authorize_run(self, principal: RemotePrincipal, run_id: str) -> None:
        if not self._owned_or_configured(principal, "run", run_id):
            raise RemoteGatewayError("principal is not authorized for run")
        privacy = self._run_privacy(run_id)
        if not self._privacy_allowed(principal, privacy):
            raise RemoteGatewayError("principal privacy ceiling rejects run")

    def _authorize_model_state(self, principal: RemotePrincipal, state_id: str) -> None:
        if self._owned_or_configured(principal, "model_state", state_id):
            return
        state = self.dispatcher.runtime.control.model_state(state_id)
        run_id = state.get("system", {}).get("control_run_id") if isinstance(state, dict) else None
        if isinstance(run_id, str) and SHA256_REF_RE.fullmatch(run_id):
            self._authorize_run(principal, run_id)
            return
        raise RemoteGatewayError("principal is not authorized for model state")

    def _authorize_replay(self, principal: RemotePrincipal, replay_id: str) -> None:
        if not self._owned_or_configured(principal, "replay", replay_id):
            raise RemoteGatewayError("principal is not authorized for replay")

    def authorize(self, principal: RemotePrincipal, operation: str, params: dict[str, Any]) -> None:
        if operation in {"control.health", "control.capabilities"}:
            return
        if operation == "control.file.put":
            privacy = params.get("privacy_class", "INTERNAL")
            if privacy not in PRIVACY_RANK or not self._privacy_allowed(principal, privacy):
                raise RemoteGatewayError("principal cannot create File at requested privacy class")
            return
        if operation == "control.collection.create":
            privacy = params.get("privacy_class", "INTERNAL")
            if privacy not in PRIVACY_RANK or not self._privacy_allowed(principal, privacy):
                raise RemoteGatewayError("principal cannot create Collection at requested privacy class")
            for file_id in params.get("file_ids", []):
                self._authorize_file(principal, file_id)
            return
        if operation == "control.ask":
            if not self._privacy_allowed(principal, "INTERNAL"):
                raise RemoteGatewayError("remote questions are INTERNAL unless bound state is stricter")
            council_privacy = params.get("privacy_class")
            if council_privacy is not None and (
                council_privacy not in PRIVACY_RANK
                or not self._privacy_allowed(principal, council_privacy)
            ):
                raise RemoteGatewayError("principal cannot ask at requested privacy class")
            for file_id in params.get("file_ids", []):
                self._authorize_file(principal, file_id)
            collection_id = params.get("collection_id")
            if collection_id is not None:
                self._authorize_collection(principal, collection_id)
            return
        if operation == "control.file.get":
            self._authorize_file(principal, params.get("file_id"))
            return
        if operation in {"control.collection.snapshot", "control.collection.search"}:
            self._authorize_collection(principal, params.get("collection_id"))
            return
        if operation == "control.run.compare":
            self._authorize_run(principal, params.get("left_run_id"))
            self._authorize_run(principal, params.get("right_run_id"))
            return
        if operation in {
            "control.run.get",
            "control.evidence.get",
            "control.council.get",
            "control.replay.classify",
            "control.replay.execute",
            "control.research.timeline",
        }:
            self._authorize_run(principal, params.get("run_id"))
            return
        if operation == "control.replay.get":
            self._authorize_replay(principal, params.get("replay_id"))
            return
        if operation == "control.models.get":
            run_id = params.get("run_id")
            state_id = params.get("state_id")
            if run_id is not None:
                self._authorize_run(principal, run_id)
                return
            if state_id is not None:
                self._authorize_model_state(principal, state_id)
                return
            raise RemoteGatewayError("remote model-state listing requires run_id or state_id")
        if operation in {"control.memory.get", "control.memory.trace"}:
            run_id = params.get("run_id")
            if run_id is None:
                raise RemoteGatewayError("remote memory access requires an authorized run_id")
            self._authorize_run(principal, run_id)
            return
        raise RemoteGatewayError("remote operation has no record-authorization policy")


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
        raw = _canonical_json_bytes(value)
        self._headers(status, content_length=len(raw))
        self.wfile.write(raw)

    def _reject(self, status: int, code: str, message: str) -> None:
        self._emit(
            status,
            {
                "protocol": REMOTE_GATEWAY_PROTOCOL,
                "ok": False,
                "error": {"code": code, "message": message},
                "authority": "none",
            },
        )

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._reject(
            HTTPStatus.METHOD_NOT_ALLOWED,
            "METHOD_NOT_ALLOWED",
            "CORS/preflight is not enabled",
        )

    def do_GET(self) -> None:  # noqa: N802
        self._reject(
            HTTPStatus.METHOD_NOT_ALLOWED,
            "METHOD_NOT_ALLOWED",
            "remote gateway accepts POST /v1/agent only",
        )

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
            self._reject(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "RESOURCE_LIMIT",
                "request body exceeds remote gateway limit",
            )
            return
        try:
            raw = self.rfile.read(length)
        except (socket.timeout, TimeoutError, OSError):
            self._reject(HTTPStatus.REQUEST_TIMEOUT, "REQUEST_TIMEOUT", "request body timed out")
            return
        try:
            request = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_pairs,
                parse_constant=_reject_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, RemoteGatewayError, RecursionError):
            self._reject(HTTPStatus.BAD_REQUEST, "INVALID_JSON", "invalid UTF-8 JSON request")
            return
        if not isinstance(request, dict) or set(request) != {
            "protocol",
            "request_id",
            "operation",
            "params",
        }:
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
        if not isinstance(operation, str) or operation not in OPERATIONS:
            self._reject(HTTPStatus.BAD_REQUEST, "UNKNOWN_OPERATION", "unsupported operation")
            return
        if not isinstance(params, dict):
            self._reject(HTTPStatus.BAD_REQUEST, "INVALID_REQUEST", "params must be an object")
            return
        requested_refs = _extract_requested_refs(operation, params)
        try:
            self.server.audit(
                principal=principal,
                request_id=request_id,
                operation=operation,
                stage="started",
                outcome="pending",
                requested_resources=requested_refs,
            )
        except (RemoteGatewayError, OSError):
            self._reject(HTTPStatus.INTERNAL_SERVER_ERROR, "AUDIT_UNAVAILABLE", "remote audit trail is unavailable")
            return
        if operation not in principal.allowed_operations:
            self.server.audit(
                principal=principal,
                request_id=request_id,
                operation=operation,
                stage="completed",
                outcome="denied",
                requested_resources=requested_refs,
                error_code="OPERATION_FORBIDDEN",
            )
            self._reject(HTTPStatus.FORBIDDEN, "OPERATION_FORBIDDEN", "principal is not permitted to call this operation")
            return
        try:
            self.server.authorize(principal, operation, params)
        except (RemoteGatewayError, OSError, ValueError):
            self.server.audit(
                principal=principal,
                request_id=request_id,
                operation=operation,
                stage="completed",
                outcome="denied",
                requested_resources=requested_refs,
                error_code="RECORD_ACCESS_DENIED",
            )
            self._reject(HTTPStatus.FORBIDDEN, "RECORD_ACCESS_DENIED", "principal is not authorized for requested record scope")
            return
        local_request = {
            "protocol": "qsol-control-agent-request/1",
            "request_id": request_id,
            "caller": {"kind": principal.caller_kind, "id": principal.caller_id},
            "operation": operation,
            "params": params,
        }
        response = self.server.dispatch_local(local_request)
        created_refs = _extract_created_refs(operation, response)
        try:
            self.server.audit(
                principal=principal,
                request_id=request_id,
                operation=operation,
                stage="completed",
                outcome="ok" if response.get("ok") is True else "error",
                requested_resources=requested_refs,
                created_resources=created_refs,
                error_code=(
                    None
                    if response.get("ok") is True
                    else response.get("error", {}).get("code")
                ),
            )
        except (RemoteGatewayError, OSError):
            self._reject(HTTPStatus.INTERNAL_SERVER_ERROR, "AUDIT_COMPLETION_FAILED", "operation completed but audit completion failed")
            return
        self._emit(HTTPStatus.OK, response)


def build_server(gateway: RemoteGatewayConfig, control: WebUIConfig) -> RemoteGatewayServer:
    gateway = _validate_gateway_object(gateway)
    server = RemoteGatewayServer(
        (gateway.bind, gateway.port),
        RemoteGatewayHandler,
        gateway_config=gateway,
        control_config=control,
    )
    if gateway.tls_enabled:
        assert gateway.tls_cert_file is not None and gateway.tls_key_file is not None
        cert, key = _validate_tls_files(gateway.tls_cert_file, gateway.tls_key_file)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(str(cert), str(key))
        server.socket = context.wrap_socket(server.socket, server_side=True)
    return server
