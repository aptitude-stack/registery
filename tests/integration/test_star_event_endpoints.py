"""Integration tests for the aggregate star-events telemetry endpoint."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import DEFAULT_AUTH_SERVICE_TOKENS
from tests.integration.skill_endpoint_helpers import (
    _headers,
    _publish,
    _request,
    _token_record,
)

TELEMETRY_TOKEN_ID = "telemetry-token"
TELEMETRY_TOKEN_SECRET = "dev-telemetry-secret"
TELEMETRY_BEARER = f"{TELEMETRY_TOKEN_ID}.{TELEMETRY_TOKEN_SECRET}"


def _telemetry_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TELEMETRY_BEARER}"}


def _set_telemetry_token(monkeypatch: pytest.MonkeyPatch) -> None:
    token_records = [
        *DEFAULT_AUTH_SERVICE_TOKENS,
        _token_record(
            token_id=TELEMETRY_TOKEN_ID,
            secret=TELEMETRY_TOKEN_SECRET,
            scopes=["telemetry"],
            namespace_grants=[],
        ),
    ]
    monkeypatch.setenv("AUTH_SERVICE_TOKENS_JSON", json.dumps(token_records))


@pytest.mark.integration
def test_star_events_apply_deltas_and_clamp_at_zero(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    _set_telemetry_token(monkeypatch)
    suffix = uuid4().hex
    slug_lint = f"python.lint-{suffix}"
    slug_test = f"python.test-{suffix}"

    with TestClient(create_app()) as client:
        _publish(
            client,
            slug_lint,
            _request("1.0.0", intent="create_skill", name="Lint", description="Lint skill"),
        )
        _publish(
            client,
            slug_test,
            _request("1.0.0", intent="create_skill", name="Test", description="Test skill"),
        )

        first = client.post(
            "/catalog/star-events",
            json={
                "events": [
                    {"slug": slug_lint, "action": "star"},
                    {"slug": slug_test, "action": "star"},
                    {"slug": slug_lint, "action": "star"},
                ]
            },
            headers=_telemetry_headers(),
        )
        clamping = client.post(
            "/catalog/star-events",
            json={
                "events": [
                    {"slug": slug_test, "action": "unstar"},
                    {"slug": slug_test, "action": "unstar"},
                ]
            },
            headers=_telemetry_headers(),
        )
        metadata_lint = client.get(
            f"/skills/{slug_lint}/1.0.0",
            headers=_headers("reader-token"),
        )
        metadata_test = client.get(
            f"/skills/{slug_test}/1.0.0",
            headers=_headers("reader-token"),
        )

    assert first.status_code == 200, first.text
    body = first.json()
    assert body["accepted"] == 3
    counts = {entry["slug"]: entry["star_count"] for entry in body["counts"]}
    assert counts == {slug_lint: 2, slug_test: 1}

    assert clamping.status_code == 200, clamping.text
    clamped = {entry["slug"]: entry["star_count"] for entry in clamping.json()["counts"]}
    assert clamped == {slug_test: 0}

    assert metadata_lint.status_code == 200
    assert metadata_lint.json()["star_count"] == 2
    assert metadata_test.status_code == 200
    assert metadata_test.json()["star_count"] == 0


@pytest.mark.integration
def test_star_events_reject_unknown_slug_without_committing(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    _set_telemetry_token(monkeypatch)
    suffix = uuid4().hex
    slug = f"python.lint-{suffix}"
    missing = f"python.missing-{suffix}"

    with TestClient(create_app()) as client:
        _publish(
            client,
            slug,
            _request("1.0.0", intent="create_skill", name="Lint", description="Lint skill"),
        )

        response = client.post(
            "/catalog/star-events",
            json={
                "events": [
                    {"slug": slug, "action": "star"},
                    {"slug": missing, "action": "star"},
                ]
            },
            headers=_telemetry_headers(),
        )
        metadata = client.get(
            f"/skills/{slug}/1.0.0",
            headers=_headers("reader-token"),
        )

    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "STAR_EVENT_UNKNOWN_SKILL"
    assert response.json()["error"]["details"]["slugs"] == [missing]
    # No partial commit: the published skill stays at zero.
    assert metadata.status_code == 200
    assert metadata.json()["star_count"] == 0


@pytest.mark.integration
def test_star_events_require_telemetry_scope(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    _set_telemetry_token(monkeypatch)
    suffix = uuid4().hex
    slug = f"python.lint-{suffix}"

    with TestClient(create_app()) as client:
        _publish(
            client,
            slug,
            _request("1.0.0", intent="create_skill", name="Lint", description="Lint skill"),
        )

        unauthenticated = client.post(
            "/catalog/star-events",
            json={"events": [{"slug": slug, "action": "star"}]},
        )
        wrong_scope = client.post(
            "/catalog/star-events",
            json={"events": [{"slug": slug, "action": "star"}]},
            headers=_headers("reader-token"),
        )
        admin_allowed = client.post(
            "/catalog/star-events",
            json={"events": [{"slug": slug, "action": "star"}]},
            headers=_headers("admin-token"),
        )

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert wrong_scope.status_code == 403
    assert wrong_scope.json()["error"]["code"] == "INSUFFICIENT_SCOPE"
    # Admin tokens carry every scope and are intentionally allowed for tooling/break-glass.
    assert admin_allowed.status_code == 200, admin_allowed.text


@pytest.mark.integration
def test_star_events_validate_request_shape(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    _set_telemetry_token(monkeypatch)

    with TestClient(create_app()) as client:
        empty_batch = client.post(
            "/catalog/star-events",
            json={"events": []},
            headers=_telemetry_headers(),
        )
        bad_action = client.post(
            "/catalog/star-events",
            json={"events": [{"slug": "python.lint", "action": "favorite"}]},
            headers=_telemetry_headers(),
        )
        bad_slug = client.post(
            "/catalog/star-events",
            json={"events": [{"slug": "***bad***", "action": "star"}]},
            headers=_telemetry_headers(),
        )

    assert empty_batch.status_code == 422
    assert empty_batch.json()["error"]["code"] == "INVALID_REQUEST"
    assert bad_action.status_code == 422
    assert bad_action.json()["error"]["code"] == "INVALID_REQUEST"
    assert bad_slug.status_code == 422
    assert bad_slug.json()["error"]["code"] == "INVALID_REQUEST"
