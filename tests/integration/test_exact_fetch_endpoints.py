"""Integration tests for exact fetch endpoints."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.integration.skill_endpoint_helpers import (
    _headers,
    _publish,
    _query_install_counts,
    _request,
)


@pytest.mark.integration
def test_content_fetch_increments_aggregate_install_count(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python.install-count.{uuid4().hex}"

    with TestClient(create_app()) as client:
        published = _publish(client, slug, _request("1.0.0", intent="create_skill"))
        initial_metadata = client.get(
            f"/skills/{slug}/1.0.0",
            headers=_headers("reader-token"),
        )
        content = client.get(
            f"/skills/{slug}/1.0.0/content",
            headers=_headers("reader-token"),
        )
        updated_metadata = client.get(
            f"/skills/{slug}/1.0.0",
            headers=_headers("reader-token"),
        )

    counts = _query_install_counts(migrated_registry_database, slug=slug)

    assert published["install_count"] == 0
    assert initial_metadata.status_code == 200
    assert initial_metadata.json()["install_count"] == 0
    assert content.status_code == 200
    assert updated_metadata.status_code == 200
    assert updated_metadata.json()["install_count"] == 1
    assert counts == {
        "skill_install_count": 1,
        "min_usage_count": 1,
        "max_usage_count": 1,
    }


@pytest.mark.integration
def test_exact_fetch_returns_not_found_for_missing_coordinates(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)

    with TestClient(create_app()) as client:
        metadata = client.get(
            "/skills/python.missing/9.9.9",
            headers=_headers("reader-token"),
        )
        content = client.get(
            "/skills/python.missing/9.9.9/content",
            headers=_headers("reader-token"),
        )

    assert metadata.status_code == 404
    assert metadata.json()["error"]["code"] == "SKILL_VERSION_NOT_FOUND"
    assert content.status_code == 404
    assert content.json()["error"]["code"] == "SKILL_VERSION_NOT_FOUND"


