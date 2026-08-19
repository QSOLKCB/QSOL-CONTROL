#!/usr/bin/env python3
"""Persistent AI model-state registry for QSOL-CONTROL.

Model-state records preserve externally inspectable reproducibility metadata only.
They do not preserve a model mind, consciousness, hidden activations, or hidden
chain-of-thought. Local artifact paths may be inspected to compute hashes, but
paths and artifact bytes are never copied into canonical model-state records.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any, Iterable

from storage.control_store import StorageError, canonical_json_bytes, sha256_ref
from storage.interaction_store import InteractionStore

MODEL_STATE_PROTOCOL = "qsol-control-model-state/1"
STATE_VERIFICATION_PROTOCOL = "qsol-control-model-state-verification/1"
STATE_COMPARISON_PROTOCOL = "qsol-control-model-state-comparison/1"
RUN_COMPARISON_PROTOCOL = "qsol-control-model-state-run-comparison/1"
ARCHAEOLOGY_PROTOCOL = "qsol-control-model-state-archaeology/1"
LOCAL_ARTIFACT_MANIFEST_PROTOCOL = "qsol-control-local-artifact-manifest/1"
EPISTEMIC_BOUNDARY = "MODEL_STATE != MODEL_MIND"
AUTHORITY = "reproducibility-metadata-only"

SHA256_REF_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
PROVENANCE_KINDS = {
    "observed",
    "provider_reported",
    "locally_verified",
    "inferred",
    "unknown",
}
PRIVACY_CLASSES = {"PUBLIC", "INTERNAL", "RESTRICTED"}
PRIVACY_RANK = {"PUBLIC": 0, "INTERNAL": 1, "RESTRICTED": 2}
ARTIFACT_ROLES = ("model", "weights", "tokenizer")
MAX_RECORD_BYTES = 4 * 1024 * 1024
MAX_REGISTRY_STATES = 100_000
MAX_EXPORT_STATES = 10_000
MAX_SCAN_NODES = 1_000_000

FORBIDDEN_REASONING_KEYS = {
    "chain_of_thought",
    "hidden_chain_of_thought",
    "hidden_reasoning",
    "private_reasoning",
    "internal_reasoning",
    "reasoning_trace",
    "scratchpad",
    "private_scratchpad",
    "model_mind",
    "mind_state",
    "internal_activations",
}
FORBIDDEN_SECRET_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "auth_token",
    "bearer_token",
    "client_secret",
    "private_key",
    "password",
    "passwd",
    "credential",
    "credentials",
    "authorization",
    "cookie",
    "session_cookie",
}
FORBIDDEN_SECRET_MARKERS = (
    "ghp_",
    "github_pat_",
    "Bearer ",
    "-----BEGIN PRIVATE KEY-----",
    "AKIA",
)

PROVENANCE_FIELDS = (
    "captured_at",
    "model.provider",
    "model.runtime",
    "model.runtime_version",
    "model.model_id",
    "model.revision",
    "model.model_hash",
    "model.weight_hash",
    "model.tokenizer_identity",
    "model.tokenizer_hash",
    "model.quantization",
    "model.artifacts.model",
    "model.artifacts.weights",
    "model.artifacts.tokenizer",
    "execution.council_seat",
    "execution.mode",
    "execution.stochastic",
    "execution.seed",
    "execution.context_limit",
    "execution.sampling",
    "execution.tool_permissions",
    "execution.tool_permission_envelope",
    "system.control_run_id",
    "system.control_manifest_identity",
    "system.nexus_identity",
    "system.oracle_refs",
    "system.substrate_identity",
    "system.ark_identity",
    "system.int_identity",
    "system.collection_snapshot_id",
    "system.evidence_snapshot_ref",
    "system.hardware_runtime_metadata",
)

MODEL_KEYS = {
    "provider",
    "runtime",
    "runtime_version",
    "model_id",
    "revision",
    "model_hash",
    "weight_hash",
    "tokenizer_identity",
    "tokenizer_hash",
    "quantization",
    "artifacts",
}
EXECUTION_KEYS = {
    "council_seat",
    "mode",
    "stochastic",
    "seed",
    "context_limit",
    "sampling",
    "tool_permissions",
    "tool_permission_envelope",
}
SYSTEM_KEYS = {
    "control_run_id",
    "control_manifest_identity",
    "nexus_identity",
    "oracle_refs",
    "substrate_identity",
    "ark_identity",
    "int_identity",
    "collection_snapshot_id",
    "evidence_snapshot_ref",
    "hardware_runtime_metadata",
}
RECORD_KEYS = {
    "protocol",
    "state_id",
    "captured_at",
    "model",
    "execution",
    "system",
    "field_provenance",
    "privacy_class",
    "epistemic_boundary",
    "hidden_chain_of_thought_captured",
    "model_mind_captured",
    "authority",
}

TOOL_FILESYSTEM_CLASSES = {
    "none",
    "read-only",
    "workspace-write",
    "unrestricted",
    "unknown",
}
TOOL_NETWORK_CLASSES = {
    "none",
    "loopback",
    "restricted",
    "unrestricted",
    "unknown",
}


class ModelStateError(StorageError):
    """Raised when model-state capture, verification, comparison, or export fails."""


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _reject_forbidden_material(value: Any, label: str) -> None:
    """Reject hidden-reasoning and credential-bearing keys/values recursively."""

    stack = [value]
    visited = 0
    while stack:
        current = stack.pop()
        visited += 1
        if visited > MAX_SCAN_NODES:
            raise ModelStateError(f"{label} exceeds security-scan node limit")
        if isinstance(current, dict):
            for key, item in current.items():
                if not isinstance(key, str):
                    raise ModelStateError(f"{label} contains a non-string object key")
                normalized = _normalize_key(key)
                if normalized in FORBIDDEN_REASONING_KEYS:
                    raise ModelStateError(
                        f"{label} contains forbidden hidden-reasoning field {key!r}"
                    )
                if normalized in FORBIDDEN_SECRET_KEYS:
                    raise ModelStateError(
                        f"{label} contains forbidden credential field {key!r}"
                    )
                stack.append(item)
        elif isinstance(current, list):
            stack.extend(current)
        elif isinstance(current, str):
            for marker in FORBIDDEN_SECRET_MARKERS:
                if marker in current:
                    raise ModelStateError(f"{label} contains forbidden credential material")


def _validate_timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ModelStateError("captured_at must be a non-empty ISO-8601 timestamp")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    from datetime import datetime

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ModelStateError("captured_at must be valid ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ModelStateError("captured_at must include an explicit UTC offset")
    return value


def _sha256_ref_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _validate_sha_ref(value: Any, label: str, *, allow_none: bool = True) -> str | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or SHA256_REF_RE.fullmatch(value) is None:
        raise ModelStateError(f"{label} must be a sha256: reference")
    return value


def _optional_string(value: Any, label: str, *, maximum: int = 4096) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ModelStateError(f"{label} must be null or bounded non-empty text")
    return value


def _required_string(value: Any, label: str, *, maximum: int = 4096) -> str:
    output = _optional_string(value, label, maximum=maximum)
    if output is None:
        raise ModelStateError(f"{label} is required")
    return output


def _unique_strings(values: Any, label: str) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list) or any(not isinstance(item, str) or not item for item in values):
        raise ModelStateError(f"{label} must be an array of non-empty strings")
    if len(values) != len(set(values)):
        raise ModelStateError(f"{label} must not contain duplicates")
    return sorted(values, key=lambda item: item.encode("utf-8"))


def _atomic_write(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temp_path = Path(handle.name)
        if os.name != "nt":
            os.fchmod(handle.fileno(), mode)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temp_path, path)
        if os.name != "nt":
            os.chmod(path, mode, follow_symlinks=False)
    finally:
        temp_path.unlink(missing_ok=True)


def _read_canonical_json(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ModelStateError("model-state record must not be a symbolic link")
    try:
        encoded = path.read_bytes()
        value = json.loads(encoded.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ModelStateError("model-state record cannot be decoded") from exc
    if not isinstance(value, dict):
        raise ModelStateError("model-state record must contain a JSON object")
    try:
        canonical = canonical_json_bytes(value)
    except (TypeError, ValueError, RecursionError) as exc:
        raise ModelStateError("model-state record is not canonical JSON") from exc
    if canonical != encoded:
        raise ModelStateError("model-state record bytes are not canonical JSON")
    return value


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(8 * 1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return "sha256:" + digest.hexdigest(), size


def hash_local_artifact(path_value: str | Path) -> dict[str, Any]:
    """Hash a local file or directory without persisting its path or bytes.

    Directory identity is the SHA-256 of a canonical manifest of relative file
    names, exact file-byte hashes, and sizes. It is therefore explicitly a
    directory-manifest identity rather than a claim that a directory has one raw
    byte stream.
    """

    path = Path(path_value).expanduser()
    if path.is_symlink():
        raise ModelStateError("local model artifact must not be a symbolic link")
    if not path.exists():
        raise ModelStateError("local model artifact does not exist")
    if path.is_file():
        digest, size = _hash_file(path)
        return {
            "kind": "file-bytes",
            "sha256": digest,
            "size_bytes": size,
            "file_count": 1,
            "manifest_protocol": None,
        }
    if not path.is_dir():
        raise ModelStateError("local model artifact must be a regular file or directory")

    rows: list[dict[str, Any]] = []
    total = 0
    for candidate in sorted(path.rglob("*"), key=lambda item: item.relative_to(path).as_posix().encode("utf-8")):
        if candidate.is_symlink():
            raise ModelStateError("local artifact directory must not contain symbolic links")
        if candidate.is_dir():
            continue
        if not candidate.is_file():
            raise ModelStateError("local artifact directory contains a non-regular entry")
        digest, size = _hash_file(candidate)
        total += size
        rows.append(
            {
                "path": candidate.relative_to(path).as_posix(),
                "sha256": digest,
                "size_bytes": size,
            }
        )
    manifest = {"protocol": LOCAL_ARTIFACT_MANIFEST_PROTOCOL, "files": rows}
    return {
        "kind": "directory-manifest",
        "sha256": _sha256_ref_bytes(canonical_json_bytes(manifest)),
        "size_bytes": total,
        "file_count": len(rows),
        "manifest_protocol": LOCAL_ARTIFACT_MANIFEST_PROTOCOL,
    }


def _validate_artifact_descriptor(value: Any, label: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {
        "kind",
        "sha256",
        "size_bytes",
        "file_count",
        "manifest_protocol",
    }:
        raise ModelStateError(f"{label} artifact descriptor is invalid")
    if value.get("kind") not in {"file-bytes", "directory-manifest"}:
        raise ModelStateError(f"{label} artifact kind is invalid")
    _validate_sha_ref(value.get("sha256"), f"{label} artifact sha256", allow_none=False)
    size = value.get("size_bytes")
    count = value.get("file_count")
    if type(size) is not int or size < 0 or type(count) is not int or count < 0:
        raise ModelStateError(f"{label} artifact size/count is invalid")
    if value["kind"] == "file-bytes":
        if count != 1 or value.get("manifest_protocol") is not None:
            raise ModelStateError(f"{label} file artifact descriptor is inconsistent")
    elif value.get("manifest_protocol") != LOCAL_ARTIFACT_MANIFEST_PROTOCOL:
        raise ModelStateError(f"{label} directory artifact manifest protocol is invalid")
    return copy.deepcopy(value)


def _tool_envelope(value: Any, permissions: list[str]) -> dict[str, Any]:
    if value is None:
        return {
            "filesystem": "unknown",
            "network": "unknown",
            "tools": list(permissions),
            "mcp_plugins": [],
            "external_execution": None,
        }
    if not isinstance(value, dict) or set(value) != {
        "filesystem",
        "network",
        "tools",
        "mcp_plugins",
        "external_execution",
    }:
        raise ModelStateError("tool_permission_envelope must use the canonical fields")
    filesystem = value.get("filesystem")
    network = value.get("network")
    if filesystem not in TOOL_FILESYSTEM_CLASSES or network not in TOOL_NETWORK_CLASSES:
        raise ModelStateError("tool permission filesystem/network class is invalid")
    tools = _unique_strings(value.get("tools"), "tool_permission_envelope.tools")
    plugins = _unique_strings(value.get("mcp_plugins"), "tool_permission_envelope.mcp_plugins")
    external = value.get("external_execution")
    if external is not None and type(external) is not bool:
        raise ModelStateError("tool_permission_envelope.external_execution must be boolean or null")
    if permissions and tools != permissions:
        raise ModelStateError("tool_permissions and tool_permission_envelope.tools disagree")
    return {
        "filesystem": filesystem,
        "network": network,
        "tools": tools,
        "mcp_plugins": plugins,
        "external_execution": external,
    }


def _field_category(path: str) -> str:
    if path.startswith("model."):
        return "model"
    if path.startswith("execution."):
        return "execution"
    if path.startswith("system."):
        return "system"
    return "capture"


def _get_path(record: dict[str, Any], path: str) -> Any:
    current: Any = record
    for segment in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(segment)
    return copy.deepcopy(current)


class ModelStateRegistry:
    """Immutable content-addressed registry of reproducibility metadata."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.interactions = InteractionStore(self.root)
        self.records = self.root / "records" / "model-states"
        self.records.mkdir(parents=True, exist_ok=True)

    def _path(self, state_id: str) -> Path:
        _validate_sha_ref(state_id, "state_id", allow_none=False)
        return self.records / f"{state_id.removeprefix('sha256:')}.json"

    @staticmethod
    def _identity(payload: dict[str, Any]) -> str:
        return sha256_ref(canonical_json_bytes(payload))

    def capture(
        self,
        *,
        captured_at: str,
        model: dict[str, Any],
        execution: dict[str, Any],
        system: dict[str, Any],
        field_provenance: dict[str, str] | None = None,
        privacy_class: str = "INTERNAL",
        local_artifacts: dict[str, str | Path] | None = None,
        link_run_event: bool = True,
    ) -> dict[str, Any]:
        """Capture one canonical model-state record and optionally link it to its run."""

        timestamp = _validate_timestamp(captured_at)
        if privacy_class not in PRIVACY_CLASSES:
            raise ModelStateError("privacy_class must be PUBLIC, INTERNAL, or RESTRICTED")
        if not isinstance(model, dict) or not isinstance(execution, dict) or not isinstance(system, dict):
            raise ModelStateError("model, execution, and system must be objects")
        _reject_forbidden_material(model, "model descriptor")
        _reject_forbidden_material(execution, "execution descriptor")
        _reject_forbidden_material(system, "system descriptor")

        run_id = _validate_sha_ref(system.get("control_run_id"), "system.control_run_id", allow_none=False)
        assert run_id is not None
        run = self.interactions.get_run(run_id)

        computed_artifacts: dict[str, dict[str, Any] | None] = {role: None for role in ARTIFACT_ROLES}
        for role, path in (local_artifacts or {}).items():
            if role not in ARTIFACT_ROLES:
                raise ModelStateError(f"unknown local artifact role: {role}")
            computed_artifacts[role] = hash_local_artifact(path)

        source_artifacts = model.get("artifacts", {})
        if source_artifacts is None:
            source_artifacts = {}
        if not isinstance(source_artifacts, dict) or not set(source_artifacts) <= set(ARTIFACT_ROLES):
            raise ModelStateError("model.artifacts contains unsupported roles")
        for role in ARTIFACT_ROLES:
            declared = _validate_artifact_descriptor(source_artifacts.get(role), f"model.artifacts.{role}")
            computed = computed_artifacts[role]
            if computed is not None and declared is not None and computed != declared:
                raise ModelStateError(f"locally verified {role} artifact differs from declared descriptor")
            if computed is None:
                computed_artifacts[role] = declared

        model_hash = _validate_sha_ref(model.get("model_hash"), "model.model_hash")
        weight_hash = _validate_sha_ref(model.get("weight_hash"), "model.weight_hash")
        tokenizer_hash = _validate_sha_ref(model.get("tokenizer_hash"), "model.tokenizer_hash")
        role_hash_fields = {
            "model": ("model_hash", model_hash),
            "weights": ("weight_hash", weight_hash),
            "tokenizer": ("tokenizer_hash", tokenizer_hash),
        }
        resolved_hashes = {
            "model_hash": model_hash,
            "weight_hash": weight_hash,
            "tokenizer_hash": tokenizer_hash,
        }
        for role, (field, declared_hash) in role_hash_fields.items():
            descriptor = computed_artifacts[role]
            if descriptor is None:
                continue
            verified_hash = descriptor["sha256"]
            if declared_hash is not None and declared_hash != verified_hash:
                raise ModelStateError(f"model.{field} differs from locally verified {role} artifact")
            resolved_hashes[field] = verified_hash

        canonical_model = {
            "provider": _required_string(model.get("provider"), "model.provider", maximum=256),
            "runtime": _required_string(model.get("runtime"), "model.runtime", maximum=256),
            "runtime_version": _optional_string(model.get("runtime_version"), "model.runtime_version", maximum=256),
            "model_id": _required_string(model.get("model_id"), "model.model_id", maximum=1024),
            "revision": _optional_string(model.get("revision"), "model.revision", maximum=1024),
            "model_hash": resolved_hashes["model_hash"],
            "weight_hash": resolved_hashes["weight_hash"],
            "tokenizer_identity": _optional_string(model.get("tokenizer_identity"), "model.tokenizer_identity", maximum=1024),
            "tokenizer_hash": resolved_hashes["tokenizer_hash"],
            "quantization": _optional_string(model.get("quantization"), "model.quantization", maximum=256),
            "artifacts": {role: computed_artifacts[role] for role in ARTIFACT_ROLES},
        }

        permissions = _unique_strings(execution.get("tool_permissions"), "execution.tool_permissions")
        stochastic = execution.get("stochastic")
        if stochastic is not None and type(stochastic) is not bool:
            raise ModelStateError("execution.stochastic must be boolean or null")
        seed = execution.get("seed")
        if seed is not None and (type(seed) not in (int, str) or isinstance(seed, bool)):
            raise ModelStateError("execution.seed must be integer, string, or null")
        context_limit = execution.get("context_limit")
        if context_limit is not None and (type(context_limit) is not int or context_limit < 1):
            raise ModelStateError("execution.context_limit must be a positive integer or null")
        sampling = execution.get("sampling", {})
        if not isinstance(sampling, dict):
            raise ModelStateError("execution.sampling must be an object")
        _reject_forbidden_material(sampling, "execution.sampling")
        canonical_execution = {
            "council_seat": _optional_string(execution.get("council_seat"), "execution.council_seat", maximum=256),
            "mode": _optional_string(execution.get("mode"), "execution.mode", maximum=256),
            "stochastic": stochastic,
            "seed": seed,
            "context_limit": context_limit,
            "sampling": copy.deepcopy(sampling),
            "tool_permissions": permissions,
            "tool_permission_envelope": _tool_envelope(execution.get("tool_permission_envelope"), permissions),
        }

        oracle_refs = system.get("oracle_refs")
        if oracle_refs is None:
            oracle_refs = list(run.get("oracle_refs", []))
        canonical_oracle_refs = _unique_strings(oracle_refs, "system.oracle_refs")
        collection_snapshot_id = system.get("collection_snapshot_id")
        run_collection = run.get("collection_ref")
        if collection_snapshot_id is None and isinstance(run_collection, dict):
            collection_snapshot_id = run_collection.get("snapshot_id")
        if collection_snapshot_id is not None:
            _validate_sha_ref(collection_snapshot_id, "system.collection_snapshot_id", allow_none=False)
            if isinstance(run_collection, dict) and collection_snapshot_id != run_collection.get("snapshot_id"):
                raise ModelStateError("system.collection_snapshot_id differs from containing CONTROL run")

        hardware = system.get("hardware_runtime_metadata", {})
        if not isinstance(hardware, dict):
            raise ModelStateError("system.hardware_runtime_metadata must be an object")
        _reject_forbidden_material(hardware, "system.hardware_runtime_metadata")
        canonical_system = {
            "control_run_id": run_id,
            "control_manifest_identity": _optional_string(system.get("control_manifest_identity"), "system.control_manifest_identity", maximum=1024),
            "nexus_identity": _optional_string(system.get("nexus_identity"), "system.nexus_identity", maximum=1024),
            "oracle_refs": canonical_oracle_refs,
            "substrate_identity": _optional_string(system.get("substrate_identity"), "system.substrate_identity", maximum=1024),
            "ark_identity": _optional_string(system.get("ark_identity"), "system.ark_identity", maximum=1024),
            "int_identity": _optional_string(system.get("int_identity"), "system.int_identity", maximum=1024),
            "collection_snapshot_id": collection_snapshot_id,
            "evidence_snapshot_ref": _optional_string(system.get("evidence_snapshot_ref"), "system.evidence_snapshot_ref", maximum=1024),
            "hardware_runtime_metadata": copy.deepcopy(hardware),
        }

        automatic_provenance: dict[str, str] = {
            "captured_at": "observed",
            "system.control_run_id": "locally_verified",
        }
        if system.get("oracle_refs") is None and canonical_oracle_refs:
            automatic_provenance["system.oracle_refs"] = "locally_verified"
        if system.get("collection_snapshot_id") is None and collection_snapshot_id is not None:
            automatic_provenance["system.collection_snapshot_id"] = "locally_verified"
        for role, (field, _) in role_hash_fields.items():
            if (local_artifacts or {}).get(role) is not None:
                automatic_provenance[f"model.artifacts.{role}"] = "locally_verified"
                automatic_provenance[f"model.{field}"] = "locally_verified"

        supplied_provenance = field_provenance or {}
        if not isinstance(supplied_provenance, dict):
            raise ModelStateError("field_provenance must be an object")
        unknown_paths = set(supplied_provenance) - set(PROVENANCE_FIELDS)
        if unknown_paths:
            raise ModelStateError(
                "field_provenance contains unknown fields: " + ", ".join(sorted(unknown_paths))
            )
        provenance: dict[str, str] = {}
        for field in PROVENANCE_FIELDS:
            kind = automatic_provenance.get(field, supplied_provenance.get(field, "unknown"))
            if kind not in PROVENANCE_KINDS:
                raise ModelStateError(f"invalid provenance kind for {field}: {kind!r}")
            provenance[field] = kind

        payload = {
            "protocol": MODEL_STATE_PROTOCOL,
            "captured_at": timestamp,
            "model": canonical_model,
            "execution": canonical_execution,
            "system": canonical_system,
            "field_provenance": provenance,
            "privacy_class": privacy_class,
            "epistemic_boundary": EPISTEMIC_BOUNDARY,
            "hidden_chain_of_thought_captured": False,
            "model_mind_captured": False,
            "authority": AUTHORITY,
        }
        state_id = self._identity(payload)
        record = {"state_id": state_id, **payload}
        self._validate_record(record, require_run=True)
        encoded = canonical_json_bytes(record)
        if len(encoded) > MAX_RECORD_BYTES:
            raise ModelStateError("model-state record exceeds canonical byte limit")
        path = self._path(state_id)
        if path.exists():
            if path.read_bytes() != encoded:
                raise ModelStateError("model-state identity collision detected")
        else:
            _atomic_write(path, encoded)

        if link_run_event:
            self._ensure_run_event(record)
        return copy.deepcopy(record)

    def _ensure_run_event(self, record: dict[str, Any]) -> dict[str, Any]:
        run_id = record["system"]["control_run_id"]
        state_id = record["state_id"]
        for event in self.interactions.list_events(run_id):
            if event.get("kind") == "model_state" and event.get("payload", {}).get("state_id") == state_id:
                return event
        return self.interactions.append_event(
            run_id,
            kind="model_state",
            payload=record,
            occurred_at=record["captured_at"],
            record_refs=[state_id],
        )

    def get_state(self, state_id: str) -> dict[str, Any]:
        path = self._path(state_id)
        if not path.is_file():
            raise ModelStateError(f"unknown state_id: {state_id}")
        record = _read_canonical_json(path)
        if record.get("state_id") != state_id:
            raise ModelStateError("model-state record/path identity mismatch")
        payload = {key: value for key, value in record.items() if key != "state_id"}
        if self._identity(payload) != state_id:
            raise ModelStateError("model-state content identity mismatch")
        self._validate_record(record, require_run=True)
        return copy.deepcopy(record)

    def _validate_record(self, record: dict[str, Any], *, require_run: bool) -> None:
        if set(record) != RECORD_KEYS:
            raise ModelStateError("model-state fields do not match qsol-control-model-state/1")
        if record.get("protocol") != MODEL_STATE_PROTOCOL:
            raise ModelStateError("model-state protocol mismatch")
        _validate_sha_ref(record.get("state_id"), "state_id", allow_none=False)
        _validate_timestamp(record.get("captured_at"))
        if record.get("privacy_class") not in PRIVACY_CLASSES:
            raise ModelStateError("model-state privacy_class is invalid")
        if record.get("epistemic_boundary") != EPISTEMIC_BOUNDARY:
            raise ModelStateError("model-state epistemic boundary is missing or altered")
        if record.get("hidden_chain_of_thought_captured") is not False:
            raise ModelStateError("model-state must never capture hidden chain-of-thought")
        if record.get("model_mind_captured") is not False:
            raise ModelStateError("model-state must never claim model-mind capture")
        if record.get("authority") != AUTHORITY:
            raise ModelStateError("model-state authority must remain reproducibility-metadata-only")

        model = record.get("model")
        if not isinstance(model, dict) or set(model) != MODEL_KEYS:
            raise ModelStateError("model-state model descriptor is invalid")
        for field in ("provider", "runtime", "model_id"):
            _required_string(model.get(field), f"model.{field}")
        for field in ("runtime_version", "revision", "tokenizer_identity", "quantization"):
            _optional_string(model.get(field), f"model.{field}")
        for field in ("model_hash", "weight_hash", "tokenizer_hash"):
            _validate_sha_ref(model.get(field), f"model.{field}")
        artifacts = model.get("artifacts")
        if not isinstance(artifacts, dict) or set(artifacts) != set(ARTIFACT_ROLES):
            raise ModelStateError("model.artifacts must contain canonical artifact roles")
        for role in ARTIFACT_ROLES:
            descriptor = _validate_artifact_descriptor(artifacts[role], f"model.artifacts.{role}")
            if descriptor is not None:
                hash_field = role_hash_fields = {
                    "model": "model_hash",
                    "weights": "weight_hash",
                    "tokenizer": "tokenizer_hash",
                }[role]
                if model.get(hash_field) != descriptor["sha256"]:
                    raise ModelStateError(f"model.{hash_field} differs from artifact descriptor")

        execution = record.get("execution")
        if not isinstance(execution, dict) or set(execution) != EXECUTION_KEYS:
            raise ModelStateError("model-state execution descriptor is invalid")
        _optional_string(execution.get("council_seat"), "execution.council_seat")
        _optional_string(execution.get("mode"), "execution.mode")
        stochastic = execution.get("stochastic")
        if stochastic is not None and type(stochastic) is not bool:
            raise ModelStateError("execution.stochastic is invalid")
        seed = execution.get("seed")
        if seed is not None and (type(seed) not in (int, str) or isinstance(seed, bool)):
            raise ModelStateError("execution.seed is invalid")
        context_limit = execution.get("context_limit")
        if context_limit is not None and (type(context_limit) is not int or context_limit < 1):
            raise ModelStateError("execution.context_limit is invalid")
        if not isinstance(execution.get("sampling"), dict):
            raise ModelStateError("execution.sampling must be an object")
        permissions = _unique_strings(execution.get("tool_permissions"), "execution.tool_permissions")
        if permissions != execution.get("tool_permissions"):
            raise ModelStateError("execution.tool_permissions are not canonically ordered")
        envelope = _tool_envelope(execution.get("tool_permission_envelope"), permissions)
        if envelope != execution.get("tool_permission_envelope"):
            raise ModelStateError("tool_permission_envelope is not canonical")

        system = record.get("system")
        if not isinstance(system, dict) or set(system) != SYSTEM_KEYS:
            raise ModelStateError("model-state system descriptor is invalid")
        run_id = _validate_sha_ref(system.get("control_run_id"), "system.control_run_id", allow_none=False)
        assert run_id is not None
        for field in (
            "control_manifest_identity",
            "nexus_identity",
            "substrate_identity",
            "ark_identity",
            "int_identity",
            "evidence_snapshot_ref",
        ):
            _optional_string(system.get(field), f"system.{field}")
        collection_snapshot_id = system.get("collection_snapshot_id")
        if collection_snapshot_id is not None:
            _validate_sha_ref(collection_snapshot_id, "system.collection_snapshot_id", allow_none=False)
        oracle_refs = _unique_strings(system.get("oracle_refs"), "system.oracle_refs")
        if oracle_refs != system.get("oracle_refs"):
            raise ModelStateError("system.oracle_refs are not canonically ordered")
        if not isinstance(system.get("hardware_runtime_metadata"), dict):
            raise ModelStateError("system.hardware_runtime_metadata must be an object")
        if require_run:
            run = self.interactions.get_run(run_id)
            run_collection = run.get("collection_ref")
            if collection_snapshot_id is not None and isinstance(run_collection, dict):
                if collection_snapshot_id != run_collection.get("snapshot_id"):
                    raise ModelStateError("model-state collection snapshot differs from containing run")

        provenance = record.get("field_provenance")
        if not isinstance(provenance, dict) or set(provenance) != set(PROVENANCE_FIELDS):
            raise ModelStateError("field_provenance must classify every canonical model-state field")
        if any(value not in PROVENANCE_KINDS for value in provenance.values()):
            raise ModelStateError("field_provenance contains an invalid provenance kind")
        if provenance.get("system.control_run_id") != "locally_verified":
            raise ModelStateError("system.control_run_id provenance must be locally_verified")
        if provenance.get("captured_at") != "observed":
            raise ModelStateError("captured_at provenance must be observed")
        for role, field in (("model", "model_hash"), ("weights", "weight_hash"), ("tokenizer", "tokenizer_hash")):
            descriptor = model["artifacts"][role]
            if descriptor is not None and provenance.get(f"model.artifacts.{role}") == "locally_verified":
                if provenance.get(f"model.{field}") != "locally_verified":
                    raise ModelStateError("locally verified artifact hash provenance is inconsistent")

        _reject_forbidden_material(record, "model-state record")
        payload = {key: value for key, value in record.items() if key != "state_id"}
        if self._identity(payload) != record.get("state_id"):
            raise ModelStateError("model-state state_id does not match canonical record content")

    def verify_state(self, state_id: str) -> dict[str, Any]:
        record = self.get_state(state_id)
        event_linked = any(
            event.get("kind") == "model_state" and event.get("payload", {}).get("state_id") == state_id
            for event in self.interactions.list_events(record["system"]["control_run_id"])
        )
        return {
            "protocol": STATE_VERIFICATION_PROTOCOL,
            "status": "valid",
            "state_id": state_id,
            "control_run_id": record["system"]["control_run_id"],
            "interaction_event_linked": event_linked,
            "privacy_class": record["privacy_class"],
            "epistemic_boundary": EPISTEMIC_BOUNDARY,
            "hidden_chain_of_thought_captured": False,
            "model_mind_captured": False,
            "authority": AUTHORITY,
        }

    def list_states(self, *, run_id: str | None = None) -> list[dict[str, Any]]:
        if run_id is not None:
            _validate_sha_ref(run_id, "run_id", allow_none=False)
            self.interactions.get_run(run_id)
        paths = sorted(self.records.glob("*.json"), key=lambda path: path.name.encode("ascii"))
        if len(paths) > MAX_REGISTRY_STATES:
            raise ModelStateError("model-state registry exceeds scan limit")
        output: list[dict[str, Any]] = []
        for path in paths:
            state_id = "sha256:" + path.stem
            record = self.get_state(state_id)
            if run_id is None or record["system"]["control_run_id"] == run_id:
                output.append(record)
        return output

    def compare_states(self, left_state_id: str, right_state_id: str) -> dict[str, Any]:
        left = self.get_state(left_state_id)
        right = self.get_state(right_state_id)
        changes: list[dict[str, Any]] = []
        for path in PROVENANCE_FIELDS:
            left_value = _get_path(left, path)
            right_value = _get_path(right, path)
            left_provenance = left["field_provenance"][path]
            right_provenance = right["field_provenance"][path]
            if left_value != right_value or left_provenance != right_provenance:
                changes.append(
                    {
                        "path": path,
                        "category": _field_category(path),
                        "left": left_value,
                        "right": right_value,
                        "left_provenance": left_provenance,
                        "right_provenance": right_provenance,
                    }
                )
        payload = {
            "protocol": STATE_COMPARISON_PROTOCOL,
            "left_state_id": left_state_id,
            "right_state_id": right_state_id,
            "left_run_id": left["system"]["control_run_id"],
            "right_run_id": right["system"]["control_run_id"],
            "changed_fields": changes,
            "changed_field_count": len(changes),
            "same_model_identity": (
                left["model"]["provider"],
                left["model"]["runtime"],
                left["model"]["model_id"],
                left["model"]["revision"],
            )
            == (
                right["model"]["provider"],
                right["model"]["runtime"],
                right["model"]["model_id"],
                right["model"]["revision"],
            ),
            "epistemic_boundary": EPISTEMIC_BOUNDARY,
            "model_mind_inference": False,
            "authority": "metadata-comparison-only",
        }
        comparison_id = self._identity(payload)
        return {"comparison_id": comparison_id, **payload}

    @staticmethod
    def _run_key(record: dict[str, Any]) -> str:
        seat = record["execution"].get("council_seat")
        if isinstance(seat, str) and seat:
            return "seat:" + seat
        return "model:" + record["model"]["provider"] + ":" + record["model"]["model_id"]

    def compare_runs(self, left_run_id: str, right_run_id: str) -> dict[str, Any]:
        left_states = self.list_states(run_id=left_run_id)
        right_states = self.list_states(run_id=right_run_id)

        def keyed(records: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
            output: dict[str, dict[str, Any]] = {}
            for record in records:
                key = self._run_key(record)
                if key in output:
                    raise ModelStateError(f"{label} run contains ambiguous model-state key {key}")
                output[key] = record
            return output

        left = keyed(left_states, "left")
        right = keyed(right_states, "right")
        aligned: list[dict[str, Any]] = []
        left_only: list[dict[str, str]] = []
        right_only: list[dict[str, str]] = []
        for key in sorted(set(left) | set(right), key=lambda item: item.encode("utf-8")):
            if key not in left:
                right_only.append({"key": key, "state_id": right[key]["state_id"]})
            elif key not in right:
                left_only.append({"key": key, "state_id": left[key]["state_id"]})
            else:
                aligned.append(
                    {
                        "key": key,
                        "comparison": self.compare_states(left[key]["state_id"], right[key]["state_id"]),
                    }
                )
        payload = {
            "protocol": RUN_COMPARISON_PROTOCOL,
            "left_run_id": left_run_id,
            "right_run_id": right_run_id,
            "aligned": aligned,
            "left_only": left_only,
            "right_only": right_only,
            "epistemic_boundary": EPISTEMIC_BOUNDARY,
            "model_mind_inference": False,
            "authority": "metadata-comparison-only",
        }
        return {"comparison_id": self._identity(payload), **payload}

    def build_archaeology_export(
        self,
        *,
        state_ids: Iterable[str] = (),
        run_ids: Iterable[str] = (),
        include_all: bool = False,
        allow_restricted: bool = False,
    ) -> dict[str, Any]:
        selected: dict[str, dict[str, Any]] = {}
        for state_id in state_ids:
            record = self.get_state(state_id)
            selected[state_id] = record
        for run_id in run_ids:
            for record in self.list_states(run_id=run_id):
                selected[record["state_id"]] = record
        if include_all:
            for record in self.list_states():
                selected[record["state_id"]] = record
        if not selected:
            raise ModelStateError("archaeology export requires at least one selected model state")
        if len(selected) > MAX_EXPORT_STATES:
            raise ModelStateError("archaeology export exceeds model-state count limit")
        records = [selected[key] for key in sorted(selected, key=lambda item: item.encode("ascii"))]
        strictest = max(
            (record["privacy_class"] for record in records),
            key=lambda item: PRIVACY_RANK[item],
        )
        if strictest == "RESTRICTED" and not allow_restricted:
            raise ModelStateError("RESTRICTED archaeology export requires explicit acknowledgement")
        run_index: dict[str, list[str]] = {}
        for record in records:
            run_index.setdefault(record["system"]["control_run_id"], []).append(record["state_id"])
        run_index = {
            run_id: sorted(ids, key=lambda item: item.encode("ascii"))
            for run_id, ids in sorted(run_index.items(), key=lambda item: item[0].encode("ascii"))
        }
        payload = {
            "protocol": ARCHAEOLOGY_PROTOCOL,
            "model_state_protocol": MODEL_STATE_PROTOCOL,
            "state_count": len(records),
            "state_ids": [record["state_id"] for record in records],
            "run_index": run_index,
            "records": records,
            "provenance_kinds": sorted(PROVENANCE_KINDS),
            "privacy_class": strictest,
            "epistemic_boundary": EPISTEMIC_BOUNDARY,
            "hidden_chain_of_thought_captured": False,
            "model_mind_captured": False,
            "contains_model_artifact_bytes": False,
            "local_artifact_paths_persisted": False,
            "artifact_identity_semantics": "hashes-and-descriptors-only",
            "reconstruction_scope": (
                "externally inspectable computational circumstances; not hidden cognition"
            ),
            "ui_boundary_label": "Reproducibility metadata — not model mind",
            "authority": "reproducibility-archive-only",
        }
        return {"export_id": self._identity(payload), **payload}

    def write_archaeology_export(
        self,
        output: str | Path,
        *,
        state_ids: Iterable[str] = (),
        run_ids: Iterable[str] = (),
        include_all: bool = False,
        allow_restricted: bool = False,
    ) -> dict[str, Any]:
        export = self.build_archaeology_export(
            state_ids=state_ids,
            run_ids=run_ids,
            include_all=include_all,
            allow_restricted=allow_restricted,
        )
        path = Path(output)
        if path.exists() or path.is_symlink():
            raise ModelStateError("archaeology export output must not already exist")
        _atomic_write(path, canonical_json_bytes(export), mode=0o600)
        return export


__all__ = [
    "ARCHAEOLOGY_PROTOCOL",
    "EPISTEMIC_BOUNDARY",
    "MODEL_STATE_PROTOCOL",
    "ModelStateError",
    "ModelStateRegistry",
    "PROVENANCE_KINDS",
    "hash_local_artifact",
]
