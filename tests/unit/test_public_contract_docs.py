"""Contract documentation checks for the bundle-based publish/fetch surface."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_plan_12_describes_full_skill_directory_bundle_support() -> None:
    text = Path(".agents/plans/12-full-skill-directory-bundle-support.md").read_text(
        encoding="utf-8"
    )

    assert "bundle" in text
    assert "text/markdown" in text


@pytest.mark.unit
def test_publish_bundle_migration_doc_exists_and_mentions_breaking_change() -> None:
    path = Path("docs/reference/publish-bundle-migration.md")

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "breaking change" in text.lower()
    assert "application/zstd" in text
    assert "content.raw_markdown" in text


@pytest.mark.unit
def test_api_contract_docs_describe_tar_zst_upload_and_fetch() -> None:
    api_contract = Path("docs/reference/api-contract.md").read_text(encoding="utf-8")
    publish_contract = Path("docs/reference/publish-request-schema.md").read_text(encoding="utf-8")
    storage_strategy = Path("docs/reference/storage-strategy.md").read_text(encoding="utf-8")
    schema_reference = Path("docs/reference/schema.md").read_text(encoding="utf-8")

    assert "multipart/form-data" in api_contract
    assert "application/zstd" in api_contract
    assert ".tar.zst" in api_contract
    assert "5 MiB" in api_contract
    assert "multipart/form-data" in publish_contract
    assert "application/zstd" in publish_contract
    assert ".tar.zst" in publish_contract
    assert "5 MiB" in publish_contract
    assert "content.checksum.digest" in publish_contract
    assert "version_checksum.digest" in publish_contract
    assert "opaque artifact" in storage_strategy.lower()
    assert "skill_contents.payload" in schema_reference
    assert "stored bundle size" in schema_reference


@pytest.mark.unit
def test_bruno_collection_uses_tar_zst_publish_and_content_contract() -> None:
    publish_requests = [
        Path("bruno/collections/Positive/Publish Dependency Skill.yml"),
        Path("bruno/collections/Positive/Publish Extension Skill.yml"),
        Path("bruno/collections/Positive/Publish Overlap Skill.yml"),
        Path("bruno/collections/Positive/Publish Skill v1.yml"),
        Path("bruno/collections/Positive/Publish Skill v2.yml"),
        Path("bruno/collections/Negative/Publish Invalid Request.yml"),
        Path("bruno/collections/Negative/Seed Duplicate Skill Version.yml"),
        Path("bruno/collections/Negative/Publish Duplicate Skill Version.yml"),
    ]
    exact_content_requests = [
        Path("bruno/collections/Positive/Fetch Published Skill Content.yml"),
        Path("bruno/collections/Negative/Fetch Missing Skill Content.yml"),
    ]
    fixtures = [
        Path("bruno/fixtures/dependency.tar.zst"),
        Path("bruno/fixtures/duplicate.tar.zst"),
        Path("bruno/fixtures/extension.tar.zst"),
        Path("bruno/fixtures/invalid.tar.zst"),
        Path("bruno/fixtures/overlap.tar.zst"),
        Path("bruno/fixtures/primary-v1.tar.zst"),
        Path("bruno/fixtures/primary-v2.tar.zst"),
    ]

    for path in publish_requests:
        text = path.read_text(encoding="utf-8")
        assert ".tar.zst" in text
        assert "application/zip" not in text
        assert ".zip" not in text

    for path in exact_content_requests:
        text = path.read_text(encoding="utf-8")
        assert "application/zstd" in text
        assert "application/zip" not in text

    for path in fixtures:
        assert path.exists(), f"missing Bruno fixture: {path}"
