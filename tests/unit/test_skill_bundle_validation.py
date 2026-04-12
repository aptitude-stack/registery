"""Unit tests for zip bundle validation."""

from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.interface.validation.skill_bundle import (
    SkillBundleValidationError,
    validate_skill_bundle,
)


def _bundle(files: dict[str, str]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


@pytest.mark.unit
def test_validate_skill_bundle_accepts_required_root_layout() -> None:
    report = validate_skill_bundle(
        _bundle(
            {
                "python-lint/SKILL.md": "---\nname: Python Lint\n---\n",
                "python-lint/scripts/run.py": "print('ok')\n",
                "python-lint/references/usage.md": "# Usage\n",
                "python-lint/assets/icon.txt": "icon\n",
            }
        )
    )

    assert report.root_directory == "python-lint"
    assert report.file_count == 4
    assert report.size_bytes > 0


@pytest.mark.unit
def test_validate_skill_bundle_rejects_non_zip_payload() -> None:
    with pytest.raises(SkillBundleValidationError, match="valid zip archive"):
        validate_skill_bundle(b"not-a-zip")


@pytest.mark.unit
def test_validate_skill_bundle_rejects_multiple_root_directories() -> None:
    with pytest.raises(SkillBundleValidationError, match="exactly one root"):
        validate_skill_bundle(
            _bundle(
                {
                    "python-lint/SKILL.md": "---\nname: Python Lint\n---\n",
                    "python-format/SKILL.md": "---\nname: Python Format\n---\n",
                }
            )
        )


@pytest.mark.unit
def test_validate_skill_bundle_rejects_path_traversal() -> None:
    with pytest.raises(SkillBundleValidationError, match="path traversal"):
        validate_skill_bundle(
            _bundle(
                {
                    "python-lint/SKILL.md": "---\nname: Python Lint\n---\n",
                    "python-lint/../escape.txt": "nope\n",
                }
            )
        )


@pytest.mark.unit
def test_validate_skill_bundle_requires_root_skill_markdown() -> None:
    with pytest.raises(SkillBundleValidationError, match="SKILL.md"):
        validate_skill_bundle(
            _bundle(
                {
                    "python-lint/scripts/run.py": "print('ok')\n",
                }
            )
        )


@pytest.mark.unit
def test_validate_skill_bundle_forbids_root_readme() -> None:
    with pytest.raises(SkillBundleValidationError, match="README.md"):
        validate_skill_bundle(
            _bundle(
                {
                    "python-lint/SKILL.md": "---\nname: Python Lint\n---\n",
                    "python-lint/README.md": "# Legacy\n",
                }
            )
        )


@pytest.mark.unit
def test_validate_skill_bundle_rejects_disallowed_top_level_entries() -> None:
    with pytest.raises(SkillBundleValidationError, match="top-level"):
        validate_skill_bundle(
            _bundle(
                {
                    "python-lint/SKILL.md": "---\nname: Python Lint\n---\n",
                    "python-lint/docs/extra.md": "# Extra\n",
                }
            )
        )
