#!/usr/bin/env python3
"""Local human WebUI runtime for QSOL-CONTROL Phase 5.

The server is deliberately loopback-first, dependency-free, and thin. It exposes
CONTROL-owned storage plus the already-implemented read-only ORACLE adapter and
governance-preserving NEXUS Council adapter. Rendering never upgrades votes,
retrieval scores, lattice coordinates, model metadata, or stored records into
truth/evidence authority.
"""

from __future__ import annotations

import base64
import binascii
import json
import mimetypes
import os
import re
import secrets
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse, urlsplit

from adapters.nexus import NexusAdapterError, NexusCouncilAdapter
from adapters.oracle import OracleAdapter, OracleAdapterError
from storage.control_store import ControlStore, StorageError, canonical_json_bytes
from storage.dna_lattice import (
    DnaLatticeError,
    LEXICOGRAPHIC_TRAVERSAL,
    PHI_GATED_TRAVERSAL,
    encode_projection,
    lexicographic_cells,
)
from storage.interaction_store import InteractionStore
from storage.model_state import ModelStateError, ModelStateRegistry

WEBUI_PROTOCOL = "qsol-control-webui/1"
WEBUI_SESSION_PROTOCOL = "qsol-control-webui-session/1"
WEBUI_HEALTH_PROTOCOL = "qsol-control-webui-health/1"
WEBUI_RUN_VIEW_PROTOCOL = "qsol-control-webui-run-view/1"
WEBUI_LATTICE_PROTOCOL = "qsol-control-webui-lattice-view/1"
WEBUI_RUN_COMPARISON_PROTOCOL = "qsol-control-webui-run-comparison/1"
MAX_JSON_BODY_BYTES = 8 * 1024 * 1024
MAX_UPLOAD_BYTES = 4 * 1024 * 1024
MAX_DNA_EXPORT_BYTES = 4 * 1024 * 1024
MAX_LIST_ITEMS = 10_000
SHA_REF_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
OBJECT_REF_RE = re.compile(r"^object:[0-9a-f]{64}$")
LATTICE_RE = re.compile(r"^L\[[0-2],[0-2],[0-2]\](?:/L\[[0-2],[0-2],[0-2]\])*$")

def _load_model_state_labels() -> dict[str, str]:
    contract_path = Path(__file__).resolve().parents[1] / "ai" / "model-state-contract.json"
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        labels = contract["ui_labels"]
    except (OSError, KeyError, json.JSONDecodeError, TypeError) as exc:
        raise RuntimeError("Phase 4 model-state UI label contract is unavailable") from exc
    required = {
        "panel_title": "Model-state reproducibility metadata",
        "boundary_badge": "Not model mind",
        "provenance_heading": "Metadata provenance",
        "unknown_label": "Unknown / not established",
        "locally_verified_label": "Locally verified",
        "provider_reported_label": "Provider reported",
        "inferred_label": "Inferred — not verified",
        "observed_label": "Observed",
    }
    for key, expected in required.items():
        if labels.get(key) != expected:
            raise RuntimeError(f"Phase 4 model-state UI label contract drifted at {key}")
    return {
        "panel_title": labels["panel_title"],
        "boundary_badge": labels["boundary_badge"],
        "provenance_heading": labels["provenance_heading"],
        "unknown": labels["unknown_label"],
        "locally_verified": labels["locally_verified_label"],
        "provider_reported": labels["provider_reported_label"],
        "inferred": labels["inferred_label"],
        "observed": labels["observed_label"],
    }


MODEL_STATE_LABELS = _load_model_state_labels()
UI_INVARIANTS = (
    "MODEL_STATE != MODEL_MIND",
    "VISIBLE_OUTPUT != HIDDEN_CHAIN_OF_THOUGHT",
    "RUNTIME_METADATA != CONSCIOUSNESS",
    "PROVIDER_REPORTED != LOCALLY_VERIFIED",
    "MODEL_STATE_COMPARISON != MIND_COMPARISON",
    "VOTE != EVIDENCE",
    "CONSENSUS != TRUTH",
    "SEARCH_SCORE != TRUTH",
    "SEMANTIC_SIMILARITY != EVIDENCE_STRENGTH",
    "LATTICE_ADDRESS != TRUTH",
    "CODON_FREQUENCY != EVIDENCE",
)
FORBIDDEN_TRUTH_UI_FIELDS = {
    "truth_score",
    "truth_percentage",
    "probability_true",
    "verified_by_consensus",
}


class WebUIError(StorageError):
    """Raised for bounded local WebUI request/contract failures."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_string(
    value: Any, field: str, *, maximum: int = 4096, allow_empty: bool = False
) -> str:
    if not isinstance(value, str):
        raise WebUIError(f"{field} must be a string")
    if not allow_empty and not value.strip():
        raise WebUIError(f"{field} must be non-empty")
    if len(value) > maximum:
        raise WebUIError(f"{field} exceeds {maximum} characters")
    return value


def _require_sha_ref(value: Any, field: str) -> str:
    if not isinstance(value, str) or SHA_REF_RE.fullmatch(value) is None:
        raise WebUIError(f"{field} must be a sha256: reference")
    return value


def _canonical_strings(values: Any, field: str, *, maximum: int = 1000) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list) or len(values) > maximum:
        raise WebUIError(f"{field} must be a bounded array")
    if any(not isinstance(item, str) or not item for item in values):
        raise WebUIError(f"{field} must contain non-empty strings")
    if len(values) != len(set(values)):
        raise WebUIError(f"{field} must not contain duplicates")
    return sorted(values, key=lambda item: item.encode("utf-8"))


def _reject_truth_fields(value: Any) -> None:
    """Fail closed if browser input attempts to smuggle synthetic truth UI fields."""

    stack = [value]
    visited = 0
    while stack:
        current = stack.pop()
        visited += 1
        if visited > 100_000:
            raise WebUIError("request exceeds bounded UI validation depth")
        if isinstance(current, dict):
            for key, item in current.items():
                if not isinstance(key, str):
                    raise WebUIError("request object keys must be strings")
                normalized = re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")
                if normalized in FORBIDDEN_TRUTH_UI_FIELDS:
                    raise WebUIError(
                        f"synthetic truth field {key!r} is forbidden by the UI invariant"
                    )
                stack.append(item)
        elif isinstance(current, list):
            stack.extend(current)


@dataclass(frozen=True)
class WebUIConfig:
    control_root: Path
    oracle_root: Path | None = None
    nexus_command: tuple[str, ...] | None = None
    nexus_cwd: Path | None = None
    nexus_timeout_seconds: float = 1800.0
    default_council_members: tuple[dict[str, Any], ...] = ()
    bind: str = "127.0.0.1"
    port: int = 8765

    def __post_init__(self) -> None:
        if self.port < 0 or self.port > 65535:
            raise WebUIError("port must be 0..65535")
        if self.nexus_timeout_seconds <= 0:
            raise WebUIError("nexus timeout must be positive")
