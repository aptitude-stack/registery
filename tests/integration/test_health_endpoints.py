"""Integration coverage for health and readiness endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.mark.integration
def test_healthz_returns_expected_payload(
    monkeypatch: pytest.MonkeyPatch,
    require_integration_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", require_integration_database)
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("APP_NAME", "aptitude-test")

    with TestClient(create_app()) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "aptitude-test",
        "environment": "prod",
    }


@pytest.mark.integration
def test_readyz_returns_200_when_database_is_reachable(
    monkeypatch: pytest.MonkeyPatch,
    require_integration_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", require_integration_database)

    with TestClient(create_app()) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"][0]["name"] == "database"
    assert body["checks"][0]["status"] == "ok"


@pytest.mark.integration
def test_readyz_returns_503_when_database_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        ("postgresql+psycopg://postgres:postgres@127.0.0.1:65432/aptitude?connect_timeout=1"),
    )

    with TestClient(create_app()) as client:
        response = client.get("/readyz")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"][0]["name"] == "database"
    assert body["checks"][0]["status"] == "error"
