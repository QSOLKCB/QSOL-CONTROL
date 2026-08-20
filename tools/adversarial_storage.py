#!/usr/bin/env python3
"""Deterministic adversarial/fuzz-style storage battery for Phase 10.

This is intentionally reproducible rather than coverage-guided. It exercises malformed
identities, path traversal, credential metadata, object corruption, and bounded archive
validation using a fixed seed suitable for CI and long-term archaeology.
"""

from __future__ import annotations

import argparse
import json
import random
import string
import tempfile
from pathlib import Path
from typing import Any

from storage.archive_safety import ArchiveSafetyError, canonical_member_path
from storage.concap_bundle import ConcapBundleError, canonical_relative_path
from storage.control_store import ControlStore, StorageError
from tools.file_metadata_audit import MetadataAuditError, reject_secrets

DEFAULT_SEED = 0x51534F4C
DEFAULT_ITERATIONS = 256
MAX_ITERATIONS = 10_000


def _expect_error(callable_obj, error_types: tuple[type[BaseException], ...]) -> bool:
    try:
        callable_obj()
    except error_types:
        return True
    return False


def run_battery(*, seed: int = DEFAULT_SEED, iterations: int = DEFAULT_ITERATIONS) -> dict[str, Any]:
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    if not isinstance(iterations, int) or isinstance(iterations, bool) or not (1 <= iterations <= MAX_ITERATIONS):
        raise ValueError(f"iterations must be 1..{MAX_ITERATIONS}")

    rng = random.Random(seed)
    passed = 0
    failed = 0

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        store = ControlStore(root / "store")

        alphabet = string.ascii_letters + string.digits + ":/_-."
        for _ in range(iterations):
            candidate = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 90)))
            if _expect_error(lambda c=candidate: store.get_file_record(c), (StorageError,)):
                passed += 1
            else:
                failed += 1

        traversal_cases = [
            "../escape",
            "/absolute",
            "a/../b",
            "./dot",
            "a\\b",
            "a//b",
        ]
        for candidate in traversal_cases:
            ok = _expect_error(
                lambda c=candidate: canonical_relative_path(c, "fuzz"),
                (ConcapBundleError,),
            ) and _expect_error(
                lambda c=candidate: canonical_member_path(c),
                (ArchiveSafetyError,),
            )
            passed += int(ok)
            failed += int(not ok)

        secret_cases = [
            {"api_key": "synthetic"},
            {"nested": {"access-token": "synthetic"}},
            {"locator": "https://example.invalid/?access_token=synthetic"},
            {"value": "ghp_SYNTHETIC_DO_NOT_USE"},
            {"cookie": "session=synthetic"},
        ]
        for value in secret_cases:
            ok = _expect_error(lambda v=value: reject_secrets(v), (MetadataAuditError,))
            passed += int(ok)
            failed += int(not ok)

        for index in range(min(iterations, 64)):
            content = bytes(rng.randrange(256) for _ in range(rng.randint(0, 512)))
            record = store.put_file(
                content,
                filename=f"fuzz-{index:04d}.bin",
                created_at="2026-08-20T12:00:00+00:00",
                privacy_class="INTERNAL",
                retention_class="ARCHIVE",
            )
            object_path = store._object_path(record["object_id"])
            original = object_path.read_bytes()
            object_path.write_bytes(original + b"x")
            ok = _expect_error(lambda rid=record["file_id"]: store.read_file(rid), (StorageError,))
            passed += int(ok)
            failed += int(not ok)
            object_path.write_bytes(original)

    return {
        "protocol": "qsol-control-adversarial-storage/1",
        "seed": seed,
        "iterations": iterations,
        "passed": passed,
        "failed": failed,
        "status": "pass" if failed == 0 else "fail",
        "deterministic": True,
        "truth_claimed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic CONTROL storage adversarial battery")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_battery(seed=args.seed, iterations=args.iterations)
    except ValueError as exc:
        print(f"adversarial storage error: {exc}")
        return 2
    print(
        json.dumps(report, sort_keys=True, separators=(",", ":"))
        if args.json
        else json.dumps(report, indent=2, sort_keys=True)
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
