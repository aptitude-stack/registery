"""Unit tests for database engine wiring."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.engine import make_url

from app.persistence import db


class _FakeEngine:
    def __init__(self, database_url: str) -> None:
        self.url = make_url(database_url)
        self.disposed = False

    def dispose(self) -> None:
        self.disposed = True


@pytest.mark.unit
def test_init_engine_configures_runtime_pooling(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_create_engine(database_url: str, **kwargs: Any) -> _FakeEngine:
        captured["database_url"] = database_url
        captured["kwargs"] = kwargs
        return _FakeEngine(database_url)

    db.dispose_engine()
    monkeypatch.setattr(db, "create_engine", fake_create_engine)

    database_url = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude"
    db.init_engine(
        database_url,
        application_name="aptitude-registry-prod",
        connect_timeout_seconds=7,
    )

    assert captured["database_url"] == database_url
    assert captured["kwargs"]["pool_pre_ping"] is True
    assert captured["kwargs"]["pool_recycle"] == 300
    assert captured["kwargs"]["connect_args"] == {
        "application_name": "aptitude-registry-prod",
        "connect_timeout": 7,
    }

    db.dispose_engine()
