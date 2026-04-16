"""Validation helpers for uploaded opaque skill artifacts."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.skills.bundle_archive import (
    MAX_SKILL_BUNDLE_FILE_COUNT,
    MAX_SKILL_BUNDLE_PATH_LENGTH_BYTES,
    MAX_SKILL_BUNDLE_SIZE_BYTES,
    SKILL_ARTIFACT_EXTENSION,
    SKILL_ARTIFACT_MEDIA_TYPE,
    SkillBundleArchiveError,
    inspect_skill_bundle,
)


class SkillBundleValidationError(ValueError):
    """Raised when an uploaded skill artifact fails validation."""


@dataclass(frozen=True, slots=True)
class SkillBundleValidationReport:
    """Normalized metadata produced by artifact validation."""

    filename: str
    media_type: str
    size_bytes: int


def validate_skill_bundle(
    bundle_bytes: bytes,
    *,
    filename: str | None,
    media_type: str | None,
) -> SkillBundleValidationReport:
    """Validate an opaque `.tar.zst` publish artifact and return normalized metadata."""
    if len(bundle_bytes) > MAX_SKILL_BUNDLE_SIZE_BYTES:
        raise SkillBundleValidationError(
            f"Skill artifact exceeds the maximum size of {MAX_SKILL_BUNDLE_SIZE_BYTES} bytes."
        )

    normalized_filename = (filename or "").strip()
    if not normalized_filename.endswith(SKILL_ARTIFACT_EXTENSION):
        raise SkillBundleValidationError(
            f"Skill artifact filename must end with `{SKILL_ARTIFACT_EXTENSION}`."
        )

    normalized_media_type = (media_type or SKILL_ARTIFACT_MEDIA_TYPE).strip().lower()
    if normalized_media_type != SKILL_ARTIFACT_MEDIA_TYPE:
        raise SkillBundleValidationError(
            f"Skill artifact media type must be `{SKILL_ARTIFACT_MEDIA_TYPE}`."
        )

    try:
        inspect_skill_bundle(bundle_bytes)
    except SkillBundleArchiveError as exc:
        message = str(exc)
        if str(MAX_SKILL_BUNDLE_FILE_COUNT) in message:
            raise SkillBundleValidationError(
                f"Skill artifact exceeds the maximum file count of {MAX_SKILL_BUNDLE_FILE_COUNT}."
            ) from exc
        if str(MAX_SKILL_BUNDLE_PATH_LENGTH_BYTES) in message:
            raise SkillBundleValidationError(
                "Skill artifact exceeds the maximum path length of "
                f"{MAX_SKILL_BUNDLE_PATH_LENGTH_BYTES} bytes."
            ) from exc
        raise SkillBundleValidationError(
            "Skill artifact must be a valid .tar.zst archive."
        ) from exc

    return SkillBundleValidationReport(
        filename=normalized_filename,
        media_type=normalized_media_type,
        size_bytes=len(bundle_bytes),
    )
