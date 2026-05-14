"""Integration tests for exact fetch endpoints."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import create_app
from tests.integration.skill_endpoint_helpers import (
    _headers,
    _publish,
    _query_install_counts,
    _request,
    _update_status,
)


def _set_rank_fixture(
    database_url: str,
    *,
    slug: str,
    install_count: int,
    published_at: str,
    version: str | None = None,
) -> None:
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE skills SET install_count = :install_count WHERE slug = :slug"),
                {"slug": slug, "install_count": install_count},
            )
            connection.execute(
                text(
                    """
                    UPDATE skill_versions
                    SET published_at = :published_at
                    FROM skills
                    WHERE skills.id = skill_versions.skill_fk
                      AND skills.slug = :slug
                      AND (:version IS NULL OR skill_versions.version = :version)
                    """
                ),
                {"slug": slug, "published_at": published_at, "version": version},
            )
            connection.execute(
                text(
                    """
                    UPDATE skill_search_documents
                    SET usage_count = :install_count,
                        published_at = :published_at
                    FROM skill_versions
                    JOIN skills ON skills.id = skill_versions.skill_fk
                    WHERE skill_versions.id = skill_search_documents.skill_version_fk
                      AND skills.slug = :slug
                      AND (:version IS NULL OR skill_versions.version = :version)
                    """
                ),
                {
                    "slug": slug,
                    "install_count": install_count,
                    "published_at": published_at,
                    "version": version,
                },
            )
    finally:
        engine.dispose()


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


@pytest.mark.integration
def test_top_installed_skills_returns_visible_current_defaults_in_rank_order(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    prefix = f"python.top.{uuid4().hex}"
    alpha = f"{prefix}.alpha"
    beta = f"{prefix}.beta"
    hidden = f"{prefix}.hidden"
    tie_a = f"{prefix}.tie-a"
    tie_b = f"{prefix}.tie-b"

    with TestClient(create_app()) as client:
        _publish(client, alpha, _request("1.0.0", intent="create_skill", name="Alpha"))
        _publish(client, alpha, _request("2.0.0", intent="publish_version", name="Alpha"))
        _publish(client, beta, _request("1.0.0", intent="create_skill", name="Beta"))
        _publish(client, hidden, _request("1.0.0", intent="create_skill", name="Hidden"))
        _publish(client, tie_a, _request("1.0.0", intent="create_skill", name="Tie A"))
        _publish(client, tie_b, _request("1.0.0", intent="create_skill", name="Tie B"))
        _update_status(client, slug=hidden, version="1.0.0", status="archived")

        _set_rank_fixture(
            migrated_registry_database,
            slug=alpha,
            install_count=12,
            version="1.0.0",
            published_at="2026-03-12T09:00:00+00:00",
        )
        _set_rank_fixture(
            migrated_registry_database,
            slug=alpha,
            install_count=12,
            version="2.0.0",
            published_at="2026-03-13T09:00:00+00:00",
        )
        _set_rank_fixture(
            migrated_registry_database,
            slug=hidden,
            install_count=11,
            published_at="2026-03-14T09:00:00+00:00",
        )
        _set_rank_fixture(
            migrated_registry_database,
            slug=beta,
            install_count=10,
            published_at="2026-03-14T09:00:00+00:00",
        )
        _set_rank_fixture(
            migrated_registry_database,
            slug=tie_b,
            install_count=7,
            published_at="2026-03-12T09:00:00+00:00",
        )
        _set_rank_fixture(
            migrated_registry_database,
            slug=tie_a,
            install_count=7,
            published_at="2026-03-12T09:00:00+00:00",
        )

        response = client.get(
            "/catalog/top-skills?limit=4",
            headers=_headers("reader-token"),
        )
        invalid = client.get(
            "/catalog/top-skills?limit=25",
            headers=_headers("reader-token"),
        )

    assert response.status_code == 200
    body = response.json()
    assert [item["slug"] for item in body["skills"]] == [alpha, beta, tie_a, tie_b]
    assert body["skills"][0]["version"] == "2.0.0"
    assert hidden not in [item["slug"] for item in body["skills"]]
    assert invalid.status_code == 422
