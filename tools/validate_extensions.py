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
    bootstrap = load("README4AI.md")
    ext = load("extensions/manifest.json")
    remote = load("ai/remote-gateway-contract.json")
    mobile = load("ai/mobile-client-contract.json")
    consensus = load("ai/consensus-adapter-contract.json")
    nongoals = load("ai/permanent-nongoals.json")

    require(core.get("schema_version") == "2.6.0", "post-roadmap extensions must remain bound to core 2.6.0")
    require(core.get("status", {}).get("completed_through_roadmap_phase") == 10, "core roadmap completion drifted")
    require("extensions/manifest.json" in core.get("documentation", []), "core manifest must make extension registry discoverable")
    require(bootstrap.get("optional_extension_entrypoint") == "extensions/manifest.json", "AI bootstrap must point to extension registry")
    require(ext.get("protocol") == "qsol-control-post-roadmap-extensions/1", "extension manifest protocol mismatch")
    require(ext.get("schema_version") == "1.2.0", "extension manifest hardening version mismatch")
    require(ext.get("core_contract_version") == "2.6.0", "extension/core contract binding mismatch")
    require(ext.get("authority") == "none", "extension manifest must have no semantic authority")

    require(remote.get("schema_version") == "1.2.0", "remote gateway hardening contract version mismatch")
    require(remote.get("transport", {}).get("client_supplied_caller_identity") is False, "remote callers must not self-assert caller identity")
    require(remote.get("network", {}).get("non_loopback_requires_tls") is True, "remote non-loopback gateway must require TLS")
    require(remote.get("network", {}).get("programmatic_server_factory_revalidates_policy") is True, "remote server factory must revalidate network policy")
    require(remote.get("authorization", {}).get("record_level_acl_required") is True, "remote gateway must enforce record ACLs")
    require(remote.get("audit", {}).get("principal_id_recorded") is True, "remote gateway must persist authenticated principal identity")
    require(remote.get("audit", {}).get("credential_material_captured") is False, "remote audit must not capture bearer material")
    require(remote.get("availability", {}).get("quota_window_seconds") == 60, "remote gateway quota window drifted")
    require(remote.get("availability", {}).get("maximum_concurrent_connections") == 64, "remote connection bound drifted")
    require(remote.get("epistemic_privilege_added") is False, "remote transport must not add epistemic privilege")

    require(mobile.get("client_reimplements_control_runtime") is False, "mobile client must remain thin")
    require(mobile.get("truth_scoring_ui") is False, "mobile client must not add truth scoring")
    require(mobile.get("hidden_chain_of_thought_ui") is False, "mobile client must not expose hidden reasoning")

    require(consensus.get("schema_version") == "1.2.0", "consensus hardening contract version mismatch")
    require(consensus.get("consensus_algorithm_implemented_by_control") is False, "CONTROL must not silently embed a consensus algorithm")
    require(consensus.get("supplied_intents_fully_revalidated_before_provider") is True, "consensus adapter must revalidate supplied intents")
    require(consensus.get("provider_output_bounded_while_running") if "provider_output_bounded_while_running" in consensus else consensus.get("provider_stdout_bounded_while_running_bytes") == 4194304, "consensus provider output must be bounded while running")
    require(consensus.get("provider_terminated_on_output_overflow") is True, "consensus provider must terminate on output overflow")
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
