#!/usr/bin/env python3
"""Content-addressed Phase 7 replay records and deterministic comparison reports."""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from storage.control_store import StorageError, canonical_json_bytes, sha256_ref
from storage.interaction_store import InteractionStore

REPLAY_RECORD_PROTOCOL = "qsol-control-replay-record/1"
REPLAY_REPORT_PROTOCOL = "qsol-control-replay-report/1"
REPLAY_BASIS_PROTOCOL = "qsol-control-replay-basis/1"
REPLAY_LINK_PROTOCOL = "qsol-control-replay-link/1"
RESEARCH_TIMELINE_PROTOCOL = "qsol-control-research-timeline/1"
SHA_REF_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
MAX_REPLAY_RECORD_BYTES = 8 * 1024 * 1024
MAX_REPLAY_RECORDS = 100_000
MODEL_STATE_BOUNDARY = "MODEL_STATE != MODEL_MIND"

REPORT_KEYS = {
    "report_id", "protocol", "original_run_id", "replay_run_id",
    "classification_id", "classification", "original_result", "evidence",
    "collection", "retrieval_index", "council", "model_state",
    "configuration", "run_fields", "comparison_is_truth",
    "model_state_comparison_is_mind_comparison", "authority",
}
REPLAY_KEYS = {
    "replay_id", "protocol", "original_run_id", "replay_run_id", "report_id",
    "executed_at", "requested_by_kind", "classification", "classification_id",
    "changed_configuration_authorized", "original_result_immutable",
    "exact_collection_snapshot_preserved", "current_evidence_rerun",
    "exact_replay_claimed", "hidden_chain_of_thought_captured", "authority",
}


class ReplayError(StorageError):
    """Raised when replay records, reports, or longitudinal views are invalid."""


def _validate_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA_REF_RE.fullmatch(value) is None:
        raise ReplayError(f"{label} must be a sha256: reference")
    return value


def _validate_timestamp(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReplayError(f"{label} must be a non-empty ISO-8601 timestamp")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ReplayError(f"{label} must be valid ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ReplayError(f"{label} must include an explicit UTC offset")
    return value


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ReplayError(f"{label} must be an array of strings")
    if len(value) != len(set(value)):
        raise ReplayError(f"{label} must not contain duplicates")
    return value


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temp_path = Path(handle.name)
        if os.name != "nt":
            os.fchmod(handle.fileno(), 0o600)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temp_path, path)
        if os.name != "nt":
            os.chmod(path, 0o600, follow_symlinks=False)
    finally:
        temp_path.unlink(missing_ok=True)


def _read(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ReplayError("replay records must not be symbolic links")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ReplayError("replay record is unavailable") from exc
    if size > MAX_REPLAY_RECORD_BYTES:
        raise ReplayError("replay record exceeds canonical byte limit")
    try:
        encoded = path.read_bytes()
    except OSError as exc:
        raise ReplayError("replay record is unavailable") from exc
    try:
        value = json.loads(encoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ReplayError("replay record is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ReplayError("replay record must contain an object")
    if canonical_json_bytes(value) != encoded:
        raise ReplayError("replay record bytes are not canonical JSON")
    return value


class ReplayStore:
    """Immutable local replay metadata. Original run/event records are never rewritten."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.records = self.root / "records" / "replays"
        self.reports = self.root / "records" / "replay-reports"
        self.records.mkdir(parents=True, exist_ok=True)
        self.reports.mkdir(parents=True, exist_ok=True)
        self.interactions = InteractionStore(self.root)

    @staticmethod
    def _identity(payload: dict[str, Any]) -> str:
        return sha256_ref(canonical_json_bytes(payload))

    @staticmethod
    def _path(directory: Path, ref: str) -> Path:
        _validate_sha(ref, "content identity")
        return directory / f"{ref.removeprefix('sha256:')}.json"

    def _require_run(self, run_id: str, label: str) -> None:
        _validate_sha(run_id, label)
        try:
            self.interactions.get_run(run_id)
        except (StorageError, OSError, ValueError) as exc:
            raise ReplayError(f"{label} references an unavailable CONTROL run") from exc

    @staticmethod
    def _validate_evidence_lane(value: Any) -> None:
        required = {
            "original_state", "current_replay_state", "added_refs", "removed_refs",
            "unchanged_refs", "current_evidence_is_original_evidence",
        }
        if not isinstance(value, dict) or set(value) != required:
            raise ReplayError("replay report evidence lane is invalid")
        if value["original_state"] not in {"known", "conflict", "unknown", "unavailable"}:
            raise ReplayError("replay report original evidence state is invalid")
        if value["current_replay_state"] not in {"known", "conflict", "unknown", "unavailable"}:
            raise ReplayError("replay report current evidence state is invalid")
        for key in ("added_refs", "removed_refs", "unchanged_refs"):
            _string_list(value[key], f"evidence.{key}")
        if value["current_evidence_is_original_evidence"] is not False:
            raise ReplayError("current evidence must not be relabelled as original evidence")

    @staticmethod
    def _validate_collection_lane(value: Any) -> None:
        if not isinstance(value, dict) or type(value.get("applicable")) is not bool:
            raise ReplayError("replay report collection lane is invalid")
        if value.get("replay_bound_to_original_snapshot") is not True:
            raise ReplayError("replay must remain bound to the original Collection snapshot")
        for key in ("added_since_original", "removed_since_original"):
            _string_list(value.get(key), f"collection.{key}")
        if value["applicable"]:
            _validate_sha(value.get("collection_id"), "collection.collection_id")
            _validate_sha(value.get("original_snapshot_id"), "collection.original_snapshot_id")
            _validate_sha(value.get("current_head_snapshot_id"), "collection.current_head_snapshot_id")
        else:
            if value.get("original_snapshot_id") is not None or value.get("current_head_snapshot_id") is not None:
                raise ReplayError("non-applicable collection comparison must not invent snapshots")

    @staticmethod
    def _validate_index_lane(value: Any) -> None:
        required = {"original", "replay", "same_recorded_basis", "legacy_original_basis_incomplete"}
        if not isinstance(value, dict) or set(value) != required:
            raise ReplayError("replay report retrieval_index lane is invalid")
        if not isinstance(value["original"], dict) or not isinstance(value["replay"], dict):
            raise ReplayError("replay report retrieval index descriptors must be objects")
        if type(value["same_recorded_basis"]) is not bool or type(value["legacy_original_basis_incomplete"]) is not bool:
            raise ReplayError("replay report retrieval index flags must be boolean")

    @staticmethod
    def _validate_roster_diff(value: Any) -> None:
        if not isinstance(value, dict) or set(value) != {"added", "removed", "changed", "same"}:
            raise ReplayError("replay report Council roster diff is invalid")
        if not all(isinstance(value[key], list) for key in ("added", "removed", "changed")):
            raise ReplayError("replay report Council roster arrays are invalid")
        if type(value["same"]) is not bool:
            raise ReplayError("replay report Council roster same flag is invalid")

    @classmethod
    def _validate_council_lane(cls, value: Any) -> None:
        required = {
            "roster", "request_member_descriptors", "original_runtime", "replay_runtime",
            "original_consensus", "replay_consensus", "consensus_is_truth",
        }
        if not isinstance(value, dict) or set(value) != required:
            raise ReplayError("replay report Council lane is invalid")
        cls._validate_roster_diff(value["roster"])
        descriptors = value["request_member_descriptors"]
        if not isinstance(descriptors, dict) or set(descriptors) != {
            "original", "replay", "original_complete", "replay_complete"
        }:
            raise ReplayError("replay report Council request descriptors are invalid")
        if not isinstance(descriptors["original"], list) or not isinstance(descriptors["replay"], list):
            raise ReplayError("replay report Council descriptors must be arrays")
        if type(descriptors["original_complete"]) is not bool or type(descriptors["replay_complete"]) is not bool:
            raise ReplayError("replay report Council descriptor completeness flags are invalid")
        for key in ("original_runtime", "replay_runtime"):
            runtime = value[key]
            if not isinstance(runtime, dict) or set(runtime) != {"protocol", "version"}:
                raise ReplayError("replay report Council runtime descriptor is invalid")
        for key in ("original_consensus", "replay_consensus"):
            if value[key] is not None and not isinstance(value[key], dict):
                raise ReplayError("replay report Council consensus snapshot is invalid")
        if value["consensus_is_truth"] is not False:
            raise ReplayError("Council consensus must not be promoted to truth")

    @staticmethod
    def _validate_model_state_comparison(value: Any, original_run_id: str, replay_run_id: str) -> None:
        required = {
            "comparison_id", "protocol", "left_run_id", "right_run_id", "aligned",
            "left_only", "right_only", "epistemic_boundary", "model_mind_inference", "authority",
        }
        if not isinstance(value, dict) or set(value) != required:
            raise ReplayError("replay report model_state lane is invalid")
        _validate_sha(value["comparison_id"], "model_state.comparison_id")
        if value["protocol"] != "qsol-control-model-state-run-comparison/1":
            raise ReplayError("replay report model_state protocol is invalid")
        if value["left_run_id"] != original_run_id or value["right_run_id"] != replay_run_id:
            raise ReplayError("replay report model_state run binding is invalid")
        if value["epistemic_boundary"] != MODEL_STATE_BOUNDARY:
            raise ReplayError("replay report model_state epistemic boundary is invalid")
        if value["model_mind_inference"] is not False:
            raise ReplayError("replay model-state comparison must not infer model mind")
        if value["authority"] != "metadata-comparison-only":
            raise ReplayError("replay model-state comparison authority is invalid")
        if not all(isinstance(value[key], list) for key in ("aligned", "left_only", "right_only")):
            raise ReplayError("replay report model_state comparison arrays are invalid")
        for row in value["aligned"]:
            if not isinstance(row, dict) or set(row) != {"key", "comparison"}:
                raise ReplayError("replay report aligned model-state row is invalid")
            comparison = row["comparison"]
            if not isinstance(comparison, dict):
                raise ReplayError("replay report nested model-state comparison is invalid")
            if comparison.get("epistemic_boundary") != MODEL_STATE_BOUNDARY:
                raise ReplayError("nested model-state comparison lost epistemic boundary")
            if comparison.get("model_mind_inference") is not False:
                raise ReplayError("nested model-state comparison must not infer model mind")
            if comparison.get("authority") != "metadata-comparison-only":
                raise ReplayError("nested model-state comparison authority is invalid")

    @staticmethod
    def _validate_configuration_lane(value: Any) -> None:
        if not isinstance(value, dict) or set(value) != {"changes", "original", "replay"}:
            raise ReplayError("replay report configuration lane is invalid")
        if not isinstance(value["changes"], list) or not isinstance(value["original"], dict) or not isinstance(value["replay"], dict):
            raise ReplayError("replay report configuration lane structure is invalid")

    @staticmethod
    def _validate_run_fields(value: Any) -> None:
        expected = {"question_sha256_same", "mode_same", "file_ids_same", "collection_ref_same"}
        if not isinstance(value, dict) or set(value) != expected:
            raise ReplayError("replay report run_fields lane is invalid")
        if any(type(value[key]) is not bool for key in expected):
            raise ReplayError("replay report run_fields values must be boolean")

    def _validate_report(self, record: dict[str, Any]) -> None:
        if set(record) != REPORT_KEYS:
            raise ReplayError("replay report fields do not match qsol-control-replay-report/1")
        if record.get("protocol") != REPLAY_REPORT_PROTOCOL:
            raise ReplayError("replay report protocol mismatch")
        report_id = _validate_sha(record.get("report_id"), "report_id")
        original_run_id = _validate_sha(record.get("original_run_id"), "original_run_id")
        replay_run_id = _validate_sha(record.get("replay_run_id"), "replay_run_id")
        if original_run_id == replay_run_id:
            raise ReplayError("replay report must reference a distinct replay run")
        _validate_sha(record.get("classification_id"), "classification_id")
        classification = record.get("classification")
        if not isinstance(classification, str) or not classification or len(classification) > 128:
            raise ReplayError("replay report classification is invalid")
        original = record.get("original_result")
        if not isinstance(original, dict) or set(original) != {
            "immutable", "fingerprint_before", "fingerprint_after", "run_id_unchanged"
        }:
            raise ReplayError("replay report original_result is invalid")
        before = _validate_sha(original.get("fingerprint_before"), "fingerprint_before")
        after = _validate_sha(original.get("fingerprint_after"), "fingerprint_after")
        if original.get("immutable") is not True or original.get("run_id_unchanged") is not True:
            raise ReplayError("replay report must preserve the original result immutably")
        if before != after:
            raise ReplayError("replay report immutability fingerprints disagree")
        self._validate_evidence_lane(record["evidence"])
        self._validate_collection_lane(record["collection"])
        self._validate_index_lane(record["retrieval_index"])
        self._validate_council_lane(record["council"])
        self._validate_model_state_comparison(record["model_state"], original_run_id, replay_run_id)
        self._validate_configuration_lane(record["configuration"])
        self._validate_run_fields(record["run_fields"])
        if record.get("comparison_is_truth") is not False:
            raise ReplayError("replay comparison must not claim truth")
        if record.get("model_state_comparison_is_mind_comparison") is not False:
            raise ReplayError("replay model-state comparison must not claim mind comparison")
        if record.get("authority") != "comparison-only":
            raise ReplayError("replay report authority must remain comparison-only")
        payload = {key: value for key, value in record.items() if key != "report_id"}
        if self._identity(payload) != report_id:
            raise ReplayError("replay report content identity mismatch")
        self._require_run(original_run_id, "original_run_id")
        self._require_run(replay_run_id, "replay_run_id")

    def _validate_replay(self, record: dict[str, Any], report: dict[str, Any]) -> None:
        if set(record) != REPLAY_KEYS:
            raise ReplayError("replay record fields do not match qsol-control-replay-record/1")
        if record.get("protocol") != REPLAY_RECORD_PROTOCOL:
            raise ReplayError("replay protocol mismatch")
        replay_id = _validate_sha(record.get("replay_id"), "replay_id")
        original_run_id = _validate_sha(record.get("original_run_id"), "original_run_id")
        replay_run_id = _validate_sha(record.get("replay_run_id"), "replay_run_id")
        if original_run_id == replay_run_id:
            raise ReplayError("replay record must reference a distinct replay run")
        report_id = _validate_sha(record.get("report_id"), "report_id")
        classification_id = _validate_sha(record.get("classification_id"), "classification_id")
        _validate_timestamp(record.get("executed_at"), "executed_at")
        if record.get("requested_by_kind") not in {"human", "ai", "system"}:
            raise ReplayError("replay requested_by_kind is invalid")
        classification = record.get("classification")
        if not isinstance(classification, str) or not classification or len(classification) > 128:
            raise ReplayError("replay classification is invalid")
        for field in ("changed_configuration_authorized", "exact_collection_snapshot_preserved"):
            if type(record.get(field)) is not bool:
                raise ReplayError(f"replay {field} must be boolean")
        if record.get("original_result_immutable") is not True:
            raise ReplayError("replay must preserve original_result_immutable=true")
        if record.get("current_evidence_rerun") is not True:
            raise ReplayError("replay must preserve current_evidence_rerun=true")
        if record.get("exact_replay_claimed") is not False:
            raise ReplayError("replay must never claim exact replay")
        if record.get("hidden_chain_of_thought_captured") is not False:
            raise ReplayError("replay must never claim hidden chain-of-thought capture")
        if record.get("authority") != "orchestration-and-comparison-only":
            raise ReplayError("replay authority must remain orchestration-and-comparison-only")
        payload = {key: value for key, value in record.items() if key != "replay_id"}
        if self._identity(payload) != replay_id:
            raise ReplayError("replay content identity mismatch")
        self._require_run(original_run_id, "original_run_id")
        self._require_run(replay_run_id, "replay_run_id")
        if report.get("report_id") != report_id:
            raise ReplayError("replay/report report_id mismatch")
        if report.get("original_run_id") != original_run_id:
            raise ReplayError("replay/report original_run_id mismatch")
        if report.get("replay_run_id") != replay_run_id:
            raise ReplayError("replay/report replay_run_id mismatch")
        if report.get("classification_id") != classification_id:
            raise ReplayError("replay/report classification_id mismatch")
        if report.get("classification") != classification:
            raise ReplayError("replay/report classification mismatch")
        if report.get("original_result", {}).get("immutable") is not True:
            raise ReplayError("replay/report original immutability mismatch")

    def write_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ReplayError("replay report payload must be an object")
        report_id = self._identity(payload)
        record = {"report_id": report_id, **payload}
        self._validate_report(record)
        path = self._path(self.reports, report_id)
        encoded = canonical_json_bytes(record)
        if len(encoded) > MAX_REPLAY_RECORD_BYTES:
            raise ReplayError("replay report exceeds canonical byte limit")
        if path.exists():
            if path.read_bytes() != encoded:
                raise ReplayError("replay report identity collision detected")
        else:
            _atomic_write(path, encoded)
        return record

    def write_replay(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ReplayError("replay payload must be an object")
        replay_id = self._identity(payload)
        record = {"replay_id": replay_id, **payload}
        report_id = _validate_sha(record.get("report_id"), "report_id")
        report = self.get_report(report_id)
        self._validate_replay(record, report)
        path = self._path(self.records, replay_id)
        encoded = canonical_json_bytes(record)
        if len(encoded) > MAX_REPLAY_RECORD_BYTES:
            raise ReplayError("replay record exceeds canonical byte limit")
        if path.exists():
            if path.read_bytes() != encoded:
                raise ReplayError("replay record identity collision detected")
        else:
            _atomic_write(path, encoded)
        return record

    def get_report(self, report_id: str) -> dict[str, Any]:
        path = self._path(self.reports, report_id)
        if not path.is_file():
            raise ReplayError(f"unknown replay report: {report_id}")
        record = _read(path)
        if record.get("report_id") != report_id:
            raise ReplayError("replay report path/content identity mismatch")
        self._validate_report(record)
        return record

    def get_replay(self, replay_id: str) -> dict[str, Any]:
        path = self._path(self.records, replay_id)
        if not path.is_file():
            raise ReplayError(f"unknown replay: {replay_id}")
        record = _read(path)
        if record.get("replay_id") != replay_id:
            raise ReplayError("replay path/content identity mismatch")
        report = self.get_report(_validate_sha(record.get("report_id"), "report_id"))
        self._validate_replay(record, report)
        return {**record, "report": report}

    def list_replays(self, *, original_run_id: str | None = None) -> list[dict[str, Any]]:
        if original_run_id is not None:
            _validate_sha(original_run_id, "original_run_id")
        paths = sorted(self.records.glob("*.json"), key=lambda path: path.name.encode("ascii"))
        if len(paths) > MAX_REPLAY_RECORDS:
            raise ReplayError("replay registry exceeds scan limit")
        output = []
        for path in paths:
            if re.fullmatch(r"[0-9a-f]{64}\.json", path.name) is None:
                raise ReplayError("replay registry contains malformed filename")
            record = self.get_replay("sha256:" + path.stem)
            record = {key: value for key, value in record.items() if key != "report"}
            if original_run_id is None or record["original_run_id"] == original_run_id:
                output.append(record)
        output.sort(key=lambda row: (row["executed_at"], row["replay_id"]))
        return output


__all__ = [
    "REPLAY_BASIS_PROTOCOL", "REPLAY_LINK_PROTOCOL", "REPLAY_RECORD_PROTOCOL",
    "REPLAY_REPORT_PROTOCOL", "RESEARCH_TIMELINE_PROTOCOL", "ReplayError", "ReplayStore",
]
