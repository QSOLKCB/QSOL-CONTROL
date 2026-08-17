#!/usr/bin/env python3
"""Dependency-free structural validator for QSOL-CONTROL bootstrap contracts."""

from __future__ import annotations

import json
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
FORBIDDEN_SECRET_MARKERS = ("ghp_", "github_pat_", "Bearer ", "AKIA", "-----BEGIN PRIVATE KEY-----")


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
    """Parse the validator's minimum Python contract as exactly MAJOR.MINOR."""
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
            raise ValueError(f"{path.relative_to(ROOT)} contains forbidden secret marker {marker!r}")


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
        if requester_id is not None and (not isinstance(requester_id, str) or len(requester_id) > 256):
            raise ValueError("query requester.id is invalid")


def validate_interaction_instance(value: dict[str, Any]) -> None:
    required = {
        "protocol", "run_id", "question_sha256", "mode", "requester_kind",
        "created_at", "evidence_state", "record_refs", "model_state_refs", "replayability",
    }
    require_keys(value, required, "interaction fixture")
    if value["protocol"] != "qsol-control-interaction/1":
        raise ValueError("interaction protocol mismatch")
    if not isinstance(value["run_id"], str) or not RUN_ID_RE.fullmatch(value["run_id"]):
        raise ValueError("interaction run_id must be a sha256 content identifier")
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
    if any(not isinstance(ref, str) or not RUN_ID_RE.fullmatch(ref) for ref in model_refs):
        raise ValueError("interaction model_state_refs contain an invalid hash reference")
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
        "hidden_chain_of_thought_captured",
    }
    require_keys(value, required, "model-state fixture")
    if value["protocol"] != "qsol-control-model-state/1":
        raise ValueError("model-state protocol mismatch")
    if not isinstance(value["state_id"], str) or not RUN_ID_RE.fullmatch(value["state_id"]):
        raise ValueError("model-state state_id is invalid")
    parse_datetime(value["captured_at"], "model-state captured_at")
    model = value["model"]
    if not isinstance(model, dict):
        raise ValueError("model-state model must be an object")
    require_keys(model, {"provider", "runtime", "model_id"}, "model-state model")
    for field in ("provider", "runtime", "model_id"):
        if not isinstance(model[field], str) or not model[field]:
            raise ValueError(f"model-state model.{field} must be non-empty")
    provenance = model.get("metadata_provenance")
    if provenance is not None and provenance not in {
        "observed", "provider_reported", "locally_verified", "inferred", "unknown"
    }:
        raise ValueError("model-state metadata_provenance is invalid")
    execution = value["execution"]
    if not isinstance(execution, dict):
        raise ValueError("model-state execution must be an object")
    context_limit = execution.get("context_limit")
    if context_limit is not None and (not isinstance(context_limit, int) or context_limit < 1):
        raise ValueError("model-state context_limit is invalid")
    system = value["system"]
    if not isinstance(system, dict):
        raise ValueError("model-state system must be an object")
    require_keys(system, {"control_run_id"}, "model-state system")
    if not isinstance(system["control_run_id"], str) or not RUN_ID_RE.fullmatch(system["control_run_id"]):
        raise ValueError("model-state control_run_id is invalid")
    if value["hidden_chain_of_thought_captured"] is not False:
        raise ValueError("model-state must never claim hidden chain-of-thought capture")


def validate_schema_examples(manifest: dict[str, Any]) -> int:
    validators: dict[str, Callable[[dict[str, Any]], None]] = {
        "query": validate_query_instance,
        "interaction": validate_interaction_instance,
        "model_state": validate_model_state_instance,
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

    for path in manifest.get("documentation", []):
        require_file(path)

    schema_draft = manifest.get("json_schema", {}).get("draft")
    if schema_draft != "https://json-schema.org/draft/2020-12/schema":
        raise ValueError("QSOL-CONTROL Phase 0 requires JSON Schema draft 2020-12")
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
        "CONTROL_DISPLAY != AUTHORITY",
        "VOTE != EVIDENCE",
        "CONSENSUS != TRUTH",
        "STORED != TRUE",
        "MODEL_STATE != MODEL_MIND",
        "VISIBLE_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT",
        "CONTROL_MUST_NOT_REWRITE_ORACLE_HISTORY",
        "CONTROL_MUST_NOT_CHANGE_NEXUS_VOTES",
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

    example_count = validate_schema_examples(manifest)

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for phrase in [
        "QSOL-SUBSTRATE  KNOWS",
        "QSOL-ARK        SURVIVES",
        "QSOL-INT        COMPOSES",
        "QSOL-ORACLE     WITNESSES",
        "QSOL-NEXUS      REASONS",
        "QSOL-CONTROL    OPERATES",
        "LATTICE MEMORY  REMEMBERS",
    ]:
        if phrase not in readme:
            raise ValueError(f"README architecture missing role line: {phrase}")

    return {
        "protocol": manifest["protocol"],
        "status": "valid",
        "documentation_files": len(manifest.get("documentation", [])),
        "schemas": len(manifest.get("schemas", {})),
        "schema_examples": example_count,
        "schema_draft": schema_draft,
        "lattice_cells": lattice["top_level_cell_count"],
    }


def main() -> int:
    report = validate()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
