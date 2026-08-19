#!/usr/bin/env python3
"""Dependency-free structural validator for QSOL-CONTROL contracts."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RUN_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
LATTICE_RE = re.compile(r"^L\[[0-2],[0-2],[0-2]\](?:/L\[[0-2],[0-2],[0-2]\])*$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
PYTHON_MAJOR_MINOR_RE = re.compile(r"^[0-9]+\.[0-9]+$")
FORBIDDEN_SECRET_MARKERS = (
    "ghp_", "github_pat_", "Bearer ", "AKIA", "-----BEGIN PRIVATE KEY-----"
)
PRIVACY_CLASSES = {"PUBLIC", "INTERNAL", "RESTRICTED"}
RETENTION_CLASSES = {"TRANSIENT", "SESSION", "ARCHIVE"}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return value


def require_file(relative: str) -> None:
    path = ROOT / relative
    if not path.is_file():
        raise ValueError(f"missing declared file: {relative}")


def parse_datetime(value: Any, field: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 string")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include an explicit UTC offset")


def parse_python_minimum(value: Any) -> tuple[int, int]:
    if not isinstance(value, str) or not PYTHON_MAJOR_MINOR_RE.fullmatch(value):
        raise ValueError("validation.python_minimum must use MAJOR.MINOR")
    major, minor = value.split(".")
    return int(major), int(minor)


def require_keys(value: dict[str, Any], required: set[str], name: str) -> None:
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"{name} missing required fields: {missing}")


def reject_obvious_secrets(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for marker in FORBIDDEN_SECRET_MARKERS:
        if marker in text:
            raise ValueError(
                f"{path.relative_to(ROOT)} contains forbidden secret marker {marker!r}"
            )


def require_sha_ref(value: Any, field: str) -> None:
    if not isinstance(value, str) or not RUN_ID_RE.fullmatch(value):
        raise ValueError(f"{field} must be a sha256: content reference")


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def validate_query_instance(value: dict[str, Any]) -> None:
    require_keys(value, {"operation", "question", "mode"}, "query fixture")
    if value["operation"] != "control.ask":
        raise ValueError("query operation must be control.ask")
    question = value["question"]
    if not isinstance(question, str) or not (1 <= len(question) <= 32768):
        raise ValueError("query question must contain 1..32768 characters")
    if value["mode"] not in {"evidence_only", "council"}:
        raise ValueError("query mode is invalid")
    include = value.get("include", [])
    allowed_include = {
        "oracle_evidence", "sources", "votes", "minority_reports",
        "model_states", "receipts", "lattice_refs",
    }
    if not isinstance(include, list) or len(include) > 16 or len(include) != len(set(include)):
        raise ValueError("query include must be a unique list with at most 16 items")
    if any(item not in allowed_include for item in include):
        raise ValueError("query include contains an unsupported item")
    requester = value.get("requester")
    if requester is not None:
        if not isinstance(requester, dict) or requester.get("kind") not in {"human", "ai", "system"}:
            raise ValueError("query requester.kind is invalid")
        requester_id = requester.get("id")
        if requester_id is not None and (
            not isinstance(requester_id, str) or len(requester_id) > 256
        ):
            raise ValueError("query requester.id is invalid")


def validate_interaction_instance(value: dict[str, Any]) -> None:
    required = {
        "protocol", "run_id", "question_sha256", "mode", "requester_kind",
        "created_at", "evidence_state", "record_refs", "model_state_refs", "replayability",
    }
    require_keys(value, required, "interaction fixture")
    if value["protocol"] != "qsol-control-interaction/1":
        raise ValueError("interaction protocol mismatch")
    require_sha_ref(value["run_id"], "interaction run_id")
    if not isinstance(value["question_sha256"], str) or not SHA256_RE.fullmatch(value["question_sha256"]):
        raise ValueError("interaction question_sha256 is invalid")
    if value["mode"] not in {"evidence_only", "council"}:
        raise ValueError("interaction mode is invalid")
    if value["requester_kind"] not in {"human", "ai", "system"}:
        raise ValueError("interaction requester_kind is invalid")
    parse_datetime(value["created_at"], "interaction created_at")
    if value["evidence_state"] not in {"known", "conflict", "unknown", "unavailable"}:
        raise ValueError("interaction evidence_state is invalid")
    record_refs = value["record_refs"]
    if not isinstance(record_refs, list) or not record_refs or len(record_refs) != len(set(record_refs)):
        raise ValueError("interaction record_refs must be a non-empty unique list")
    model_refs = value["model_state_refs"]
    if not isinstance(model_refs, list) or len(model_refs) != len(set(model_refs)):
        raise ValueError("interaction model_state_refs must be unique")
    for ref in model_refs:
        require_sha_ref(ref, "interaction model_state_ref")
    lattice_refs = value.get("lattice_refs", [])
    if not isinstance(lattice_refs, list) or len(lattice_refs) != len(set(lattice_refs)):
        raise ValueError("interaction lattice_refs must be unique")
    if any(not isinstance(ref, str) or not LATTICE_RE.fullmatch(ref) for ref in lattice_refs):
        raise ValueError("interaction lattice_refs contain an invalid address")
    if value["replayability"] not in {"R0", "R1", "R2", "R3"}:
        raise ValueError("interaction replayability is invalid")


def validate_model_state_instance(value: dict[str, Any]) -> None:
    required = {
        "protocol", "state_id", "captured_at", "model", "execution", "system",
        "field_provenance", "privacy_class", "epistemic_boundary",
        "hidden_chain_of_thought_captured", "model_mind_captured", "authority",
    }
    if set(value) != required:
        missing = sorted(required - set(value))
        extra = sorted(set(value) - required)
        raise ValueError(
            f"model-state fixture fields mismatch; missing={missing}, extra={extra}"
        )
    if value["protocol"] != "qsol-control-model-state/1":
        raise ValueError("model-state protocol mismatch")
    require_sha_ref(value["state_id"], "model-state state_id")
    parse_datetime(value["captured_at"], "model-state captured_at")
    if value["privacy_class"] not in PRIVACY_CLASSES:
        raise ValueError("model-state privacy_class is invalid")
    if value["epistemic_boundary"] != "MODEL_STATE != MODEL_MIND":
        raise ValueError("model-state epistemic boundary is invalid")
    if value["hidden_chain_of_thought_captured"] is not False:
        raise ValueError("model-state must never claim hidden chain-of-thought capture")
    if value["model_mind_captured"] is not False:
        raise ValueError("model-state must never claim model-mind capture")
    if value["authority"] != "reproducibility-metadata-only":
        raise ValueError("model-state authority is invalid")

    model = value["model"]
    model_keys = {
        "provider", "runtime", "runtime_version", "model_id", "revision",
        "model_hash", "weight_hash", "tokenizer_identity", "tokenizer_hash",
        "quantization", "artifacts",
    }
    if not isinstance(model, dict) or set(model) != model_keys:
        raise ValueError("model-state model fields are invalid")
    for field, limit in (("provider", 256), ("runtime", 256), ("model_id", 1024)):
        item = model[field]
        if not isinstance(item, str) or not (1 <= len(item) <= limit):
            raise ValueError(f"model-state model.{field} is invalid")
    for field, limit in (
        ("runtime_version", 256), ("revision", 1024),
        ("tokenizer_identity", 1024), ("quantization", 256),
    ):
        item = model[field]
        if item is not None and (
            not isinstance(item, str) or not (1 <= len(item) <= limit)
        ):
            raise ValueError(f"model-state model.{field} is invalid")
    for field in ("model_hash", "weight_hash", "tokenizer_hash"):
        item = model[field]
        if item is not None:
            require_sha_ref(item, f"model-state model.{field}")
    artifacts = model["artifacts"]
    if not isinstance(artifacts, dict) or set(artifacts) != {"model", "weights", "tokenizer"}:
        raise ValueError("model-state model.artifacts is invalid")
    for role, artifact in artifacts.items():
        if artifact is None:
            continue
        if not isinstance(artifact, dict) or set(artifact) != {
            "kind", "sha256", "size_bytes", "file_count", "manifest_protocol",
        }:
            raise ValueError(f"model-state artifact {role} is invalid")
        if artifact["kind"] not in {"file-bytes", "directory-manifest"}:
            raise ValueError(f"model-state artifact {role} kind is invalid")
        require_sha_ref(artifact["sha256"], f"model-state artifact {role} sha256")
        if type(artifact["size_bytes"]) is not int or artifact["size_bytes"] < 0:
            raise ValueError(f"model-state artifact {role} size is invalid")
        if type(artifact["file_count"]) is not int or artifact["file_count"] < 0:
            raise ValueError(f"model-state artifact {role} file_count is invalid")
        if artifact["kind"] == "file-bytes":
            if artifact["file_count"] != 1 or artifact["manifest_protocol"] is not None:
                raise ValueError(f"model-state artifact {role} file descriptor is inconsistent")
        elif artifact["manifest_protocol"] != "qsol-control-local-artifact-manifest/1":
            raise ValueError(f"model-state artifact {role} manifest protocol is invalid")
        hash_field = {"model": "model_hash", "weights": "weight_hash", "tokenizer": "tokenizer_hash"}[role]
        if model[hash_field] != artifact["sha256"]:
            raise ValueError(f"model-state model.{hash_field} differs from artifact")

    execution = value["execution"]
    execution_keys = {
        "council_seat", "mode", "stochastic", "seed", "context_limit",
        "sampling", "tool_permissions", "tool_permission_envelope",
    }
    if not isinstance(execution, dict) or set(execution) != execution_keys:
        raise ValueError("model-state execution fields are invalid")
    for field in ("council_seat", "mode"):
        item = execution[field]
        if item is not None and (
            not isinstance(item, str) or not item or len(item) > 256
        ):
            raise ValueError(f"model-state execution.{field} is invalid")
    if execution["stochastic"] is not None and type(execution["stochastic"]) is not bool:
        raise ValueError("model-state stochastic is invalid")
    seed = execution["seed"]
    if seed is not None and (type(seed) not in (int, str) or isinstance(seed, bool)):
        raise ValueError("model-state seed is invalid")
    context_limit = execution["context_limit"]
    if context_limit is not None and (
        type(context_limit) is not int or context_limit < 1
    ):
        raise ValueError("model-state context_limit is invalid")
    if not isinstance(execution["sampling"], dict):
        raise ValueError("model-state sampling must be an object")
    permissions = execution["tool_permissions"]
    if (
        not isinstance(permissions, list)
        or any(not isinstance(item, str) or not item for item in permissions)
        or len(permissions) != len(set(permissions))
        or permissions != sorted(permissions, key=lambda item: item.encode("utf-8"))
    ):
        raise ValueError("model-state tool_permissions are invalid or non-canonical")
    envelope = execution["tool_permission_envelope"]
    if not isinstance(envelope, dict) or set(envelope) != {
        "filesystem", "network", "tools", "mcp_plugins", "external_execution",
    }:
        raise ValueError("model-state tool_permission_envelope is invalid")
    if envelope["filesystem"] not in {
        "none", "read-only", "workspace-write", "unrestricted", "unknown",
    }:
        raise ValueError("model-state filesystem permission is invalid")
    if envelope["network"] not in {
        "none", "loopback", "restricted", "unrestricted", "unknown",
    }:
        raise ValueError("model-state network permission is invalid")
    tools = envelope["tools"]
    plugins = envelope["mcp_plugins"]
    for items, label in ((tools, "tools"), (plugins, "mcp_plugins")):
        if (
            not isinstance(items, list)
            or any(not isinstance(item, str) or not item for item in items)
            or len(items) != len(set(items))
            or items != sorted(items, key=lambda item: item.encode("utf-8"))
        ):
            raise ValueError(f"model-state {label} are invalid or non-canonical")
    if tools != permissions:
        raise ValueError("model-state tool permission lists disagree")
    if envelope["external_execution"] is not None and type(envelope["external_execution"]) is not bool:
        raise ValueError("model-state external_execution is invalid")

    system = value["system"]
    system_keys = {
        "control_run_id", "control_manifest_identity", "nexus_identity", "oracle_refs",
        "substrate_identity", "ark_identity", "int_identity", "collection_snapshot_id",
        "evidence_snapshot_ref", "hardware_runtime_metadata",
    }
    if not isinstance(system, dict) or set(system) != system_keys:
        raise ValueError("model-state system fields are invalid")
    require_sha_ref(system["control_run_id"], "model-state control_run_id")
    for field in (
        "control_manifest_identity", "nexus_identity", "substrate_identity",
        "ark_identity", "int_identity", "evidence_snapshot_ref",
    ):
        item = system[field]
        if item is not None and (
            not isinstance(item, str) or not item or len(item) > 1024
        ):
            raise ValueError(f"model-state system.{field} is invalid")
    refs = system["oracle_refs"]
    if (
        not isinstance(refs, list)
        or any(not isinstance(item, str) or not item for item in refs)
        or len(refs) != len(set(refs))
        or refs != sorted(refs, key=lambda item: item.encode("utf-8"))
    ):
        raise ValueError("model-state oracle_refs are invalid or non-canonical")
    if system["collection_snapshot_id"] is not None:
        require_sha_ref(system["collection_snapshot_id"], "model-state collection_snapshot_id")
    if not isinstance(system["hardware_runtime_metadata"], dict):
        raise ValueError("model-state hardware_runtime_metadata must be an object")

    provenance = value["field_provenance"]
    provenance_fields = {
        "captured_at",
        "model.provider", "model.runtime", "model.runtime_version", "model.model_id",
        "model.revision", "model.model_hash", "model.weight_hash",
        "model.tokenizer_identity", "model.tokenizer_hash", "model.quantization",
        "model.artifacts.model", "model.artifacts.weights", "model.artifacts.tokenizer",
        "execution.council_seat", "execution.mode", "execution.stochastic",
        "execution.seed", "execution.context_limit", "execution.sampling",
        "execution.tool_permissions", "execution.tool_permission_envelope",
        "system.control_run_id", "system.control_manifest_identity",
        "system.nexus_identity", "system.oracle_refs", "system.substrate_identity",
        "system.ark_identity", "system.int_identity", "system.collection_snapshot_id",
        "system.evidence_snapshot_ref", "system.hardware_runtime_metadata",
    }
    allowed_provenance = {
        "observed", "provider_reported", "locally_verified", "inferred", "unknown",
    }
    if not isinstance(provenance, dict) or set(provenance) != provenance_fields:
        raise ValueError("model-state field_provenance is incomplete or contains extras")
    if any(item not in allowed_provenance for item in provenance.values()):
        raise ValueError("model-state field_provenance contains an invalid class")
    if provenance["captured_at"] != "observed":
        raise ValueError("model-state captured_at provenance must be observed")
    if provenance["system.control_run_id"] != "locally_verified":
        raise ValueError("model-state control_run_id provenance must be locally_verified")

    payload = {key: item for key, item in value.items() if key != "state_id"}
    expected_state_id = "sha256:" + hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    if value["state_id"] != expected_state_id:
        raise ValueError("model-state state_id does not match canonical content")


def validate_file_instance(value: dict[str, Any]) -> None:
    required = {
        "file_id", "protocol", "object_id", "content_sha256", "size_bytes", "filename",
        "media_type", "created_at", "privacy_class", "retention_class", "source", "metadata",
    }
    require_keys(value, required, "file fixture")
    if value["protocol"] != "qsol-control-file/1":
        raise ValueError("file protocol mismatch")
    require_sha_ref(value["file_id"], "file_id")
    require_sha_ref(value["object_id"], "file object_id")
    if not isinstance(value["content_sha256"], str) or not SHA256_RE.fullmatch(value["content_sha256"]):
        raise ValueError("file content_sha256 is invalid")
    if not isinstance(value["size_bytes"], int) or value["size_bytes"] < 0:
        raise ValueError("file size_bytes is invalid")
    if not isinstance(value["filename"], str) or not (1 <= len(value["filename"]) <= 512):
        raise ValueError("file filename is invalid")
    if not isinstance(value["media_type"], str) or not (1 <= len(value["media_type"]) <= 256):
        raise ValueError("file media_type is invalid")
    parse_datetime(value["created_at"], "file created_at")
    if value["privacy_class"] not in PRIVACY_CLASSES:
        raise ValueError("file privacy_class is invalid or forbidden")
    if value["retention_class"] not in RETENTION_CLASSES:
        raise ValueError("file retention_class is invalid")
    if not isinstance(value["source"], dict):
        raise ValueError("file source must be an object")
    require_keys(value["source"], {"kind", "locator"}, "file source")
    if not isinstance(value["metadata"], dict):
        raise ValueError("file metadata must be an object")


def validate_collection_instance(value: dict[str, Any]) -> None:
    required = {
        "collection_id", "protocol", "name", "created_at", "privacy_class",
        "retention_class", "metadata",
    }
    require_keys(value, required, "collection fixture")
    if value["protocol"] != "qsol-control-collection/1":
        raise ValueError("collection protocol mismatch")
    require_sha_ref(value["collection_id"], "collection_id")
    if not isinstance(value["name"], str) or not (1 <= len(value["name"]) <= 256):
        raise ValueError("collection name is invalid")
    parse_datetime(value["created_at"], "collection created_at")
    if value["privacy_class"] not in PRIVACY_CLASSES:
        raise ValueError("collection privacy_class is invalid or forbidden")
    if value["retention_class"] not in RETENTION_CLASSES:
        raise ValueError("collection retention_class is invalid")
    if not isinstance(value["metadata"], dict):
        raise ValueError("collection metadata must be an object")


def validate_collection_snapshot_instance(value: dict[str, Any]) -> None:
    required = {
        "snapshot_id", "protocol", "collection_id", "revision", "previous_snapshot_id",
        "created_at", "members",
    }
    require_keys(value, required, "collection snapshot fixture")
    if value["protocol"] != "qsol-control-collection-snapshot/1":
        raise ValueError("collection snapshot protocol mismatch")
    require_sha_ref(value["snapshot_id"], "snapshot_id")
    require_sha_ref(value["collection_id"], "snapshot collection_id")
    if not isinstance(value["revision"], int) or value["revision"] < 0:
        raise ValueError("collection snapshot revision is invalid")
    previous = value["previous_snapshot_id"]
    if previous is not None:
        require_sha_ref(previous, "previous_snapshot_id")
    if value["revision"] == 0 and previous is not None:
        raise ValueError("revision 0 must not have a previous snapshot")
    if value["revision"] > 0 and previous is None:
        raise ValueError("non-zero revision must reference a previous snapshot")
    parse_datetime(value["created_at"], "collection snapshot created_at")
    members = value["members"]
    if not isinstance(members, list) or len(members) != len(set(members)):
        raise ValueError("collection snapshot members must be a unique list")
    for member in members:
        require_sha_ref(member, "collection snapshot member")


def validate_search_index_instance(value: dict[str, Any]) -> None:
    required = {
        "index_id", "protocol", "kind", "engine", "collection_id", "snapshot_id",
        "built_at", "derived", "rebuildable", "authority",
    }
    require_keys(value, required, "search index fixture")
    if value["protocol"] != "qsol-control-search-index/1":
        raise ValueError("search index protocol mismatch")
    require_sha_ref(value["index_id"], "search index_id")
    require_sha_ref(value["collection_id"], "search collection_id")
    require_sha_ref(value["snapshot_id"], "search snapshot_id")
    if value["kind"] not in {"deterministic-lexical-baseline", "semantic-vector"}:
        raise ValueError("search index kind is invalid")
    if not isinstance(value["engine"], str) or not value["engine"]:
        raise ValueError("search index engine is invalid")
    parse_datetime(value["built_at"], "search index built_at")
    if value["derived"] is not True or value["rebuildable"] is not True:
        raise ValueError("search indexes must be derived and rebuildable")
    if value["authority"] != "none":
        raise ValueError("search indexes must have no authority")

    if value["kind"] == "deterministic-lexical-baseline":
        documents = value.get("documents")
        skipped = value.get("skipped_file_ids")
        if not isinstance(documents, dict) or not isinstance(skipped, list):
            raise ValueError("lexical index requires documents and skipped_file_ids")
        for file_id, terms in documents.items():
            require_sha_ref(file_id, "lexical document file_id")
            if not isinstance(terms, dict):
                raise ValueError("lexical term map must be an object")
            if any(not isinstance(count, int) or count < 1 for count in terms.values()):
                raise ValueError("lexical term counts must be positive integers")
        if len(skipped) != len(set(skipped)):
            raise ValueError("skipped_file_ids must be unique")
        for file_id in skipped:
            require_sha_ref(file_id, "skipped file_id")
    else:
        embedding = value.get("embedding")
        vectors = value.get("vectors")
        if not isinstance(embedding, dict) or not isinstance(vectors, dict):
            raise ValueError("semantic index requires embedding descriptor and vectors")
        require_keys(embedding, {"provider", "model_id", "revision", "dimensions"}, "embedding")
        dimensions = embedding["dimensions"]
        if not isinstance(dimensions, int) or dimensions < 1:
            raise ValueError("embedding dimensions are invalid")
        for file_id, vector in vectors.items():
            require_sha_ref(file_id, "semantic vector file_id")
            if not isinstance(vector, list) or len(vector) != dimensions:
                raise ValueError("semantic vector dimension mismatch")
            if any(
                not isinstance(item, (int, float)) or not math.isfinite(float(item))
                for item in vector
            ):
                raise ValueError("semantic vectors must contain finite numbers")


def validate_schema_examples(manifest: dict[str, Any]) -> int:
    validators: dict[str, Callable[[dict[str, Any]], None]] = {
        "query": validate_query_instance,
        "interaction": validate_interaction_instance,
        "model_state": validate_model_state_instance,
        "file": validate_file_instance,
        "collection": validate_collection_instance,
        "collection_snapshot": validate_collection_snapshot_instance,
        "search_index": validate_search_index_instance,
    }
    example_map = manifest.get("schema_examples", {})
    if set(example_map) != set(validators):
        raise ValueError("manifest must declare valid/invalid examples for every schema")

    validated = 0
    for name, validator in validators.items():
        paths = example_map[name]
        if set(paths) != {"valid", "invalid"}:
            raise ValueError(f"schema example {name} must declare valid and invalid fixtures")
        valid_path = ROOT / paths["valid"]
        invalid_path = ROOT / paths["invalid"]
        require_file(paths["valid"])
        require_file(paths["invalid"])
        reject_obvious_secrets(valid_path)
        reject_obvious_secrets(invalid_path)
        validator(load_json(valid_path))
        try:
            validator(load_json(invalid_path))
        except ValueError:
            pass
        else:
            raise ValueError(f"invalid {name} fixture unexpectedly passed validation")
        validated += 2
    return validated


def validate() -> dict[str, Any]:
    manifest = load_json(ROOT / "manifest.json")
    if manifest.get("protocol") != "QSOL-CONTROL/0.1":
        raise ValueError("manifest protocol mismatch")
    if manifest.get("semantic_authority") != "none":
        raise ValueError("CONTROL must not claim semantic authority")
    if not SEMVER_RE.fullmatch(str(manifest.get("schema_version", ""))):
        raise ValueError("manifest schema_version must use MAJOR.MINOR.PATCH")

    python_minimum = manifest.get("validation", {}).get("python_minimum")
    minimum_python = parse_python_minimum(python_minimum)
    if sys.version_info[:2] < minimum_python:
        raise ValueError(f"validator requires Python >= {python_minimum}")

    require_file(manifest["license"])
    require_file(manifest["machine_entrypoint"])
    require_file(manifest["constitution"])
    require_file(manifest["lattice_contract"])
    require_file(manifest["architecture"])
    require_file(manifest["roadmap"])
    require_file(manifest["security"])
    require_file(manifest["persistent_storage_document"])
    require_file(manifest["persistent_storage"]["runtime"])
    require_file(manifest["interfaces"]["storage_cli"])

    for path in manifest.get("documentation", []):
        require_file(path)

    schema_draft = manifest.get("json_schema", {}).get("draft")
    if schema_draft != "https://json-schema.org/draft/2020-12/schema":
        raise ValueError("QSOL-CONTROL requires JSON Schema draft 2020-12")
    if manifest.get("json_schema", {}).get("compatibility_policy") != "semantic-versioning":
        raise ValueError("schema compatibility policy must be semantic-versioning")
    for path in manifest.get("schemas", {}).values():
        require_file(path)
        schema = load_json(ROOT / path)
        if schema.get("$schema") != schema_draft:
            raise ValueError(f"schema draft mismatch: {path}")

    bootstrap = load_json(ROOT / "README4AI.md")
    if bootstrap.get("protocol") != manifest["protocol"]:
        raise ValueError("README4AI protocol does not match manifest")

    constitution = load_json(ROOT / "ai" / "constitution.json")
    required_invariants = {
        "CONTROL_DISPLAY != AUTHORITY", "VOTE != EVIDENCE", "CONSENSUS != TRUTH",
        "STORED != TRUE", "MODEL_STATE != MODEL_MIND",
        "VISIBLE_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT",
        "CONTROL_MUST_NOT_REWRITE_ORACLE_HISTORY", "CONTROL_MUST_NOT_CHANGE_NEXUS_VOTES",
        "SEARCH_SCORE != TRUTH", "SEMANTIC_SIMILARITY != EVIDENCE_STRENGTH",
        "INDEX != CANONICAL_MEMORY", "COLLECTION_MEMBERSHIP != ENDORSEMENT",
    }
    present = set(constitution.get("invariants", []))
    missing = sorted(required_invariants - present)
    if missing:
        raise ValueError(f"constitution missing invariants: {missing}")

    lattice = load_json(ROOT / "ai" / "lattice-contract.json")
    if lattice.get("top_level_cell_count") != 27:
        raise ValueError("lattice must declare exactly 27 top-level cells")
    axes = lattice.get("axes", {})
    if set(axes) != {"x", "y", "z"}:
        raise ValueError("lattice must define x, y, z axes")
    for axis_name, axis in axes.items():
        values = axis.get("values", {})
        if set(values) != {"0", "1", "2"}:
            raise ValueError(f"axis {axis_name} must define exactly values 0, 1, 2")
    if lattice.get("literal_geometric_claim") is not False:
        raise ValueError("lattice must remain a logical, not literal geometric claim")

    model_schema = load_json(ROOT / manifest["schemas"]["model_state"])
    hidden = model_schema.get("properties", {}).get("hidden_chain_of_thought_captured", {})
    if hidden.get("const") is not False:
        raise ValueError("model-state schema must forbid hidden chain-of-thought capture")
    mind = model_schema.get("properties", {}).get("model_mind_captured", {})
    if mind.get("const") is not False:
        raise ValueError("model-state schema must forbid model-mind capture")
    boundary = model_schema.get("properties", {}).get("epistemic_boundary", {})
    if boundary.get("const") != "MODEL_STATE != MODEL_MIND":
        raise ValueError("model-state schema must pin MODEL_STATE != MODEL_MIND")

    storage = manifest.get("persistent_storage", {})
    if storage.get("index_authority") != "none":
        raise ValueError("persistent search indexes must have no authority")
    if storage.get("indexes_are_derived_and_rebuildable") is not True:
        raise ValueError("search indexes must be declared derived and rebuildable")
    if storage.get("canonical_fingerprint_excludes_derived_indexes") is not True:
        raise ValueError("canonical fingerprint must exclude rebuildable indexes")
    if manifest.get("status", {}).get("phase") != 1:
        raise ValueError("persistent storage PR must declare Phase 1 status")

    example_count = validate_schema_examples(manifest)

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for phrase in [
        "QSOL-SUBSTRATE  KNOWS", "QSOL-ARK        SURVIVES", "QSOL-INT        COMPOSES",
        "QSOL-ORACLE     WITNESSES", "QSOL-NEXUS      REASONS",
        "QSOL-CONTROL    OPERATES", "LATTICE MEMORY  REMEMBERS",
    ]:
        if phrase not in readme:
            raise ValueError(f"README architecture missing role line: {phrase}")

    return {
        "protocol": manifest["protocol"], "status": "valid",
        "phase": manifest["status"]["phase"],
        "documentation_files": len(manifest.get("documentation", [])),
        "schemas": len(manifest.get("schemas", {})), "schema_examples": example_count,
        "schema_draft": schema_draft, "lattice_cells": lattice["top_level_cell_count"],
        "persistent_storage": storage["collection_protocol"],
    }


def main() -> int:
    report = validate()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
