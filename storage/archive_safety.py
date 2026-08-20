#!/usr/bin/env python3
"""Bounded archive validation for QSOL-CONTROL.

Compressed untrusted archives are default-deny. Phase 10 release verification accepts
only ZIP_STORED members and validates filesystem/archive/member bounds before reading
member payload bytes. This deliberately avoids creating a decompression-bomb surface.
"""

from __future__ import annotations

import stat
import struct
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_MEMBER_COUNT = 10_000
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
ALLOWED_COMPRESSION_METHODS = {zipfile.ZIP_STORED}
CANONICAL_RELEASE_TIME = (1980, 1, 1, 0, 0, 0)
CANONICAL_RELEASE_MODE = 0o100644
EOCD_SIGNATURE = b"PK\x05\x06"
EOCD_STRUCT = struct.Struct("<4s4H2LH")
MAX_EOCD_SEARCH_BYTES = EOCD_STRUCT.size + 0xFFFF


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


def _preflight_member_count(path: Path, size: int) -> int:
    """Read only the EOCD tail and bound entry count before ZipFile parses metadata.

    Phase 10 release archives never need ZIP64 under the published limits. ZIP64 and
    multi-disk archives therefore fail closed instead of forcing Python to materialize
    an attacker-controlled central-directory entry list before the count is checked.
    """

    read_size = min(size, MAX_EOCD_SEARCH_BYTES)
    try:
        with path.open("rb") as handle:
            handle.seek(size - read_size)
            tail = handle.read(read_size)
    except OSError as exc:
        raise ArchiveSafetyError(f"cannot read ZIP end record: {exc}") from exc

    search_end = len(tail)
    while True:
        offset = tail.rfind(EOCD_SIGNATURE, 0, search_end)
        if offset < 0:
            raise ArchiveSafetyError("ZIP end-of-central-directory record not found")
        if offset + EOCD_STRUCT.size <= len(tail):
            fields = EOCD_STRUCT.unpack_from(tail, offset)
            (
                _signature,
                disk_number,
                central_disk,
                entries_on_disk,
                total_entries,
                central_size,
                central_offset,
                comment_length,
            ) = fields
            if offset + EOCD_STRUCT.size + comment_length == len(tail):
                if disk_number != 0 or central_disk != 0 or entries_on_disk != total_entries:
                    raise ArchiveSafetyError("multi-disk ZIP archives are not accepted")
                if (
                    total_entries == 0xFFFF
                    or central_size == 0xFFFFFFFF
                    or central_offset == 0xFFFFFFFF
                ):
                    raise ArchiveSafetyError("ZIP64 archives are not accepted by the Phase 10 verifier")
                if total_entries > MAX_MEMBER_COUNT:
                    raise ArchiveSafetyError("archive member count exceeds limit")
                absolute_eocd = size - read_size + offset
                if central_offset + central_size > absolute_eocd:
                    raise ArchiveSafetyError("ZIP central-directory bounds are invalid")
                return total_entries
        search_end = offset


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

    declared_count = _preflight_member_count(archive_path, size)
    try:
        with zipfile.ZipFile(archive_path, "r", allowZip64=False) as archive:
            infos = archive.infolist()
            if len(infos) != declared_count:
                raise ArchiveSafetyError("archive member count disagrees with ZIP end record")
            if archive.comment != b"":
                raise ArchiveSafetyError("archive comment must be empty")
            names = [info.filename for info in infos]
            if names != sorted(names, key=lambda value: value.encode("utf-8")):
                raise ArchiveSafetyError("archive members are not in canonical UTF-8 order")

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
                if info.date_time != CANONICAL_RELEASE_TIME:
                    raise ArchiveSafetyError(f"archive member timestamp is noncanonical: {name}")
                if info.create_system != 3:
                    raise ArchiveSafetyError(f"archive member platform metadata is noncanonical: {name}")
                mode = (info.external_attr >> 16) & 0xFFFF
                if mode != CANONICAL_RELEASE_MODE:
                    raise ArchiveSafetyError(f"archive member mode is noncanonical: {name}")
                if info.extra != b"" or info.comment != b"":
                    raise ArchiveSafetyError(f"archive member extra/comment metadata is noncanonical: {name}")
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
        "canonical_metadata_verified": True,
        "member_count_bounded_before_zipfile_parse": True,
    }
