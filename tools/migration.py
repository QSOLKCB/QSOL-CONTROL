#!/usr/bin/env python3
"""Versioned, fail-closed migration planning for QSOL-CONTROL Phase 10.

The tool plans declared contract-version transitions and emits a deterministic receipt.
It does not rewrite a CONTROL store in place and does not reinterpret canonical state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "ai" / "migration-policy.json"
PROTOCOL = "qsol-control-migration-receipt/1"
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


class MigrationError(ValueError):
    """Raised when a requested migration is undeclared or unsafe."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_ref(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def parse_semver(value: Any) -> tuple[int, int, int]:
    if not isinstance(value, str):
        raise MigrationError("contract version must be a semantic-version string")
    match = SEMVER.fullmatch(value)
    if match is None:
        raise MigrationError(f"invalid semantic version: {value!r}")
    return tuple(int(part) for part in match.groups())


def load_policy() -> dict[str, Any]:
    try:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MigrationError("cannot load migration policy") from exc
    if not isinstance(policy, dict):
        raise MigrationError("migration policy root must be an object")
    return policy


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("protocol") != "qsol-control-migration/1":
        raise MigrationError("migration policy protocol mismatch")
    current = policy.get("current_contract_version")
    current_tuple = parse_semver(current)
    if current_tuple[0] != 2:
        raise MigrationError("Phase 10 migration policy must target CONTROL contract major 2")
    supported = policy.get("supported_source_versions")
    if not isinstance(supported, list) or not supported:
        raise MigrationError("supported_source_versions must be a non-empty array")
    if len(supported) != len(set(supported)):
        raise MigrationError("supported_source_versions must be unique")
    parsed_supported = [parse_semver(value) for value in supported]
    if parsed_supported != sorted(parsed_supported):
        raise MigrationError("supported_source_versions must be sorted")
    if current not in supported:
        raise MigrationError("current contract version must be a supported source version")
    rules = policy.get("rules")
    if not isinstance(rules, dict):
        raise MigrationError("migration rules are missing")
    if rules.get("in_place_rewrite") is not False or rules.get("source_preserved") is not True:
        raise MigrationError("migration policy must preserve source and forbid in-place rewrite")
    steps = policy.get("steps")
    if not isinstance(steps, list):
        raise MigrationError("migration steps must be an array")
    seen: set[tuple[str, str]] = set()
    for row in steps:
        if not isinstance(row, dict):
            raise MigrationError("migration step must be an object")
        source = row.get("from")
        target = row.get("to")
        source_tuple = parse_semver(source)
        target_tuple = parse_semver(target)
        if source_tuple >= target_tuple:
            raise MigrationError("migration step must move forward")
        if source not in supported or target not in supported:
            raise MigrationError("migration step references unsupported version")
        if row.get("canonical_store_rewrite_required") is not False:
            raise MigrationError("declared Phase 10 steps must not rewrite canonical store state")
        key = (source, target)
        if key in seen:
            raise MigrationError("duplicate migration step")
        seen.add(key)


def _step_map(policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["from"]: row for row in policy["steps"]}


def plan_migration(source: str, target: str | None = None) -> dict[str, Any]:
    policy = load_policy()
    validate_policy(policy)
    target = target or policy["current_contract_version"]
    source_tuple = parse_semver(source)
    target_tuple = parse_semver(target)
    if source_tuple[0] != target_tuple[0]:
        raise MigrationError("unknown/breaking contract major requires manual review; automatic migration rejected")
    if source_tuple > target_tuple:
        raise MigrationError("downgrade migration is forbidden")
    supported = set(policy["supported_source_versions"])
    if source not in supported or target not in supported:
        raise MigrationError("source/target version is not declared by the migration policy")

    steps: list[dict[str, Any]] = []
    current = source
    step_map = _step_map(policy)
    while current != target:
        row = step_map.get(current)
        if row is None:
            raise MigrationError(f"no declared migration step from {current}")
        if parse_semver(row["to"]) > target_tuple:
            raise MigrationError("declared migration chain overshoots requested target")
        steps.append(row)
        current = row["to"]
        if len(steps) > len(policy["steps"]):
            raise MigrationError("migration step cycle detected")

    payload = {
        "type": "qsol-control-migration-receipt",
        "protocol": PROTOCOL,
        "source_contract_version": source,
        "target_contract_version": target,
        "status": "no_op" if not steps else "planned",
        "steps": steps,
        "source_preserved": True,
        "in_place_rewrite": False,
        "canonical_store_rewrite_required": any(
            row["canonical_store_rewrite_required"] for row in steps
        ),
        "authority": "integrity-and-procedure-only",
        "semantic_authority_claimed": False,
        "boundaries": policy["boundaries"],
    }
    return {"receipt_id": sha256_ref(canonical_json_bytes(payload)), **payload}


def validate_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("protocol") != PROTOCOL:
        raise MigrationError("migration receipt protocol mismatch")
    if receipt.get("source_preserved") is not True or receipt.get("in_place_rewrite") is not False:
        raise MigrationError("migration receipt violates source-preservation boundary")
    if receipt.get("semantic_authority_claimed") is not False:
        raise MigrationError("migration receipt cannot claim semantic authority")
    if receipt.get("canonical_store_rewrite_required") is not False:
        raise MigrationError("Phase 10 migration receipt unexpectedly requires canonical rewrite")
    payload = {key: value for key, value in receipt.items() if key != "receipt_id"}
    if receipt.get("receipt_id") != sha256_ref(canonical_json_bytes(payload)):
        raise MigrationError("migration receipt identity mismatch")
    expected = plan_migration(
        receipt.get("source_contract_version"), receipt.get("target_contract_version")
    )
    if expected != receipt:
        raise MigrationError("migration receipt does not match declared policy")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QSOL-CONTROL versioned migration policy")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate the committed migration policy")
    plan = sub.add_parser("plan", help="emit a deterministic migration receipt")
    plan.add_argument("--from-version", required=True)
    plan.add_argument("--to-version")
    plan.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            policy = load_policy()
            validate_policy(policy)
            print(json.dumps({"status": "valid", "current_contract_version": policy["current_contract_version"]}, sort_keys=True))
            return 0
        receipt = plan_migration(args.from_version, args.to_version)
        validate_receipt(receipt)
        print(
            canonical_json_bytes(receipt).decode("utf-8")
            if args.json
            else json.dumps(receipt, indent=2, sort_keys=True)
        )
        return 0
    except MigrationError as exc:
        print(f"migration error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
