"""Migration database URL selection and safety checks."""

from __future__ import annotations

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def is_neon_pooler_url(database_url: str) -> bool:
    """Return whether the URL points at a Neon pooled endpoint."""
    try:
        host = make_url(database_url).host or ""
    except ArgumentError:
        return False
    return "-pooler" in host


def select_migration_database_url(
    *,
    configured_url: str | None,
    migration_database_url: str | None,
    database_url: str,
) -> str:
    """Return the URL Alembic should use for migrations.

    Explicit Alembic config remains the top-priority override for local tests
    and one-off operator commands. The environment-level migration URL must be
    direct, not pooled, because Alembic uses transactional DDL and connection
    semantics that should not run through PgBouncer.
    """
    selected_url = configured_url or migration_database_url or database_url
    if is_neon_pooler_url(selected_url):
        raise ValueError("Alembic migrations must use a direct Neon host, not a pooler host.")
    return selected_url
