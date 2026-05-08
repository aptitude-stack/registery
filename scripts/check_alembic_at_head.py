"""Verify that the configured database is at the repository Alembic head."""

from __future__ import annotations

import sys
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.settings import get_settings, reset_settings_cache  # noqa: E402
from app.persistence.migration_url import select_migration_database_url  # noqa: E402


def _configured_database_url(config: Config) -> str | None:
    configured_url = config.get_main_option("sqlalchemy.url")
    if configured_url is None:
        return None
    configured_url = configured_url.strip()
    return configured_url or None


def main() -> int:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)
    expected_heads = set(script.get_heads())

    reset_settings_cache()
    settings = get_settings()
    database_url = select_migration_database_url(
        configured_url=_configured_database_url(config),
        migration_database_url=settings.migration_database_url,
        database_url=settings.database_url,
    )

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            current_heads = set(MigrationContext.configure(connection).get_current_heads())
    finally:
        engine.dispose()

    if current_heads != expected_heads:
        print(
            "Alembic head mismatch: "
            f"database={sorted(current_heads) or ['<base>']} "
            f"repo={sorted(expected_heads)}",
            file=sys.stderr,
        )
        return 1

    print(f"Alembic at head: {', '.join(sorted(expected_heads))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
