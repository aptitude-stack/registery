"""Unit tests for typed settings loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.governance import build_default_policy_profile
from app.core.semantic_defaults import (
    DEFAULT_SEMANTIC_CANDIDATE_LIMIT,
    DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS,
    DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
    DEFAULT_SEMANTIC_EMBEDDING_MODEL,
    DEFAULT_SEMANTIC_EMBEDDING_PROVIDER,
    DEFAULT_SEMANTIC_HNSW_EF_SEARCH,
    DEFAULT_SEMANTIC_QUERY_TIMEOUT_MS,
)
from app.core.settings import Settings, get_settings
from tests.conftest import DEFAULT_ALLOWED_HOSTS, DEFAULT_AUTH_SERVICE_TOKENS


@pytest.mark.unit
@pytest.mark.parametrize("app_env", ["dev", "prod"])
def test_settings_load_valid_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_env: str,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude",
    )
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FORMAT", "pretty")
    monkeypatch.setenv("APP_NAME", "aptitude-test")
    if app_env == "prod":
        monkeypatch.setenv("ALLOWED_HOSTS_JSON", json.dumps(DEFAULT_ALLOWED_HOSTS))

    settings = Settings(_env_file=None)
    default_policy = build_default_policy_profile()

    assert settings.database_url.endswith("/aptitude")
    assert settings.migration_database_url is None
    assert settings.database_connect_timeout_seconds == 5
    assert settings.app_env == app_env
    assert settings.log_level == "DEBUG"
    assert settings.log_format == "pretty"
    assert settings.app_name == "aptitude-test"
    assert (
        settings.active_policy.discovery_default_statuses
        == default_policy.discovery_default_statuses
    )
    assert settings.semantic_discovery_mode == "off"
    assert settings.semantic_embedding_provider == DEFAULT_SEMANTIC_EMBEDDING_PROVIDER
    assert settings.semantic_embedding_model == DEFAULT_SEMANTIC_EMBEDDING_MODEL
    assert settings.semantic_embedding_index_key == DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY
    assert settings.semantic_embedding_dimensions == DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS
    assert settings.semantic_candidate_limit == DEFAULT_SEMANTIC_CANDIDATE_LIMIT
    assert settings.semantic_query_timeout_ms == DEFAULT_SEMANTIC_QUERY_TIMEOUT_MS
    assert settings.semantic_hnsw_ef_search == DEFAULT_SEMANTIC_HNSW_EF_SEARCH
    assert settings.co_usage_ranking_enabled is False
    assert settings.co_usage_boost_cap == 0.05


@pytest.mark.unit
def test_settings_validate_semantic_discovery_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude",
    )
    monkeypatch.setenv("SEMANTIC_DISCOVERY_MODE", "hybrid")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("SEMANTIC_EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv(
        "SEMANTIC_EMBEDDING_INDEX_KEY",
        "openai:text-embedding-3-small:description-tags-v1",
    )
    monkeypatch.setenv("SEMANTIC_CANDIDATE_LIMIT", "12")
    monkeypatch.setenv("SEMANTIC_QUERY_TIMEOUT_MS", "75")
    monkeypatch.setenv("CO_USAGE_RANKING_ENABLED", "true")
    monkeypatch.setenv("CO_USAGE_BOOST_CAP", "0.03")

    settings = Settings(_env_file=None)

    assert settings.semantic_discovery_mode == "hybrid"
    assert settings.openai_api_key == "test-openai-key"
    assert settings.semantic_embedding_model == "text-embedding-3-small"
    assert (
        settings.semantic_embedding_index_key == "openai:text-embedding-3-small:description-tags-v1"
    )
    assert settings.semantic_candidate_limit == 12
    assert settings.semantic_query_timeout_ms == 75
    assert settings.co_usage_ranking_enabled is True
    assert settings.co_usage_boost_cap == 0.03


@pytest.mark.unit
def test_settings_require_openai_key_when_semantic_mode_uses_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude",
    )
    monkeypatch.setenv("SEMANTIC_DISCOVERY_MODE", "shadow")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        Settings(_env_file=None)


@pytest.mark.unit
def test_settings_reject_embedding_index_key_that_does_not_match_provider_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("SEMANTIC_DISCOVERY_MODE", "hybrid")
    monkeypatch.setenv("SEMANTIC_EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("SEMANTIC_EMBEDDING_INDEX_KEY", "metadata-1536-v1")

    with pytest.raises(ValidationError, match="SEMANTIC_EMBEDDING_INDEX_KEY"):
        Settings(_env_file=None)


@pytest.mark.unit
def test_settings_require_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.unit
def test_settings_load_optional_migration_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://runtime:postgres@ep-runtime-pooler.us-east-1.aws.neon.tech/aptitude",
    )
    monkeypatch.setenv(
        "MIGRATION_DATABASE_URL",
        "postgresql+psycopg://migration:postgres@ep-runtime.us-east-1.aws.neon.tech/aptitude",
    )

    settings = Settings(_env_file=None)

    assert settings.database_url.endswith("-pooler.us-east-1.aws.neon.tech/aptitude")
    assert settings.migration_database_url is not None
    assert settings.migration_database_url.endswith(".us-east-1.aws.neon.tech/aptitude")


@pytest.mark.unit
def test_settings_reject_invalid_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude",
    )
    monkeypatch.setenv("APP_ENV", "test")

    with pytest.raises(ValidationError, match="APP_ENV"):
        Settings(_env_file=None)


@pytest.mark.unit
def test_settings_require_allowed_hosts_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude",
    )
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("ALLOWED_HOSTS_JSON", raising=False)

    with pytest.raises(ValidationError, match="ALLOWED_HOSTS_JSON"):
        Settings(_env_file=None)


@pytest.mark.unit
def test_settings_load_service_tokens_from_dotenv_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_SERVICE_TOKENS_JSON", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude",
                f"AUTH_SERVICE_TOKENS_JSON={json.dumps(DEFAULT_AUTH_SERVICE_TOKENS[:2])}",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert tuple(token.token_id for token in settings.auth_service_tokens) == (
        "reader-token",
        "publisher-token",
    )
    assert settings.service_token_records[0].scopes == frozenset({"read"})
    assert settings.service_token_records[1].scopes == frozenset({"read", "publish"})


@pytest.mark.unit
def test_settings_load_service_tokens_from_provider_quoted_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude",
    )
    monkeypatch.setenv(
        "AUTH_SERVICE_TOKENS_JSON",
        f"'{json.dumps(DEFAULT_AUTH_SERVICE_TOKENS[:1])}'",
    )

    settings = Settings(_env_file=None)

    assert tuple(token.token_id for token in settings.auth_service_tokens) == ("reader-token",)


@pytest.mark.unit
def test_get_settings_uses_configured_dotenv_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("AUTH_SERVICE_TOKENS_JSON", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude",
                f"AUTH_SERVICE_TOKENS_JSON={json.dumps(DEFAULT_AUTH_SERVICE_TOKENS[:2])}",
                f"ALLOWED_HOSTS_JSON={json.dumps(DEFAULT_ALLOWED_HOSTS)}",
                "APP_ENV=prod",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_SETTINGS_ENV_FILE", str(env_file))

    settings = get_settings()

    assert settings.database_url.endswith("/aptitude")
    assert tuple(token.token_id for token in settings.auth_service_tokens) == (
        "reader-token",
        "publisher-token",
    )
    assert settings.allowed_hosts == DEFAULT_ALLOWED_HOSTS
    assert settings.app_env == "prod"
