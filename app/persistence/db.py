"""Database engine, session lifecycle, and readiness checks."""

from __future__ import annotations

from threading import Lock

from sqlalchemy import create_engine, text
from sqlalchemy import types as sqltypes
from sqlalchemy.dialects.postgresql.base import ischema_names
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.ports import DatabaseReadinessPort


class ReflectedHalfVec(sqltypes.UserDefinedType[tuple[float, ...]]):
    """Reflection-only SQLAlchemy type for pgvector halfvec columns."""

    cache_ok = True

    def __init__(self, dimensions: str | int | None = None) -> None:
        self.dimensions = int(dimensions) if dimensions is not None else None

    def get_col_spec(self, **_: object) -> str:
        if self.dimensions is None:
            return "halfvec"
        return f"halfvec({self.dimensions})"


ischema_names.setdefault("halfvec", ReflectedHalfVec)

_ENGINE: Engine | None = None
_SESSION_FACTORY: sessionmaker[Session] | None = None
_ENGINE_LOCK = Lock()


def init_engine(
    database_url: str,
    *,
    application_name: str | None = None,
    connect_timeout_seconds: int = 5,
) -> None:
    """Initialize the shared SQLAlchemy engine/session factory.

    `application_name` is forwarded to libpq via psycopg's connect_args so the
    connection identity surfaces in the database server (e.g. Neon Console
    "Active Connections", `pg_stat_activity.application_name`).
    """
    global _ENGINE, _SESSION_FACTORY

    with _ENGINE_LOCK:
        if _ENGINE is not None and str(_ENGINE.url) == database_url:
            return

        if _ENGINE is not None:
            _ENGINE.dispose()

        connect_args: dict[str, str | int] = {"connect_timeout": connect_timeout_seconds}
        if application_name is not None:
            connect_args["application_name"] = application_name

        _ENGINE = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args=connect_args,
        )
        _SESSION_FACTORY = sessionmaker(
            bind=_ENGINE,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )


def get_engine() -> Engine | None:
    """Return the current shared engine if initialized."""
    return _ENGINE


def dispose_engine() -> None:
    """Dispose the shared SQLAlchemy engine."""
    global _ENGINE, _SESSION_FACTORY

    with _ENGINE_LOCK:
        if _ENGINE is not None:
            _ENGINE.dispose()

        _ENGINE = None
        _SESSION_FACTORY = None


def get_session_factory() -> sessionmaker[Session]:
    """Return initialized process session factory."""
    if _SESSION_FACTORY is None:
        raise RuntimeError("Database engine is not initialized.")
    return _SESSION_FACTORY


class SQLAlchemyDatabaseReadinessProbe(DatabaseReadinessPort):
    """Persistence adapter for database readiness checks."""

    def ping(self) -> tuple[bool, str | None]:
        """Execute a cheap probe query to verify DB readiness."""
        if _ENGINE is None:
            return False, "Database engine is not initialized."

        try:
            with _ENGINE.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True, None
        except SQLAlchemyError as exc:
            return False, str(exc)
