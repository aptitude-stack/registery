"""Unit tests for opaque skill artifact validation."""

from __future__ import annotations

import pytest

from app.interface.validation.skill_bundle import (
    SKILL_ARTIFACT_MEDIA_TYPE,
    SkillBundleValidationError,
    validate_skill_bundle,
)


@pytest.mark.unit
def test_validate_skill_bundle_accepts_tar_zst_artifact() -> None:
    report = validate_skill_bundle(
        b"zstd-compressed-tarball",
        filename="python-lint.tar.zst",
        media_type=SKILL_ARTIFACT_MEDIA_TYPE,
    )

    assert report.filename == "python-lint.tar.zst"
    assert report.media_type == SKILL_ARTIFACT_MEDIA_TYPE
    assert report.size_bytes == len(b"zstd-compressed-tarball")


@pytest.mark.unit
def test_validate_skill_bundle_rejects_non_tar_zst_filename() -> None:
    with pytest.raises(SkillBundleValidationError, match=r"\.tar\.zst"):
        validate_skill_bundle(
            b"zip-payload",
            filename="python-lint.zip",
            media_type=SKILL_ARTIFACT_MEDIA_TYPE,
        )


@pytest.mark.unit
def test_validate_skill_bundle_rejects_unsupported_media_type() -> None:
    with pytest.raises(SkillBundleValidationError, match="media type"):
        validate_skill_bundle(
            b"opaque-payload",
            filename="python-lint.tar.zst",
            media_type="application/zip",
        )


@pytest.mark.unit
def test_validate_skill_bundle_rejects_oversized_payload() -> None:
    oversized = b"x" * ((5 * 1024 * 1024) + 1)

    with pytest.raises(SkillBundleValidationError, match="maximum size"):
        validate_skill_bundle(
            oversized,
            filename="python-lint.tar.zst",
            media_type=SKILL_ARTIFACT_MEDIA_TYPE,
        )
