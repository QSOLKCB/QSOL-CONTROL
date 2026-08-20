#!/usr/bin/env python3
"""Validate QSOL-CONTROL post-roadmap extension contracts without changing core state."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ExtensionValidationError(ValueError):
    pass


def load(relative: str):
    path = ROOT / relative
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ExtensionValidationError(f"{relative} must be an object")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ExtensionValidationError(message)


def validate() -> dict:
    core = load("manifest.json")
    ext = load("extensions/manifest.json")
    remote = load("ai/remote-gateway-contract.json")
    mobile = load("ai/mobile-client-contract.json")
    consensus = load("ai/consensus-adapter-contract.json")
    nongoals = load("ai/permanent-nongoals.json")

    require(core.get("schema_version") == "2.6.0", "post-roadmap extensions must remain bound to core 2.6.0")
    require(core.get("status", {}).get("completed_through_roadmap_phase") == 10, "core roadmap completion drifted")
    require(ext.get("protocol") == "qsol-control-post-roadmap-extensions/1", "extension manifest protocol mismatch")
    require(ext.get("core_contract_version") == "2.6.0", "extension/core contract binding mismatch")
    require(ext.get("authority") == "none", "extension manifest must have no semantic authority")

    require(remote.get("transport", {}).get("client_supplied_caller_identity") is False, "remote callers must not self-assert caller identity")
    require(remote.get("network", {}).get("non_loopback_requires_tls") is True, "remote non-loopback gateway must require TLS")
    require(remote.get("epistemic_privilege_added") is False, "remote transport must not add epistemic privilege")

    require(mobile.get("client_reimplements_control_runtime") is False, "mobile client must remain thin")
    require(mobile.get("truth_scoring_ui") is False, "mobile client must not add truth scoring")
    require(mobile.get("hidden_chain_of_thought_ui") is False, "mobile client must not expose hidden reasoning")

    require(consensus.get("consensus_algorithm_implemented_by_control") is False, "CONTROL must not silently embed a consensus algorithm")
    require(consensus.get("control_storage_mutated_by_adapter") is False, "consensus adapter must not mutate CONTROL storage")
    require(consensus.get("semantic_authority_claimed") is False, "consensus receipt must not claim semantic authority")

    expected_nongoals = {
        "automatic_truth_scoring",
        "hidden_chain_of_thought_capture",
        "literal_geometric_cognition_claims",
        "biological_claims_from_dna_codec",
        "phi_traversal_physical_optimality_claims",
    }
    require(set(nongoals.get("items", {})) == expected_nongoals, "permanent non-goal set mismatch")
    for name, row in nongoals["items"].items():
        require(row.get("implemented") is False and row.get("forbidden") is True, f"permanent non-goal weakened: {name}")

    required_files = [
        "api/remote_http.py",
        "tools/remote_gateway.py",
        "adapters/consensus.py",
        "tools/consensus_adapter.py",
        "mobile/ios/QSOLControl/ControlClient.swift",
        "mobile/android/app/src/main/java/org/qsol/control/ControlClient.kt",
        "docs/POST-ROADMAP-EXTENSIONS.md",
    ]
    for relative in required_files:
        require((ROOT / relative).is_file(), f"extension file missing: {relative}")

    return {
        "status": "valid",
        "protocol": ext["protocol"],
        "core_contract_version": ext["core_contract_version"],
        "extension_count": len(ext["extensions"]),
        "permanent_nongoal_count": len(nongoals["items"]),
    }


def main() -> int:
    try:
        result = validate()
    except (ExtensionValidationError, OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"extension validation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
