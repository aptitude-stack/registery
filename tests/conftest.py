"""Shared pytest fixtures for the service skeleton."""

from __future__ import annotations

import json
import os
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from alembic import command
from app.core.settings import SETTINGS_ENV_FILE_ENV_VAR, reset_settings_cache
from app.persistence.db import dispose_engine

DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5433/aptitude_test"
DEFAULT_ALLOWED_HOSTS = ("testserver", "127.0.0.1", "localhost", "server")
DEFAULT_SERVICE_TOKEN_SECRETS = {
    "reader-token": "dev-reader-secret",
    "publisher-token": "dev-publisher-secret",
    "admin-token": "dev-admin-secret",
}
DEFAULT_BEARER_TOKENS = {
    token_id: f"{token_id}.{secret}" for token_id, secret in DEFAULT_SERVICE_TOKEN_SECRETS.items()
}
DEFAULT_AUTH_SERVICE_TOKENS = (
    {
        "token_id": "reader-token",
        "secret_digest": "5f2a948f1a0f51d636721e4381eaf64fc8032a03b540a12da0645e0edc564084",
        "scopes": ["read"],
        "active": True,
    },
    {
        "token_id": "publisher-token",
        "secret_digest": "99e880bea53395534bf471d5d086ac2b2f6d45c6fe7c6c9ac7f6225cbe19c559",
        "scopes": ["read", "publish"],
        "active": True,
    },
    {
        "token_id": "admin-token",
        "secret_digest": "f0f642b692ba908c91a9afe3c53878700b32e66c8132fc071109b4af48625d46",
        "scopes": ["read", "publish", "admin"],
        "active": True,
    },
)


def _database_is_available(database_url: str) -> bool:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
    finally:
        engine.dispose()


def _reset_database(database_url: str) -> None:
    """Drop and recreate the public schema for a clean integration DB."""
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
            connection.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
            connection.execute(text("GRANT ALL ON SCHEMA public TO public"))
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Generator[None, None, None]:
    """Ensure tests never share cached settings state."""
    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.fixture(autouse=True)
def default_auth_service_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide explicit governed service tokens for all tests exercising HTTP routes."""
    monkeypatch.setenv(
        "AUTH_SERVICE_TOKENS_JSON",
        json.dumps(DEFAULT_AUTH_SERVICE_TOKENS),
    )
    monkeypatch.setenv("ALLOWED_HOSTS_JSON", json.dumps(DEFAULT_ALLOWED_HOSTS))
    monkeypatch.setenv("SEMANTIC_DISCOVERY_MODE", "off")


@pytest.fixture(autouse=True)
def dummy_settings_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point settings loading at a test-owned dotenv file."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"DATABASE_URL={DEFAULT_TEST_DATABASE_URL}",
                f"AUTH_SERVICE_TOKENS_JSON={json.dumps(DEFAULT_AUTH_SERVICE_TOKENS)}",
                f"ALLOWED_HOSTS_JSON={json.dumps(DEFAULT_ALLOWED_HOSTS)}",
                "APP_ENV=prod",
                "LOG_LEVEL=DEBUG",
                "APP_NAME=aptitude-test",
                "SEMANTIC_DISCOVERY_MODE=off",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(SETTINGS_ENV_FILE_ENV_VAR, str(env_file))
    return env_file


@pytest.fixture(scope="session")
def integration_database_url() -> str:
    """Return a PostgreSQL URL used by integration tests."""
    return os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)


@pytest.fixture(scope="session")
def require_integration_database(integration_database_url: str) -> str:
    """Skip integration tests when PostgreSQL is not reachable."""
    if not _database_is_available(integration_database_url):
        pytest.skip(
            "PostgreSQL is not reachable for integration tests. "
            "Run `make test` or set TEST_DATABASE_URL to a reachable test database.",
        )
    return integration_database_url


@pytest.fixture
def clean_integration_database(require_integration_database: str) -> Generator[str, None, None]:
    """Provide a blank Postgres schema for integration tests."""
    _reset_database(require_integration_database)
    yield require_integration_database
    dispose_engine()
    reset_settings_cache()
    _reset_database(require_integration_database)


def _build_alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture
def migrated_integration_database(clean_integration_database: str) -> str:
    """Provide a blank Postgres schema upgraded to the latest Alembic revision."""
    command.upgrade(_build_alembic_config(clean_integration_database), "head")
    return clean_integration_database


@pytest.fixture
def migrated_registry_database(migrated_integration_database: str) -> str:
    """Compatibility alias for integration tests that expect the older fixture name."""
    return migrated_integration_database
