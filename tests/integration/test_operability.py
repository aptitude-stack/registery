"""Integration coverage for metrics, request correlation, and audit stitching."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import create_app


def _headers(token: str, *, request_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if request_id is not None:
        headers["X-Request-ID"] = request_id
    return headers


def _request(version: str) -> dict[str, object]:
    return {
        "intent": "create_skill",
        "version": version,
        "content": {"raw_markdown": "# Python Lint\n\nLint Python files.\n"},
        "metadata": {
            "name": "Python Lint",
            "description": "Linting skill",
            "tags": ["python", "lint"],
            "inputs_schema": {"type": "object"},
            "outputs_schema": {"type": "object"},
            "token_estimate": 128,
            "maturity_score": 0.9,
            "security_score": 0.95,
        },
        "governance": {"trust_tier": "untrusted", "provenance": None},
        "relationships": {
            "depends_on": [],
            "extends": [],
            "conflicts_with": [],
            "overlaps_with": [],
        },
    }


def _query_audit_events(database_url: str) -> list[dict[str, Any]]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return [
                {"event_type": str(row["event_type"]), "payload": row["payload"]}
                for row in connection.execute(
                    text("SELECT event_type, payload FROM audit_events ORDER BY id")
                ).mappings()
            ]
    finally:
        engine.dispose()


@pytest.mark.integration
def test_metrics_endpoint_is_unauthenticated_and_exposes_prometheus_payload(
    monkeypatch: pytest.MonkeyPatch,
    require_integration_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", require_integration_database)

    with TestClient(create_app()) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "aptitude_http_requests_total" in response.text


@pytest.mark.integration
def test_request_id_is_echoed_on_success_and_error_responses(
    monkeypatch: pytest.MonkeyPatch,
    require_integration_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", require_integration_database)

    with TestClient(create_app()) as client:
        success = client.get("/healthz", headers={"X-Request-ID": "req-health"})
        error = client.post(
            "/discovery",
            json={"name": "Python Lint"},
            headers={"X-Request-ID": "req-error"},
        )

    assert success.status_code == 200
    assert success.headers["X-Request-ID"] == "req-health"
    assert error.status_code == 401
    assert error.headers["X-Request-ID"] == "req-error"


@pytest.mark.integration
def test_readyz_initializes_database_readiness_metric(
    monkeypatch: pytest.MonkeyPatch,
    require_integration_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", require_integration_database)

    with TestClient(create_app()) as client:
        readyz = client.get("/readyz")
        metrics = client.get("/metrics")

    assert readyz.status_code == 200
    assert 'aptitude_readiness_status{dependency="database"} 1.0' in metrics.text


@pytest.mark.integration
def test_publish_flow_stitches_request_id_into_audit_rows_and_metrics(
    monkeypatch: pytest.MonkeyPatch,
    migrated_integration_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_integration_database)
    slug = f"python.operability.{uuid4().hex}"

    with TestClient(create_app()) as client:
        publish = client.post(
            f"/skills/{slug}",
            json=_request("1.0.0"),
            headers=_headers("publisher-token", request_id="req-publish"),
        )
        metrics = client.get("/metrics")

    audit_events = _query_audit_events(migrated_integration_database)

    assert publish.status_code == 201, publish.text
    assert publish.headers["X-Request-ID"] == "req-publish"
    assert any(
        event["payload"] is not None and event["payload"].get("request_id") == "req-publish"
        for event in audit_events
    )
    assert "aptitude_registry_operation_total" in metrics.text


@pytest.mark.integration
def test_structured_request_logs_capture_surface_outcome_and_error_code(
    monkeypatch: pytest.MonkeyPatch,
    require_integration_database: str,
    tmp_path,
) -> None:
    monkeypatch.setenv("DATABASE_URL", require_integration_database)
    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path / "app.jsonl"))

    with TestClient(create_app()) as client:
        response = client.post(
            "/discovery",
            json={"name": "Python Lint"},
            headers={"X-Request-ID": "req-log-shape"},
        )

    assert response.status_code == 401

    log_lines = [
        json.loads(line)
        for line in (tmp_path / "app.jsonl").read_text().splitlines()
        if line.strip()
    ]
    request_log = next(
        payload
        for payload in log_lines
        if payload.get("event_type") == "request.completed"
        and payload.get("request_id") == "req-log-shape"
    )

    assert request_log["http_method"] == "POST"
    assert request_log["http_route"] == "/discovery"
    assert request_log["status_code"] == 401
    assert request_log["surface"] == "discovery"
    assert request_log["outcome"] == "client_error"
    assert request_log["error_code"] == "AUTHENTICATION_REQUIRED"
    assert request_log["client_ip"] == "testclient"
    assert "user_agent" in request_log
