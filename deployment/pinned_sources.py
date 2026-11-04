#!/usr/bin/env python3
"""Fetch immutable QSOL donor commits at build time; never pull during a request.

Requires only Python 3.11+ and git. An absent or changed pin fails closed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath

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


def _git_bytes(*args: str, timeout: int = 120) -> bytes:
    """Read a bounded Git result without losing NUL-delimited path bytes."""
    result = subprocess.run(
        ["git", *args], check=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=timeout,
    )
    return result.stdout


def _verify_worktree_bytes(root: Path) -> None:
    """Compare every checked-out file with HEAD's tree, not the cached index.

    Git status alone can miss assume-unchanged/index-masked modifications;
    source imports also need protection against *ignored* or untracked files.
    All tracked blobs are byte-compared to their Git object identities.
    """
    entries = _git_bytes("-C", str(root), "ls-tree", "-r", "-z", "--full-tree", "HEAD")
    if not entries:
        raise PinError("pinned checkout has no tracked source files")
    inspected = 0
    for entry in entries.split(b"\0"):
        if not entry:
            continue
        try:
            meta, raw_path = entry.split(b"\t", 1)
            mode, kind, expected_blob = meta.decode("ascii").split(" ")
            relative = PurePosixPath(os.fsdecode(raw_path))
        except (ValueError, UnicodeError) as exc:
            raise PinError("invalid tracked source tree entry") from exc
        if (kind != "blob" or mode not in {"100644", "100755"}
                or not relative.parts or relative.is_absolute()
                or any(part in {".", ".."} for part in relative.parts)
                or len(expected_blob) != 40):
            raise PinError("unsupported source entry type or path")
        current = root
        for segment in relative.parts:
            current = current / segment
            if current.is_symlink():
                raise PinError("symlink in pinned source path")
        try:
            file_stat = current.lstat()
            if not stat.S_ISREG(file_stat.st_mode):
                raise PinError("non-regular pinned source object")
            if os.name == "posix" and bool(file_stat.st_mode & stat.S_IXUSR) != (mode == "100755"):
                raise PinError("tracked source executable bit drift")
            contents = current.read_bytes()
        except (OSError, ValueError) as exc:
            raise PinError("pinned source file could not be verified") from exc
        object_input = b"blob " + str(len(contents)).encode("ascii") + b"\0" + contents
        if hashlib.sha1(object_input).hexdigest() != expected_blob:
            raise PinError("pinned source byte hash mismatch")
        inspected += 1
    if not inspected:
        raise PinError("no source files verified")
    # Includes ignored .pyc, __pycache__, shadow modules and untracked files.
    # All source-backed Python entrypoints must run with -B (no bytecode writes).
    dirty = _git("-C", str(root), "status", "--porcelain=v1",
                 "--untracked-files=all", "--ignored=matching")
    if dirty:
        raise PinError("pinned source checkout contains modified or extra files")


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
        _verify_worktree_bytes(root)
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
        # PinError messages are fixed, nonsecret validation reasons.
        reason = str(exc) if isinstance(exc, PinError) else type(exc).__name__
        print(f"source pin verification failed: {reason}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
