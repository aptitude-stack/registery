"""Alembic migration environment wiring.

This module connects Alembic to the application's SQLAlchemy metadata and
resolves the database URL used during migration runs.

URL resolution order:
1. ``sqlalchemy.url`` from ``alembic.ini`` (explicit migration override)
2. ``migration_database_url`` from application settings (direct migration URL)
3. ``database_url`` from application settings (environment-driven fallback)
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.settings import get_settings, reset_settings_cache
from app.persistence.migration_url import select_migration_database_url

# Import all mapped tables so they are registered on Base.metadata.
from app.persistence.models import (
    audit_event,  # noqa: F401
    skill,  # noqa: F401
    skill_content,  # noqa: F401
    skill_metadata,  # noqa: F401
    skill_relationship_selector,  # noqa: F401
    skill_search_document,  # noqa: F401
    skill_version,  # noqa: F401
)
from app.persistence.models.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic autogenerate compares migration state against this metadata object.
target_metadata = Base.metadata


def get_database_url() -> str:
    """Return the database URL used for the current migration run.

    Preference is given to Alembic's ``sqlalchemy.url`` so operators can point
    migrations to a specific database without changing app settings. If not
    configured, use the dedicated migration URL before falling back to the
    runtime database URL.
    """
    configured_url = config.get_main_option("sqlalchemy.url")
    if configured_url:
        return configured_url

    # Ensure settings reflect current environment variables for migration runs.
    reset_settings_cache()
    settings = get_settings()
    return select_migration_database_url(
        configured_url=None,
        migration_database_url=settings.migration_database_url,
        database_url=settings.database_url,
    )


def run_migrations_offline() -> None:
    """Run migrations in offline mode (emit SQL without a DB connection).

    ``literal_binds=True`` renders SQL with concrete values, which is useful
    when generating scripts with ``alembic upgrade --sql``.
    """
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode (connect to the target database).

    Uses ``NullPool`` so migration connections are short-lived and not reused
    across runs.
    """
    alembic_section = config.get_section(config.config_ini_section) or {}
    alembic_section["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        alembic_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
