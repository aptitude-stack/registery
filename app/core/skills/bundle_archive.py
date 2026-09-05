"""Shared helpers for deterministic `.tar.zst` skill bundle handling."""

from __future__ import annotations

import tarfile
from collections.abc import Mapping
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath

import zstandard

MAX_SKILL_BUNDLE_SIZE_BYTES = 5 * 1024 * 1024
MAX_SKILL_BUNDLE_FILE_COUNT = 200
MAX_SKILL_BUNDLE_PATH_LENGTH_BYTES = 240
SKILL_ARTIFACT_EXTENSION = ".tar.zst"
SKILL_ARTIFACT_MEDIA_TYPE = "application/zstd"
SKILL_BUNDLE_MARKDOWN_PATH = "skill-bundle/SKILL.md"


class SkillBundleArchiveError(ValueError):
    """Raised when a skill bundle is not a valid `.tar.zst` archive."""


@dataclass(frozen=True, slots=True)
class SkillBundleInspection:
    """Summary information collected while validating a skill bundle."""

    member_count: int
    max_path_length_bytes: int


def build_skill_bundle(markdown: str, *, member_path: str = SKILL_BUNDLE_MARKDOWN_PATH) -> bytes:
    """Build a deterministic single-file `.tar.zst` skill bundle."""
    return build_skill_bundle_from_entries({member_path: markdown.encode("utf-8")})


def build_skill_bundle_from_entries(entries: Mapping[str, bytes]) -> bytes:
    """Build a deterministic `.tar.zst` skill bundle from the provided entries."""
    tar_buffer = BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w") as archive:
        for path, payload in sorted(entries.items()):
            info = tarfile.TarInfo(path)
            info.size = len(payload)
            info.mode = 0o644
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            archive.addfile(info, BytesIO(payload))

    compressor = zstandard.ZstdCompressor()
    return compressor.compress(tar_buffer.getvalue())


def inspect_skill_bundle(bundle_bytes: bytes) -> SkillBundleInspection:
    """Validate that bytes represent a readable `.tar.zst` archive and inspect its shape."""
    member_count = 0
    max_path_length_bytes = 0

    try:
        with zstandard.ZstdDecompressor().stream_reader(BytesIO(bundle_bytes)) as reader:
            with tarfile.open(fileobj=reader, mode="r|") as archive:
                for member in archive:
                    member_count += 1
                    if member_count > MAX_SKILL_BUNDLE_FILE_COUNT:
                        raise SkillBundleArchiveError(
                            "Skill artifact exceeds the maximum file count of "
                            f"{MAX_SKILL_BUNDLE_FILE_COUNT}."
                        )

                    if not member.isdir() and not member.isfile():
                        raise SkillBundleArchiveError(
                            f"Skill artifact member '{member.name}' is not a regular "
                            "file or directory."
                        )
                    _validate_member_path(member.name)

                    path_length_bytes = len(member.name.encode("utf-8"))
                    max_path_length_bytes = max(max_path_length_bytes, path_length_bytes)
                    if path_length_bytes > MAX_SKILL_BUNDLE_PATH_LENGTH_BYTES:
                        raise SkillBundleArchiveError(
                            "Skill artifact exceeds the maximum path length of "
                            f"{MAX_SKILL_BUNDLE_PATH_LENGTH_BYTES} bytes."
                        )
    except SkillBundleArchiveError:
        raise
    except (OSError, tarfile.TarError, zstandard.ZstdError) as exc:
        raise SkillBundleArchiveError("Skill artifact must be a valid `.tar.zst` archive.") from exc

    return SkillBundleInspection(
        member_count=member_count,
        max_path_length_bytes=max_path_length_bytes,
    )


def _validate_member_path(raw_name: str) -> None:
    """Reject archive paths that could escape an extraction directory."""
    if "\\" in raw_name:
        raise SkillBundleArchiveError(
            f"Skill artifact member '{raw_name}' uses an unsafe path separator."
        )

    member_path = PurePosixPath(raw_name)
    if member_path.is_absolute():
        raise SkillBundleArchiveError(f"Skill artifact member '{raw_name}' uses an absolute path.")
    if not member_path.parts or any(part in {"", ".", ".."} for part in member_path.parts):
        raise SkillBundleArchiveError(
            f"Skill artifact member '{raw_name}' contains an unsafe path segment."
        )
    if ":" in member_path.parts[0]:
        raise SkillBundleArchiveError(
            f"Skill artifact member '{raw_name}' looks like a drive-qualified path."
        )
