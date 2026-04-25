"""Regression coverage for removing legacy zip artifact storage."""

from __future__ import annotations

import importlib.util
import tarfile
from io import BytesIO
from pathlib import Path
from types import ModuleType
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
import zstandard


def _load_migration(path: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location("migration_under_test", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_bundle_storage_migration_no_longer_creates_zip_artifacts() -> None:
    migration = Path("alembic/versions/0003_skill_bundle_storage.py").read_text(encoding="utf-8")

    assert "application/zip" not in migration
    assert "zipfile" not in migration


@pytest.mark.unit
def test_legacy_zip_cleanup_rewrites_payload_as_tar_zst() -> None:
    migration = _load_migration("alembic/versions/0005_remove_legacy_zip_skill_artifacts.py")
    legacy_payload = BytesIO()
    with ZipFile(legacy_payload, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("legacy-skill/SKILL.md", "# Legacy Skill\n")

    markdown = migration._extract_legacy_zip_markdown(legacy_payload.getvalue())
    converted = migration._bundle_markdown(markdown)

    assert markdown == "# Legacy Skill\n"
    with zstandard.ZstdDecompressor().stream_reader(BytesIO(converted)) as reader:
        with tarfile.open(fileobj=reader, mode="r|") as archive:
            member = archive.next()
            assert member is not None
            extracted = archive.extractfile(member)
            assert extracted is not None
            assert member.name == "skill-bundle/SKILL.md"
            assert extracted.read().decode("utf-8") == "# Legacy Skill\n"
