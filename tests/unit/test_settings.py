"""Unit tests for typed settings loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.governance import build_default_policy_profile
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
    assert settings.app_env == app_env
    assert settings.log_level == "DEBUG"
    assert settings.log_format == "pretty"
    assert settings.app_name == "aptitude-test"
    assert (
        settings.active_policy.discovery_default_statuses
        == default_policy.discovery_default_statuses
    )


@pytest.mark.unit
def test_settings_require_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


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
