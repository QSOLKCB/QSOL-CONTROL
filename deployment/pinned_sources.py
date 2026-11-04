#!/usr/bin/env python3
"""Fetch immutable QSOL donor commits at build time; never pull during a request.

Requires only Python 3.11+ and git. An absent or changed pin fails closed.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PINS = HERE / "source-pins.json"
VENDOR = HERE / "_vendor"
SHA = re.compile(r"^[0-9a-f]{40}$")
REPOS = {
    "nexus": "https://github.com/QSOLKCB/QSOL-NEXUS.git",
    "fed": "https://github.com/QSOLKCB/QSOL-FED.git",
    "oracle": "https://github.com/QSOLKCB/QSOL-ORACLE.git",
}


class PinError(ValueError):
    pass


def pins() -> dict[str, str]:
    value = json.loads(PINS.read_text("utf-8"))
    if not isinstance(value, dict) or set(value) != {"protocol", "commits"}:
        raise PinError("source-pin manifest has unexpected fields")
    if value["protocol"] != "qsol-edge-pinned-sources/1":
        raise PinError("unsupported pin manifest")
    commits = value["commits"]
    if not isinstance(commits, dict) or set(commits) != set(REPOS):
        raise PinError("source-pin repository set changed")
    if any(not isinstance(item, str) or SHA.fullmatch(item) is None for item in commits.values()):
        raise PinError("source pin is not a full SHA-1 commit identity")
    return commits


def _git(*args: str, cwd: Path | None = None, timeout: int = 120) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(cwd) if cwd else None, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=timeout,
    )
    return result.stdout.strip()


def verify_sources() -> dict[str, str]:
    expected = pins()
    for name, sha in expected.items():
        root = VENDOR / name
        if root.is_symlink() or not root.is_dir() or not (root / ".git").is_dir():
            raise PinError(f"missing or unsafe pinned checkout: {name}")
        actual = _git("-C", str(root), "rev-parse", "HEAD")
        if actual != sha:
            raise PinError(f"pinned checkout mismatch: {name}")
        remote = _git("-C", str(root), "remote", "get-url", "origin")
        if remote != REPOS[name]:
            raise PinError(f"unexpected pinned checkout origin: {name}")
    return expected


def fetch_sources() -> dict[str, str]:
    expected = pins()
    if VENDOR.is_symlink():
        raise PinError("source cache may not be a symlink")
    VENDOR.mkdir(mode=0o700, exist_ok=True)
    for name, sha in expected.items():
        target = VENDOR / name
        if target.exists():
            continue  # Never auto-repair an unexpected or drifting checkout.
        target.mkdir(mode=0o700)
        _git("init", "-q", str(target))
        _git("-C", str(target), "remote", "add", "origin", REPOS[name])
        _git("-C", str(target), "fetch", "--depth=1", "--filter=blob:none",
             "--no-tags", "origin", sha, timeout=240)
        _git("-C", str(target), "checkout", "--detach", "--quiet", "FETCH_HEAD", timeout=240)
    return verify_sources()


def main(argv: list[str]) -> int:
    try:
        result = verify_sources() if argv == ["--verify"] else fetch_sources() if not argv else None
        if result is None:
            raise PinError("usage: python3 -m deployment.pinned_sources [--verify]")
        print(json.dumps({"protocol": "qsol-edge-pinned-sources/1", "verified": sorted(result),
                          "commits": result}, sort_keys=True))
        return 0
    except (PinError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(f"source pin verification failed: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
