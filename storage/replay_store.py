#!/usr/bin/env python3
"""Content-addressed Phase 7 replay records and deterministic comparison reports."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from storage.control_store import StorageError, canonical_json_bytes, sha256_ref

REPLAY_RECORD_PROTOCOL = "qsol-control-replay-record/1"
REPLAY_REPORT_PROTOCOL = "qsol-control-replay-report/1"
REPLAY_BASIS_PROTOCOL = "qsol-control-replay-basis/1"
REPLAY_LINK_PROTOCOL = "qsol-control-replay-link/1"
RESEARCH_TIMELINE_PROTOCOL = "qsol-control-research-timeline/1"
SHA_REF_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
MAX_REPLAY_RECORD_BYTES = 8 * 1024 * 1024
MAX_REPLAY_RECORDS = 100_000


class ReplayError(StorageError):
    """Raised when replay records, reports, or longitudinal views are invalid."""


def _validate_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA_REF_RE.fullmatch(value) is None:
        raise ReplayError(f"{label} must be a sha256: reference")
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
        encoded = path.read_bytes()
    except OSError as exc:
        raise ReplayError("replay record is unavailable") from exc
    if len(encoded) > MAX_REPLAY_RECORD_BYTES:
        raise ReplayError("replay record exceeds canonical byte limit")
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

    @staticmethod
    def _identity(payload: dict[str, Any]) -> str:
        return sha256_ref(canonical_json_bytes(payload))

    @staticmethod
    def _path(directory: Path, ref: str) -> Path:
        _validate_sha(ref, "content identity")
        return directory / f"{ref.removeprefix('sha256:')}.json"

    def write_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ReplayError("replay report payload must be an object")
        if payload.get("protocol") != REPLAY_REPORT_PROTOCOL:
            raise ReplayError("replay report protocol mismatch")
        if payload.get("authority") != "comparison-only":
            raise ReplayError("replay report authority must remain comparison-only")
        _validate_sha(payload.get("original_run_id"), "original_run_id")
        _validate_sha(payload.get("replay_run_id"), "replay_run_id")
        report_id = self._identity(payload)
        record = {"report_id": report_id, **payload}
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
        if payload.get("protocol") != REPLAY_RECORD_PROTOCOL:
            raise ReplayError("replay protocol mismatch")
        if payload.get("authority") != "orchestration-and-comparison-only":
            raise ReplayError("replay authority must remain orchestration-and-comparison-only")
        _validate_sha(payload.get("original_run_id"), "original_run_id")
        _validate_sha(payload.get("replay_run_id"), "replay_run_id")
        _validate_sha(payload.get("report_id"), "report_id")
        replay_id = self._identity(payload)
        record = {"replay_id": replay_id, **payload}
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
        payload = {key: value for key, value in record.items() if key != "report_id"}
        if self._identity(payload) != report_id:
            raise ReplayError("replay report content identity mismatch")
        return record

    def get_replay(self, replay_id: str) -> dict[str, Any]:
        path = self._path(self.records, replay_id)
        if not path.is_file():
            raise ReplayError(f"unknown replay: {replay_id}")
        record = _read(path)
        if record.get("replay_id") != replay_id:
            raise ReplayError("replay path/content identity mismatch")
        payload = {key: value for key, value in record.items() if key != "replay_id"}
        if self._identity(payload) != replay_id:
            raise ReplayError("replay content identity mismatch")
        report = self.get_report(record["report_id"])
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
    "REPLAY_BASIS_PROTOCOL",
    "REPLAY_LINK_PROTOCOL",
    "REPLAY_RECORD_PROTOCOL",
    "REPLAY_REPORT_PROTOCOL",
    "RESEARCH_TIMELINE_PROTOCOL",
    "ReplayError",
    "ReplayStore",
]
