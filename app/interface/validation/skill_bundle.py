"""Validation helpers for uploaded skill zip bundles."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

MAX_SKILL_BUNDLE_SIZE_BYTES = 5 * 1024 * 1024
MAX_SKILL_BUNDLE_FILE_COUNT = 200
MAX_SKILL_BUNDLE_PATH_LENGTH = 240
ALLOWED_TOP_LEVEL_CHILDREN = frozenset({"SKILL.md", "scripts", "references", "assets"})


class SkillBundleValidationError(ValueError):
    """Raised when an uploaded skill bundle fails structural validation."""


@dataclass(frozen=True, slots=True)
class SkillBundleValidationReport:
    """Normalized bundle metadata produced by validation."""

    root_directory: str
    file_count: int
    size_bytes: int


def validate_skill_bundle(bundle_bytes: bytes) -> SkillBundleValidationReport:
    """Validate a skill bundle zip payload and return normalized metadata."""
    if len(bundle_bytes) > MAX_SKILL_BUNDLE_SIZE_BYTES:
        raise SkillBundleValidationError(
            f"Skill bundle exceeds the maximum size of {MAX_SKILL_BUNDLE_SIZE_BYTES} bytes."
        )

    try:
        with ZipFile(BytesIO(bundle_bytes)) as archive:
            return _validate_archive(bundle_bytes=bundle_bytes, archive=archive)
    except BadZipFile as exc:
        raise SkillBundleValidationError("Uploaded bundle must be a valid zip archive.") from exc


def _validate_archive(*, bundle_bytes: bytes, archive: ZipFile) -> SkillBundleValidationReport:
    file_count = 0
    root_directories: set[str] = set()
    normalized_entries: set[str] = set()
    root_children: set[str] = set()
    skill_markdown_present = False

    for info in archive.infolist():
        path = info.filename
        if not path:
            raise SkillBundleValidationError("Skill bundle entries must have a non-empty path.")
        if len(path) > MAX_SKILL_BUNDLE_PATH_LENGTH:
            raise SkillBundleValidationError(
                f"Skill bundle entry paths must not exceed {MAX_SKILL_BUNDLE_PATH_LENGTH} bytes."
            )

        normalized_path = _normalize_archive_path(path)
        if normalized_path in normalized_entries:
            raise SkillBundleValidationError(
                "Skill bundle must not contain duplicate normalized archive entries."
            )
        normalized_entries.add(normalized_path)
        parts = normalized_path.split("/")
        root_directories.add(parts[0])

        if len(root_directories) > 1:
            raise SkillBundleValidationError(
                "Skill bundle must contain exactly one root skill directory."
            )

        if not info.is_dir():
            file_count += 1
            if file_count > MAX_SKILL_BUNDLE_FILE_COUNT:
                raise SkillBundleValidationError(
                    f"Skill bundle must not exceed {MAX_SKILL_BUNDLE_FILE_COUNT} files."
                )

        if len(parts) >= 2:
            root_children.add(parts[1])
        if len(parts) == 2 and parts[1] == "SKILL.md" and not info.is_dir():
            skill_markdown_present = True
        if len(parts) == 2 and parts[1] == "README.md":
            raise SkillBundleValidationError(
                "README.md is not allowed at the root of the skill directory."
            )

    if not root_directories:
        raise SkillBundleValidationError("Skill bundle must contain at least one root directory.")

    root_directory = next(iter(root_directories))
    if not _is_kebab_case(root_directory):
        raise SkillBundleValidationError("Root skill directory name must be kebab-case.")

    disallowed_children = root_children - ALLOWED_TOP_LEVEL_CHILDREN
    if disallowed_children:
        disallowed = ", ".join(sorted(disallowed_children))
        raise SkillBundleValidationError(
            f"Skill bundle contains unsupported top-level entries: {disallowed}."
        )
    if not skill_markdown_present:
        raise SkillBundleValidationError("Skill bundle must include SKILL.md at the root.")

    return SkillBundleValidationReport(
        root_directory=root_directory,
        file_count=file_count,
        size_bytes=len(bundle_bytes),
    )


def _normalize_archive_path(path: str) -> str:
    pure_path = PurePosixPath(path)
    if pure_path.is_absolute():
        raise SkillBundleValidationError("Skill bundle must not contain absolute archive paths.")
    if any(part in {"", ".", ".."} for part in pure_path.parts):
        raise SkillBundleValidationError("Skill bundle must not contain path traversal entries.")
    return pure_path.as_posix().rstrip("/")


def _is_kebab_case(value: str) -> bool:
    if not value or value.startswith("-") or value.endswith("-") or "--" in value:
        return False
    return value.replace("-", "").isalnum() and value.lower() == value
