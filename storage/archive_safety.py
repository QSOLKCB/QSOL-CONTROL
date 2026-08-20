#!/usr/bin/env python3
"""Bounded archive validation for QSOL-CONTROL.

Compressed untrusted archives are default-deny. Phase 10 release verification accepts
only ZIP_STORED members and validates filesystem/archive/member bounds before reading
member payload bytes. This deliberately avoids creating a decompression-bomb surface.
"""

from __future__ import annotations

import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_MEMBER_COUNT = 10_000
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
ALLOWED_COMPRESSION_METHODS = {zipfile.ZIP_STORED}


class ArchiveSafetyError(ValueError):
    """Raised when an archive violates the Phase 10 bounded-import contract."""


def canonical_member_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ArchiveSafetyError("archive member must be a canonical relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ArchiveSafetyError("archive member contains absolute/dot/parent segment")
    if path.as_posix() != value:
        raise ArchiveSafetyError("archive member path is not canonical POSIX form")
    return value


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_ISLNK(mode)


def validate_zip_archive(path: str | Path) -> dict[str, Any]:
    """Validate a ZIP without extracting it or decompressing member payloads.

    Only stored members are accepted. This is intentional: callers that later need
    compressed imports must introduce a separately reviewed bounded decoder rather than
    silently widening this policy.
    """

    archive_path = Path(path)
    if archive_path.is_symlink():
        raise ArchiveSafetyError("archive path must not be a symlink")
    if not archive_path.is_file():
        raise ArchiveSafetyError("archive path must be a regular file")
    size = archive_path.stat().st_size
    if size > MAX_ARCHIVE_BYTES:
        raise ArchiveSafetyError("archive exceeds on-disk byte limit")

    try:
        with zipfile.ZipFile(archive_path, "r", allowZip64=True) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_MEMBER_COUNT:
                raise ArchiveSafetyError("archive member count exceeds limit")
            seen: set[str] = set()
            total = 0
            for info in infos:
                name = canonical_member_path(info.filename)
                if name in seen:
                    raise ArchiveSafetyError(f"duplicate archive member: {name}")
                seen.add(name)
                if info.is_dir():
                    raise ArchiveSafetyError("directory entries are not accepted in release archives")
                if _is_symlink(info):
                    raise ArchiveSafetyError(f"symlink archive member rejected: {name}")
                if info.compress_type not in ALLOWED_COMPRESSION_METHODS:
                    raise ArchiveSafetyError(
                        f"compressed archive member rejected: {name}; only ZIP_STORED is accepted"
                    )
                if info.file_size < 0 or info.file_size > MAX_MEMBER_BYTES:
                    raise ArchiveSafetyError(f"archive member exceeds byte limit: {name}")
                if info.compress_size != info.file_size:
                    raise ArchiveSafetyError(f"stored archive member size mismatch: {name}")
                total += info.file_size
                if total > MAX_TOTAL_UNCOMPRESSED_BYTES:
                    raise ArchiveSafetyError("archive total member bytes exceed limit")
    except ArchiveSafetyError:
        raise
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ArchiveSafetyError(f"invalid ZIP archive: {exc}") from exc

    return {
        "status": "valid",
        "compression_policy": "zip-stored-only",
        "archive_size_bytes": size,
        "member_count": len(seen),
        "total_member_bytes": total,
        "decompression_performed": False,
    }
