"""Unit tests for opaque skill artifact validation."""

from __future__ import annotations

import pytest

from app.core.skills.bundle_archive import build_skill_bundle, build_skill_bundle_from_entries
from app.interface.validation.skill_bundle import (
    MAX_SKILL_BUNDLE_FILE_COUNT,
    MAX_SKILL_BUNDLE_PATH_LENGTH_BYTES,
    SKILL_ARTIFACT_MEDIA_TYPE,
    SkillBundleValidationError,
    validate_skill_bundle,
)


@pytest.mark.unit
def test_validate_skill_bundle_accepts_tar_zst_artifact() -> None:
    report = validate_skill_bundle(
        build_skill_bundle("# Python Lint\n\nLint Python files.\n"),
        filename="python-lint.tar.zst",
        media_type=SKILL_ARTIFACT_MEDIA_TYPE,
    )

    assert report.filename == "python-lint.tar.zst"
    assert report.media_type == SKILL_ARTIFACT_MEDIA_TYPE
    assert report.size_bytes > 0


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
            build_skill_bundle("# Python Lint\n\nLint Python files.\n"),
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


@pytest.mark.unit
def test_validate_skill_bundle_rejects_invalid_tar_zst_payload() -> None:
    with pytest.raises(SkillBundleValidationError, match="valid \\.tar\\.zst"):
        validate_skill_bundle(
            b"not-a-real-tar-zst-stream",
            filename="python-lint.tar.zst",
            media_type=SKILL_ARTIFACT_MEDIA_TYPE,
        )


@pytest.mark.unit
def test_validate_skill_bundle_rejects_too_many_archive_members() -> None:
    entries = {
        f"skill-bundle/files/{index}.txt": f"file-{index}".encode()
        for index in range(MAX_SKILL_BUNDLE_FILE_COUNT + 1)
    }

    with pytest.raises(SkillBundleValidationError, match="maximum file count"):
        validate_skill_bundle(
            build_skill_bundle_from_entries(entries),
            filename="python-lint.tar.zst",
            media_type=SKILL_ARTIFACT_MEDIA_TYPE,
        )


@pytest.mark.unit
def test_validate_skill_bundle_rejects_overlong_member_paths() -> None:
    long_name = "a" * (MAX_SKILL_BUNDLE_PATH_LENGTH_BYTES + 1)

    with pytest.raises(SkillBundleValidationError, match="maximum path length"):
        validate_skill_bundle(
            build_skill_bundle_from_entries({long_name: b"too-long"}),
            filename="python-lint.tar.zst",
            media_type=SKILL_ARTIFACT_MEDIA_TYPE,
        )
