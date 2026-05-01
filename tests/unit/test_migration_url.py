"""Unit tests for migration database URL selection."""

from __future__ import annotations

import pytest

from app.persistence.migration_url import select_migration_database_url


@pytest.mark.unit
def test_migration_url_prefers_explicit_alembic_config() -> None:
    assert (
        select_migration_database_url(
            configured_url="postgresql+psycopg://explicit:pw@127.0.0.1/db",
            migration_database_url="postgresql+psycopg://migration:pw@direct.neon.tech/db",
            database_url="postgresql+psycopg://runtime:pw@pooler.neon.tech/db",
        )
        == "postgresql+psycopg://explicit:pw@127.0.0.1/db"
    )


@pytest.mark.unit
def test_migration_url_prefers_dedicated_migration_url() -> None:
    assert (
        select_migration_database_url(
            configured_url=None,
            migration_database_url="postgresql+psycopg://migration:pw@ep-direct.us-east-1.aws.neon.tech/db",
            database_url="postgresql+psycopg://runtime:pw@ep-direct-pooler.us-east-1.aws.neon.tech/db",
        )
        == "postgresql+psycopg://migration:pw@ep-direct.us-east-1.aws.neon.tech/db"
    )


@pytest.mark.unit
def test_migration_url_falls_back_to_runtime_database_url() -> None:
    assert (
        select_migration_database_url(
            configured_url=None,
            migration_database_url=None,
            database_url="postgresql+psycopg://runtime:pw@127.0.0.1/db",
        )
        == "postgresql+psycopg://runtime:pw@127.0.0.1/db"
    )


@pytest.mark.unit
def test_migration_url_rejects_neon_pooler_migration_url() -> None:
    with pytest.raises(ValueError, match="direct Neon host"):
        select_migration_database_url(
            configured_url=None,
            migration_database_url=(
                "postgresql+psycopg://migration:pw@ep-direct-pooler.us-east-1.aws.neon.tech/db"
            ),
            database_url="postgresql+psycopg://runtime:pw@127.0.0.1/db",
        )


@pytest.mark.unit
def test_migration_url_rejects_neon_pooler_explicit_config() -> None:
    with pytest.raises(ValueError, match="direct Neon host"):
        select_migration_database_url(
            configured_url=(
                "postgresql+psycopg://explicit:pw@ep-direct-pooler.us-east-1.aws.neon.tech/db"
            ),
            migration_database_url="postgresql+psycopg://migration:pw@ep-direct.us-east-1.aws.neon.tech/db",
            database_url="postgresql+psycopg://runtime:pw@127.0.0.1/db",
        )


@pytest.mark.unit
def test_migration_url_rejects_neon_pooler_runtime_fallback() -> None:
    with pytest.raises(ValueError, match="direct Neon host"):
        select_migration_database_url(
            configured_url=None,
            migration_database_url=None,
            database_url=(
                "postgresql+psycopg://runtime:pw@ep-direct-pooler.us-east-1.aws.neon.tech/db"
            ),
        )
