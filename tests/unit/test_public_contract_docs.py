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
    service_token_governance = Path("docs/reference/service-token-governance.md").read_text(
        encoding="utf-8"
    )
    storage_strategy = Path("docs/reference/storage-strategy.md").read_text(encoding="utf-8")
    schema_reference = Path("docs/reference/schema.md").read_text(encoding="utf-8")
    runtime_profiles = Path("docs/reference/runtime-profiles.md").read_text(encoding="utf-8")

    assert "multipart/form-data" in api_contract
    assert "application/zstd" in api_contract
    assert ".tar.zst" in api_contract
    assert "5 MiB" in api_contract
    assert "<token_id>.<token_secret>" in api_contract
    assert "multipart/form-data" in publish_contract
    assert "application/zstd" in publish_contract
    assert ".tar.zst" in publish_contract
    assert "5 MiB" in publish_contract
    assert "<token_id>.<token_secret>" in publish_contract
    assert "content.checksum.digest" in publish_contract
    assert "version_checksum.digest" in publish_contract
    assert "AUTH_SERVICE_TOKENS_JSON" in service_token_governance
    assert "ALLOWED_HOSTS_JSON" in service_token_governance
    assert "MALFORMED_AUTH_TOKEN" in service_token_governance
    assert "admin-token.dev-admin-secret" in service_token_governance
    assert "opaque artifact" in storage_strategy.lower()
    assert "skill_contents.payload" in schema_reference
    assert "stored bundle size" in schema_reference
    assert "AUTH_SERVICE_TOKENS_JSON" in runtime_profiles
    assert "ALLOWED_HOSTS_JSON" in runtime_profiles
