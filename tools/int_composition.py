#!/usr/bin/env python3
"""QSOL-CONTROL Phase 9 INT-style composition batteries.

The runner produces deterministic CONTROL-local conformance receipts bound to
exact pinned parent evidence. It does not redefine QSOL-INT composition
authority and never turns compatibility into truth, evidence, or endorsement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
PINS_PATH = ROOT / "composition" / "parent-pins.json"
CASES_PATH = ROOT / "composition" / "cases.json"
PROTOCOL = "qsol-control-int-composition-report/1"
OBSERVED_PROTOCOL = "qsol-control-int-observed-parents/1"
VERSION = "1.0.0"


class CompositionError(ValueError):
    """Raised when pinned evidence or a composition boundary is invalid."""


def _no_constant(value: str) -> None:
    raise CompositionError(f"non-finite JSON number is forbidden: {value}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise CompositionError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def load_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CompositionError(f"cannot read {path}") from exc
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_no_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise CompositionError(f"invalid UTF-8 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise CompositionError(f"JSON root must be an object: {path}")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_sha1(data: bytes) -> str:
    prefix = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(prefix + data).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CompositionError(message)


def _major(value: Any) -> int | None:
    if not isinstance(value, str) or not value:
        return None
    head = value.split("/", 1)[-1] if "/" in value else value
    head = head.lstrip("v")
    token = head.split(".", 1)[0]
    return int(token) if token.isdigit() else None


def validate_pins(pins: dict[str, Any]) -> None:
    _require(pins.get("protocol") == "qsol-control-int-parent-pins/1", "parent pin protocol mismatch")
    _require(pins.get("scope") == "pinned_parent_evidence_only", "parent pin scope must remain pinned only")
    _require(pins.get("authority") == "compatibility-evidence-only", "parent pins must have compatibility-only authority")
    methodology = pins.get("int_methodology")
    _require(isinstance(methodology, dict), "INT methodology pin is missing")
    _require(methodology.get("repository") == "QSOLKCB/QSOL-INT", "INT methodology repository mismatch")
    _require(methodology.get("rule") == "INTEGRATION_MUST_NOT_INCREASE_SEMANTIC_AUTHORITY", "INT non-escalation rule missing")
    parents = pins.get("parents")
    _require(isinstance(parents, dict) and set(parents) == {"oracle", "nexus", "thoth"}, "parent pin set must be oracle/nexus/thoth")
    for name, row in parents.items():
        _require(isinstance(row, dict), f"{name} parent pin must be an object")
        _require(isinstance(row.get("repository"), str) and row["repository"].startswith("QSOLKCB/"), f"{name} repository is invalid")
        commit = row.get("pinned_commit")
        _require(isinstance(commit, str) and len(commit) == 40 and all(c in "0123456789abcdef" for c in commit), f"{name} pinned commit is invalid")
        artifact = row.get("artifact")
        _require(isinstance(artifact, dict), f"{name} artifact pin missing")
        blob = artifact.get("git_blob_sha1")
        _require(isinstance(blob, str) and len(blob) == 40 and all(c in "0123456789abcdef" for c in blob), f"{name} blob identity is invalid")
        _require(isinstance(row.get("expected"), dict), f"{name} semantic projection missing")
    local = pins.get("local_contracts")
    _require(isinstance(local, dict) and set(local) == {"oracle", "nexus", "thoth"}, "local contract pin set mismatch")
    for name, row in local.items():
        _require(isinstance(row, dict), f"local {name} contract pin invalid")
        path = row.get("path")
        blob = row.get("git_blob_sha1")
        _require(isinstance(path, str) and path.startswith("ai/"), f"local {name} contract path invalid")
        _require(isinstance(blob, str) and len(blob) == 40, f"local {name} blob pin invalid")
        try:
            raw = (ROOT / path).read_bytes()
        except OSError as exc:
            raise CompositionError(f"local {name} contract is unavailable") from exc
        _require(git_blob_sha1(raw) == blob, f"local {name} contract drifted from Phase 9 pin")


def validate_cases(index: dict[str, Any]) -> list[dict[str, Any]]:
    _require(index.get("protocol") == "qsol-control-int-battery-index/1", "battery index protocol mismatch")
    _require(index.get("authority") == "conformance-only", "battery index authority mismatch")
    rows = index.get("cases")
    _require(isinstance(rows, list) and len(rows) == 11, "Phase 9 requires exactly 11 declared battery cases")
    ids: set[str] = set()
    names: set[str] = set()
    for row in rows:
        _require(isinstance(row, dict), "battery case must be an object")
        case_id = row.get("id")
        name = row.get("name")
        _require(isinstance(case_id, str) and case_id.startswith("CONTROL-INT-"), "battery id invalid")
        _require(isinstance(name, str) and name, "battery name invalid")
        _require(case_id not in ids and name not in names, "battery ids/names must be unique")
        ids.add(case_id)
        names.add(name)
    return rows


def _local_contract(name: str, pins: dict[str, Any]) -> dict[str, Any]:
    row = pins["local_contracts"][name]
    return load_json(ROOT / row["path"])


def _case(case_id: str, name: str, ok: bool, observed: dict[str, Any], *, failure_code: str | None = None) -> dict[str, Any]:
    return {
        "id": case_id,
        "battery": name,
        "result": "pass" if ok else "fail",
        "failure_code": None if ok else failure_code or "CONTROL_INT_CONFORMANCE_FAILURE",
        "observed": observed,
    }


def _parent_receipt(name: str, pins: dict[str, Any]) -> dict[str, Any]:
    parent = pins["parents"][name]
    local = pins["local_contracts"][name]
    return {
        "parent": name,
        "repository": parent["repository"],
        "pinned_commit": parent["pinned_commit"],
        "parent_artifact": parent["artifact"],
        "local_contract": local,
        "compatibility": "compatible",
        "scope": "pinned_parent_evidence_only",
        "current_parent_compatibility": "not_claimed",
        "authority": "compatibility-evidence-only",
    }


def _validate_observed_shape(value: dict[str, Any]) -> None:
    _require(value.get("protocol") == OBSERVED_PROTOCOL, "observed parent protocol mismatch")
    parents = value.get("parents")
    _require(isinstance(parents, dict), "observed parents must be an object")
    for name, row in parents.items():
        _require(name in {"oracle", "nexus", "thoth"}, f"unknown observed parent: {name}")
        _require(isinstance(row, dict), f"observed {name} must be an object")
        if row.get("available") is False:
            continue
        _require(row.get("available") is True, f"observed {name}.available must be boolean")
        commit = row.get("commit")
        blob = row.get("git_blob_sha1")
        _require(isinstance(commit, str) and len(commit) == 40, f"observed {name} commit invalid")
        _require(isinstance(blob, str) and len(blob) == 40, f"observed {name} blob invalid")
        protocol = row.get("protocol")
        if protocol is not None:
            _require(isinstance(protocol, str) and protocol, f"observed {name} protocol invalid")
        schema_version = row.get("schema_version")
        if schema_version is not None:
            _require(isinstance(schema_version, str) and schema_version, f"observed {name} schema_version invalid")


def classify_observed_parents(pins: dict[str, Any], observed: dict[str, Any] | None) -> dict[str, Any]:
    if observed is None:
        return {
            "status": "NOT_OBSERVED",
            "compatibility": "not_claimed",
            "requires_review": False,
            "parents": {},
        }
    _validate_observed_shape(observed)
    outcomes: dict[str, Any] = {}
    review = False
    incompatible = False
    for name in ("oracle", "nexus", "thoth"):
        pin = pins["parents"][name]
        row = observed.get("parents", {}).get(name)
        if row is None or row.get("available") is False:
            outcomes[name] = {"drift": "SOURCE_UNAVAILABLE", "compatibility": "unknown", "requires_review": True}
            review = True
            continue
        if row["commit"] == pin["pinned_commit"] and row["git_blob_sha1"] == pin["artifact"]["git_blob_sha1"]:
            outcomes[name] = {"drift": "NO_DRIFT", "compatibility": "compatible", "requires_review": False}
            continue
        expected_protocol = pin["expected"].get("protocol") or pin["expected"].get("release_protocol")
        observed_protocol = row.get("protocol")
        if observed_protocol is not None and expected_protocol is not None and _major(observed_protocol) != _major(expected_protocol):
            outcomes[name] = {"drift": "BREAKING_DRIFT", "compatibility": "incompatible", "requires_review": True}
            incompatible = True
            review = True
            continue
        expected_schema = pin["expected"].get("schema_version")
        observed_schema = row.get("schema_version")
        if observed_schema is not None and expected_schema is not None and _major(observed_schema) != _major(expected_schema):
            outcomes[name] = {"drift": "SCHEMA_DRIFT", "compatibility": "untested", "requires_review": True}
            review = True
            continue
        outcomes[name] = {"drift": "CONTENT_DRIFT", "compatibility": "untested", "requires_review": True}
        review = True
    return {
        "status": "OBSERVED",
        "compatibility": "incompatible" if incompatible else ("untested" if review else "compatible"),
        "requires_review": review,
        "parents": outcomes,
    }


def _build_checks(pins: dict[str, Any], observed: dict[str, Any] | None) -> dict[str, tuple[bool, dict[str, Any], str | None]]:
    oracle = _local_contract("oracle", pins)
    nexus = _local_contract("nexus", pins)
    thoth = _local_contract("thoth", pins)
    constitution = load_json(ROOT / "ai" / "constitution.json")
    manifest = load_json(ROOT / "manifest.json")
    lattice = load_json(ROOT / "ai" / "lattice-contract.json")
    model_state = load_json(ROOT / "ai" / "model-state-contract.json")
    search_schema = load_json(ROOT / "schema" / "search-index.schema.json")
    dna_schema = load_json(ROOT / "schema" / "dna-lattice.schema.json")
    recovery = load_json(ROOT / "ai" / "ark-repository-recovery-contract.json")

    oracle_expected = pins["parents"]["oracle"]["expected"]
    oracle_ok = (
        oracle.get("parent_protocol") == oracle_expected["protocol"]
        and oracle.get("mode") == "read-only"
        and oracle.get("discovery", {}).get("required_ledger_model") == oracle_expected["ledger_model"]
        and oracle.get("evidence_query", {}).get("states") == oracle_expected["response_states"]
        and oracle.get("oracle_write_operations") == []
        and oracle.get("security_gate", {}).get("control_can_append_oracle_history") is False
        and oracle.get("security_gate", {}).get("control_can_rewrite_oracle_history") is False
        and oracle.get("security_gate", {}).get("control_can_relabel_oracle_history") is False
        and oracle.get("evidence_query", {}).get("suggested_searches_are_evidence") is oracle_expected["search_suggestions_are_evidence"]
    )

    nexus_expected = pins["parents"]["nexus"]["expected"]
    nexus_invariants = set(nexus.get("invariants", []))
    nexus_ok = (
        nexus.get("parent", {}).get("repository") == pins["parents"]["nexus"]["repository"]
        and nexus.get("parent", {}).get("transport") == nexus_expected["control_transport"]
        and nexus.get("control_surface", {}).get("mutation_operations") == ["council.run"]
        and nexus.get("control_surface", {}).get("arbitrary_operation_passthrough") is False
        and nexus.get("governance_gate", {}).get("control_can_alter_vote_weight") is False
        and nexus.get("governance_gate", {}).get("control_can_alter_ballot_contents") is False
        and nexus.get("governance_gate", {}).get("control_can_alter_consensus_threshold") is False
        and "CONSENSUS != EVIDENCE" in nexus_invariants
        and "CONSENSUS != TRUTH" in nexus_invariants
    )

    thoth_expected = pins["parents"]["thoth"]["expected"]
    thoth_boundaries = set(thoth.get("boundaries", []))
    thoth_ok = (
        thoth.get("object_identity") == "sha256(exact_object_bytes)"
        and thoth.get("object_container") == "qsol-restore-dat/1"
        and "ROUTING != RESOLUTION" in thoth_boundaries
        and "RESOLUTION != TRANSPORT" in thoth_boundaries
        and "TRANSPORT != AUTHORITY" in thoth_boundaries
        and thoth_expected["semantic_change_requires_new_version"] is True
        and thoth_expected["implicit_version_substitution"] is False
        and thoth_expected["resolver_must_match_exact_declared_role_id"] is True
    )

    constitution_invariants = set(constitution.get("invariants", []))
    authority_ok = (
        oracle_ok
        and nexus_ok
        and thoth_ok
        and "CONTROL_DISPLAY != AUTHORITY" in constitution_invariants
        and "VOTE != EVIDENCE" in constitution_invariants
        and "CONSENSUS != TRUTH" in constitution_invariants
        and "INDEX != CANONICAL_MEMORY" in constitution_invariants
        and "MODEL_STATE != MODEL_MIND" in constitution_invariants
    )

    drift = classify_observed_parents(pins, observed)
    stale_ok = drift["compatibility"] in {"not_claimed", "compatible", "untested", "incompatible", "unknown"}
    if observed is None:
        stale_observed = {
            "current_parent_compatibility": "not_claimed",
            "reason": "no live parent evidence supplied; pinned compatibility is not widened",
            "drift_is_silently_accepted": False,
        }
    else:
        stale_observed = drift

    vote_ok = (
        "VOTE != EVIDENCE" in constitution_invariants
        and "CONSENSUS != TRUTH" in constitution_invariants
        and "CONSENSUS != EVIDENCE" in nexus_invariants
        and nexus.get("render", {}).get("truth_score_generated") is False
    )

    lattice_rules = set(lattice.get("identity_rules", []))
    memory_ok = (
        lattice.get("authority") == "storage-only"
        and lattice.get("literal_geometric_claim") is False
        and "lattice_address_does_not_replace_content_hash" in lattice_rules
        and "lattice_address_does_not_confer_authority" in lattice_rules
        and manifest.get("persistent_storage", {}).get("canonical_fingerprint_excludes_derived_indexes") is True
    )

    model_invariants = set(model_state.get("invariants", []))
    model_ok = (
        model_state.get("epistemic_boundary") == "MODEL_STATE != MODEL_MIND"
        and model_state.get("authority") == "reproducibility-metadata-only"
        and model_state.get("identity", {}).get("state_id") == "sha256(canonical record payload without state_id)"
        and model_state.get("local_artifact_verification", {}).get("artifact_bytes_copied") is False
        and model_state.get("comparison", {}).get("model_mind_inference") is False
        and "HASH_IDENTITY != ARTIFACT_BYTES" in model_invariants
    )

    storage = manifest.get("persistent_storage", {})
    search_props = search_schema.get("properties", {})
    index_ok = (
        storage.get("index_authority") == "none"
        and storage.get("indexes_are_derived_and_rebuildable") is True
        and storage.get("canonical_fingerprint_excludes_derived_indexes") is True
        and search_props.get("authority", {}).get("const") == "none"
        and search_props.get("derived", {}).get("const") is True
        and search_props.get("rebuildable", {}).get("const") is True
    )

    dna_props = dna_schema.get("properties", {})
    optional_dna = recovery.get("optional_derived_material", {}).get("dna_lattice_projections", {})
    dna_ok = (
        dna_props.get("authority", {}).get("const") == "none"
        and optional_dna.get("canonical") is False
        and optional_dna.get("restored_as_raw_source") is False
        and "dna-lattice-projections" in recovery.get("canonical_fingerprint_excludes", [])
        and "RAW_OBJECT_BYTES = CANONICAL" in recovery.get("boundaries", [])
    )

    schema_version = manifest.get("schema_version")
    schema_ok = (
        isinstance(schema_version, str)
        and _major(schema_version) == 2
        and oracle.get("discovery", {}).get("unknown_major_policy") == "fail-closed"
        and pins["parents"]["thoth"]["expected"].get("new_version_backward_compatible_by_default") is False
        and pins["parents"]["thoth"]["expected"].get("implicit_version_substitution") is False
    )
    if observed is not None:
        schema_ok = schema_ok and all(
            row.get("drift") != "BREAKING_DRIFT"
            for row in drift.get("parents", {}).values()
        )

    return {
        "control_oracle_compatibility": (oracle_ok, _parent_receipt("oracle", pins), "CONTROL_INT_ORACLE_INCOMPATIBLE"),
        "control_nexus_compatibility": (nexus_ok, _parent_receipt("nexus", pins), "CONTROL_INT_NEXUS_INCOMPATIBLE"),
        "control_thoth_concap_compatibility": (thoth_ok, _parent_receipt("thoth", pins), "CONTROL_INT_THOTH_INCOMPATIBLE"),
        "authority_non_escalation": (authority_ok, {"semantic_authority_increased": False, "composition_authority_owned_by_control": False}, "CONTROL_INT_AUTHORITY_ESCALATION"),
        "stale_parent_handling": (stale_ok, stale_observed, "CONTROL_INT_STALE_PARENT_ACCEPTED"),
        "vote_evidence_separation": (vote_ok, {"vote_is_evidence": False, "consensus_is_truth": False}, "CONTROL_INT_VOTE_EVIDENCE_COLLAPSE"),
        "memory_canonical_separation": (memory_ok, {"lattice_authority": lattice.get("authority"), "lattice_replaces_content_identity": False}, "CONTROL_INT_MEMORY_CANONICAL_COLLAPSE"),
        "model_state_identity_separation": (model_ok, {"model_state_is_model_mind": False, "hash_identity_is_artifact_bytes": False}, "CONTROL_INT_MODEL_IDENTITY_COLLAPSE"),
        "collection_index_authority_separation": (index_ok, {"index_authority": storage.get("index_authority"), "index_is_canonical_memory": False}, "CONTROL_INT_INDEX_AUTHORITY_ESCALATION"),
        "dna_raw_byte_separation": (dna_ok, {"raw_objects_canonical": True, "dna_projection_canonical": False}, "CONTROL_INT_DNA_CANONICAL_COLLAPSE"),
        "schema_version_drift": (schema_ok, {"control_schema_version": schema_version, "unknown_parent_major_policy": "fail-closed", "observed_parent_state": drift}, "CONTROL_INT_SCHEMA_DRIFT_UNSAFE"),
    }


def run_batteries(*, observed: dict[str, Any] | None = None) -> dict[str, Any]:
    pins = load_json(PINS_PATH)
    validate_pins(pins)
    index = load_json(CASES_PATH)
    cases = validate_cases(index)
    checks = _build_checks(pins, observed)
    results = []
    for row in cases:
        name = row["name"]
        if name not in checks:
            raise CompositionError(f"battery case has no implementation: {name}")
        ok, observed_value, failure_code = checks[name]
        results.append(_case(row["id"], name, ok, observed_value, failure_code=failure_code))

    failed = sum(item["result"] == "fail" for item in results)
    drift = classify_observed_parents(pins, observed)
    compatibility = "incompatible" if failed else "compatible"
    payload = {
        "type": "qsol-control-int-composition-report",
        "protocol": PROTOCOL,
        "version": VERSION,
        "scope": "pinned_parent_evidence_only",
        "int_methodology": pins["int_methodology"],
        "parents": {name: _parent_receipt(name, pins) for name in ("oracle", "nexus", "thoth")},
        "current_parent_observation": drift,
        "case_results": results,
        "compatibility": compatibility,
        "summary": {
            "case_count": len(results),
            "passed": len(results) - failed,
            "failed": failed,
            "current_parent_compatibility": drift["compatibility"],
            "current_parent_review_required": drift["requires_review"],
        },
        "authority": "conformance-only",
        "int_authority_claimed": False,
        "truth_claimed": False,
        "invariants": [
            "INTEGRATION_MUST_NOT_INCREASE_SEMANTIC_AUTHORITY",
            "COMPATIBLE != TRUE",
            "BATTERY_PASS != TRUTH",
            "PINNED_PARENT_COMPATIBILITY != CURRENT_PARENT_COMPATIBILITY",
            "DRIFT_IS_NEVER_SILENTLY_ACCEPTED",
            "VOTE != EVIDENCE",
            "INDEX != CANONICAL_MEMORY",
            "MODEL_STATE != MODEL_MIND",
            "RAW_OBJECT_BYTES = CANONICAL",
        ],
    }
    return {"report_id": "sha256:" + sha256_hex(canonical_bytes(payload)), **payload}


def validate_report(report: dict[str, Any]) -> None:
    _require(report.get("protocol") == PROTOCOL, "composition report protocol mismatch")
    _require(report.get("scope") == "pinned_parent_evidence_only", "composition report scope mismatch")
    _require(report.get("authority") == "conformance-only", "composition report authority mismatch")
    _require(report.get("int_authority_claimed") is False, "CONTROL must not claim INT authority")
    _require(report.get("truth_claimed") is False, "composition report must not claim truth")
    case_results = report.get("case_results")
    _require(isinstance(case_results, list) and len(case_results) == 11, "composition report case count mismatch")
    _require(all(row.get("result") == "pass" for row in case_results), "composition report contains failed cases")
    report_id = report.get("report_id")
    payload = {key: value for key, value in report.items() if key != "report_id"}
    _require(report_id == "sha256:" + sha256_hex(canonical_bytes(payload)), "composition report identity mismatch")


def _load_observed(path: str | None) -> dict[str, Any] | None:
    return None if path is None else load_json(Path(path))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QSOL-CONTROL Phase 9 INT composition batteries")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run deterministic pinned composition batteries")
    run.add_argument("--observed-parents", help="optional current-parent identity observation JSON")
    run.add_argument("--json", action="store_true", help="emit canonical compact JSON")
    validate = sub.add_parser("validate", help="validate pins, case index, and battery result")
    validate.add_argument("--observed-parents", help="optional current-parent identity observation JSON")
    drift = sub.add_parser("check-drift", help="classify supplied current-parent identities against pins")
    drift.add_argument("--observed-parents", required=True)
    drift.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        observed = _load_observed(getattr(args, "observed_parents", None))
        if args.command == "check-drift":
            pins = load_json(PINS_PATH)
            validate_pins(pins)
            result = classify_observed_parents(pins, observed)
            text = canonical_bytes(result).decode("utf-8") if args.json else json.dumps(result, indent=2, sort_keys=True)
            print(text)
            return 2 if result["requires_review"] else 0
        report = run_batteries(observed=observed)
        validate_report(report)
        if args.command == "validate":
            print(json.dumps({"status": "valid", "report_id": report["report_id"], "cases": 11}, sort_keys=True))
            return 0
        print(canonical_bytes(report).decode("utf-8") if args.json else json.dumps(report, indent=2, sort_keys=True))
        return 0
    except CompositionError as exc:
        print(f"INT composition error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
