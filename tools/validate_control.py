#!/usr/bin/env python3
"""Dependency-free structural validator for QSOL-CONTROL bootstrap contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


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


def validate() -> dict[str, Any]:
    manifest = load_json(ROOT / "manifest.json")
    if manifest.get("protocol") != "QSOL-CONTROL/0.1":
        raise ValueError("manifest protocol mismatch")
    if manifest.get("semantic_authority") != "none":
        raise ValueError("CONTROL must not claim semantic authority")

    require_file(manifest["machine_entrypoint"])
    require_file(manifest["constitution"])
    require_file(manifest["lattice_contract"])
    require_file(manifest["architecture"])
    require_file(manifest["roadmap"])
    require_file(manifest["security"])

    for path in manifest.get("documentation", []):
        require_file(path)
    for path in manifest.get("schemas", {}).values():
        require_file(path)
        load_json(ROOT / path)

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
        "lattice_cells": lattice["top_level_cell_count"],
    }


def main() -> int:
    report = validate()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
