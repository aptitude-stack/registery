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
    version_filter = "" if version is None else "AND skill_versions.version = :version"
    parameters = {
        "slug": slug,
        "install_count": install_count,
        "published_at": published_at,
    }
    if version is not None:
        parameters["version"] = version
    try:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE skills SET install_count = :install_count WHERE slug = :slug"),
                {"slug": slug, "install_count": install_count},
            )
            connection.execute(
                text(
                    f"""
                    UPDATE skill_versions
                    SET published_at = :published_at
                    FROM skills
                    WHERE skills.id = skill_versions.skill_fk
                      AND skills.slug = :slug
                      {version_filter}
                    """
                ),
                parameters,
            )
            connection.execute(
                text(
                    f"""
                    UPDATE skill_search_documents
                    SET usage_count = :install_count,
                        published_at = :published_at
                    FROM skill_versions
                    JOIN skills ON skills.id = skill_versions.skill_fk
                    WHERE skill_versions.id = skill_search_documents.skill_version_fk
                      AND skills.slug = :slug
                      {version_filter}
                    """
                ),
                parameters,
            )
    finally:
        engine.dispose()


@pytest.mark.integration
def test_content_fetch_increments_aggregate_install_count(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python-install-count-{uuid4().hex}"

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
    assert published["star_count"] == 0
    assert initial_metadata.status_code == 200
    assert initial_metadata.json()["install_count"] == 0
    assert initial_metadata.json()["star_count"] == 0
    assert content.status_code == 200
    assert updated_metadata.status_code == 200
    assert updated_metadata.json()["install_count"] == 1
    assert updated_metadata.json()["star_count"] == 0
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
            "/skills/python-missing/9.9.9",
            headers=_headers("reader-token"),
        )
        content = client.get(
            "/skills/python-missing/9.9.9/content",
            headers=_headers("reader-token"),
        )

    assert metadata.status_code == 404
    assert metadata.json()["error"]["code"] == "SKILL_VERSION_NOT_FOUND"
    assert content.status_code == 404
    assert content.json()["error"]["code"] == "SKILL_VERSION_NOT_FOUND"


@pytest.mark.integration
def test_publish_and_exact_fetch_return_overall_score_without_search_projection(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python-overall-score-{uuid4().hex}"

    with TestClient(create_app()) as client:
        published = _publish(
            client,
            slug,
            _request("1.0.0", intent="create_skill", overall_score=0.87),
        )
        exact = client.get(f"/skills/{slug}/1.0.0", headers=_headers("reader-token"))
        search = client.post(
            "/catalog/search?limit=20",
            json={"query": "Python Lint"},
            headers=_headers("reader-token"),
        )

    assert published["metadata"]["overall_score"] == 0.87
    assert exact.status_code == 200
    assert exact.json()["metadata"]["overall_score"] == 0.87
    assert search.status_code == 200
    matching = [item for item in search.json()["skills"] if item["slug"] == slug]
    assert matching
    assert "overall_score" not in matching[0]["metadata"]


@pytest.mark.integration
def test_top_installed_skills_returns_visible_current_defaults_in_rank_order(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    prefix = f"python-top-{uuid4().hex}"
    alpha = f"{prefix}-alpha"
    beta = f"{prefix}-beta"
    hidden = f"{prefix}-hidden"
    tie_a = f"{prefix}-tie-a"
    tie_b = f"{prefix}-tie-b"

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


@pytest.mark.integration
def test_catalog_skills_returns_all_visible_current_defaults_ordered_by_installs(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    prefix = f"python-catalog-all-{uuid4().hex}"
    alpha = f"{prefix}-alpha"
    beta = f"{prefix}-beta"
    gamma = f"{prefix}-gamma"
    hidden = f"{prefix}-hidden"

    with TestClient(create_app()) as client:
        _publish(client, alpha, _request("1.0.0", intent="create_skill", name="Alpha"))
        _publish(client, beta, _request("1.0.0", intent="create_skill", name="Beta"))
        _publish(client, gamma, _request("1.0.0", intent="create_skill", name="Gamma"))
        _publish(client, hidden, _request("1.0.0", intent="create_skill", name="Hidden"))
        _update_status(client, slug=hidden, version="1.0.0", status="archived")

        _set_rank_fixture(
            migrated_registry_database,
            slug=alpha,
            install_count=3,
            published_at="2026-03-12T09:00:00+00:00",
        )
        _set_rank_fixture(
            migrated_registry_database,
            slug=beta,
            install_count=5,
            published_at="2026-03-13T09:00:00+00:00",
        )
        _set_rank_fixture(
            migrated_registry_database,
            slug=gamma,
            install_count=1,
            published_at="2026-03-14T09:00:00+00:00",
        )
        _set_rank_fixture(
            migrated_registry_database,
            slug=hidden,
            install_count=99,
            published_at="2026-03-15T09:00:00+00:00",
        )

        response = client.get("/catalog/skills", headers=_headers("reader-token"))

    assert response.status_code == 200
    body = response.json()
    slugs = [item["slug"] for item in body["skills"]]
    matching_slugs = [slug for slug in slugs if slug.startswith(prefix)]
    assert matching_slugs == [beta, alpha, gamma]
    assert hidden not in slugs


@pytest.mark.integration
def test_skill_graph_returns_visible_current_defaults_and_safe_authored_edges(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    prefix = f"python-skill-graph-{uuid4().hex}"
    source = f"{prefix}-source"
    target = f"{prefix}-target"
    overlap = f"{prefix}-overlap"
    hidden = f"{prefix}-hidden"
    outside = f"{prefix}-outside"

    with TestClient(create_app()) as client:
        _publish(client, target, _request("1.0.0", intent="create_skill", name="Target"))
        _publish(client, overlap, _request("1.0.0", intent="create_skill", name="Overlap"))
        _publish(client, hidden, _request("1.0.0", intent="create_skill", name="Hidden"))
        _publish(client, outside, _request("1.0.0", intent="create_skill", name="Outside"))
        _publish(
            client,
            source,
            _request(
                "1.0.0",
                intent="create_skill",
                name="Source",
                depends_on=[{"slug": target, "version_constraint": ">=1.0.0"}],
                extends=[{"slug": overlap, "version": "1.0.0"}],
                conflicts_with=[{"slug": target, "version": "1.0.0"}],
                overlaps_with=[
                    {"slug": hidden, "version": "1.0.0"},
                    {"slug": outside, "version": "1.0.0"},
                ],
            ),
        )
        _publish(
            client,
            source,
            _request(
                "1.1.0",
                intent="publish_version",
                name="Source",
                depends_on=[{"slug": target, "version_constraint": ">=1.0.0"}],
                extends=[{"slug": overlap, "version": "1.0.0"}],
            ),
        )
        _update_status(client, slug=hidden, version="1.0.0", status="archived")

        _set_rank_fixture(
            migrated_registry_database,
            slug=source,
            install_count=30,
            published_at="2026-03-13T09:00:00+00:00",
            version="1.0.0",
        )
        _set_rank_fixture(
            migrated_registry_database,
            slug=source,
            install_count=30,
            published_at="2026-03-14T09:00:00+00:00",
            version="1.1.0",
        )
        _set_rank_fixture(
            migrated_registry_database,
            slug=target,
            install_count=20,
            published_at="2026-03-13T09:00:00+00:00",
        )
        _set_rank_fixture(
            migrated_registry_database,
            slug=overlap,
            install_count=10,
            published_at="2026-03-12T09:00:00+00:00",
        )
        _set_rank_fixture(
            migrated_registry_database,
            slug=hidden,
            install_count=9,
            published_at="2026-03-11T09:00:00+00:00",
        )
        _set_rank_fixture(
            migrated_registry_database,
            slug=outside,
            install_count=1,
            published_at="2026-03-10T09:00:00+00:00",
        )

        response = client.get(
            "/catalog/skill-graph?limit=3",
            headers=_headers("reader-token"),
        )
        invalid = client.get(
            "/catalog/skill-graph?limit=25",
            headers=_headers("reader-token"),
        )

    assert response.status_code == 200
    body = response.json()
    assert [(item["slug"], item["version"]) for item in body["nodes"]] == [
        (source, "1.1.0"),
        (target, "1.0.0"),
        (overlap, "1.0.0"),
    ]
    assert body["edges"] == [
        {
            "source_slug": source,
            "target_slug": target,
            "edge_type": "depends_on",
            "provenance": "authored",
            "confidence": None,
        },
        {
            "source_slug": source,
            "target_slug": overlap,
            "edge_type": "extends",
            "provenance": "authored",
            "confidence": None,
        },
    ]
    assert invalid.status_code == 422


@pytest.mark.integration
def test_co_usage_import_creates_and_deactivates_relates_to_graph_edges(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    monkeypatch.setenv("CO_USAGE_RELATES_TO_WINDOW_DAYS", "90")
    prefix = f"python-co-usage-graph-{uuid4().hex}"
    source = f"{prefix}-source"
    target = f"{prefix}-target"
    other = f"{prefix}-other"

    with TestClient(create_app()) as client:
        _publish(client, source, _request("1.0.0", intent="create_skill", name="Source"))
        _publish(client, target, _request("1.0.0", intent="create_skill", name="Target"))
        _publish(client, other, _request("1.0.0", intent="create_skill", name="Other"))
        _set_rank_fixture(
            migrated_registry_database,
            slug=source,
            install_count=30,
            published_at="2026-03-14T09:00:00+00:00",
        )
        _set_rank_fixture(
            migrated_registry_database,
            slug=target,
            install_count=20,
            published_at="2026-03-13T09:00:00+00:00",
        )
        _set_rank_fixture(
            migrated_registry_database,
            slug=other,
            install_count=1,
            published_at="2026-03-12T09:00:00+00:00",
        )

        summaries = [
            client.post(
                "/admin/co-usage/observation-runs",
                json={
                    "source": "resolver",
                    "source_digest": f"{index:064x}",
                    "observed_at": f"2026-03-{index + 1:02d}T12:00:00Z",
                    "skill_slugs": [source, target],
                },
                headers=_headers("admin-token"),
            )
            for index in range(3)
        ]
        background = client.post(
            "/admin/co-usage/observation-runs",
            json={
                "source": "resolver",
                "source_digest": f"{10:064x}",
                "observed_at": "2026-03-04T12:00:00Z",
                "skill_slugs": [other],
            },
            headers=_headers("admin-token"),
        )
        duplicate = client.post(
            "/admin/co-usage/observation-runs",
            json={
                "source": "resolver",
                "source_digest": f"{2:064x}",
                "observed_at": "2026-03-03T12:00:00Z",
                "skill_slugs": [source, target],
            },
            headers=_headers("admin-token"),
        )
        graph = client.get("/catalog/skill-graph?limit=2", headers=_headers("reader-token"))

        stale = client.post(
            "/admin/co-usage/observation-runs",
            json={
                "source": "resolver",
                "source_digest": f"{99:064x}",
                "observed_at": "2026-07-01T12:00:00Z",
                "skill_slugs": [source],
            },
            headers=_headers("admin-token"),
        )
        degraded_graph = client.get(
            "/catalog/skill-graph?limit=2",
            headers=_headers("reader-token"),
        )

    assert [response.status_code for response in summaries] == [200, 200, 200]
    assert background.status_code == 200
    assert background.json()["edges_activated"] == 1
    assert duplicate.status_code == 200
    assert duplicate.json()["imported"] is False
    assert duplicate.json()["duplicate"] is True
    assert graph.status_code == 200
    assert graph.json()["edges"] == [
        {
            "source_slug": source,
            "target_slug": target,
            "edge_type": "relates_to",
            "provenance": "co_usage",
            "confidence": 1.0,
        }
    ]
    assert stale.status_code == 200
    assert stale.json()["edges_deactivated"] == 1
    assert degraded_graph.status_code == 200
    assert degraded_graph.json()["edges"] == []


@pytest.mark.integration
def test_co_usage_import_rejects_unknown_observed_skill(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python-co-usage-unknown-{uuid4().hex}"

    with TestClient(create_app()) as client:
        _publish(client, slug, _request("1.0.0", intent="create_skill"))
        response = client.post(
            "/admin/co-usage/observation-runs",
            json={
                "source": "resolver",
                "source_digest": f"{1:064x}",
                "observed_at": "2026-03-01T12:00:00Z",
                "skill_slugs": [slug, f"{slug}-missing"],
            },
            headers=_headers("admin-token"),
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNKNOWN_CO_USAGE_SKILL"


@pytest.mark.integration
def test_catalog_search_returns_visible_current_default_metadata_in_discovery_order(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    prefix = f"python-catalog-search-{uuid4().hex}"
    alpha = f"{prefix}-alpha"
    beta = f"{prefix}-beta"
    hidden = f"{prefix}-hidden"
    request_body = {"query": "Catalog Search", "tags": [prefix]}

    with TestClient(create_app()) as client:
        _publish(
            client,
            alpha,
            _request(
                "1.0.0",
                intent="create_skill",
                name="Catalog Search",
                tags=[prefix, "search"],
            ),
        )
        _publish(
            client,
            alpha,
            _request(
                "2.0.0",
                intent="publish_version",
                name="Catalog Search",
                tags=[prefix, "search"],
            ),
        )
        _publish(
            client,
            beta,
            _request(
                "1.0.0",
                intent="create_skill",
                name="Catalog Search",
                tags=[prefix, "search"],
            ),
        )
        _publish(
            client,
            hidden,
            _request(
                "1.0.0",
                intent="create_skill",
                name="Catalog Search",
                tags=[prefix, "search"],
            ),
        )
        _update_status(client, slug=hidden, version="1.0.0", status="archived")

        _set_rank_fixture(
            migrated_registry_database,
            slug=beta,
            install_count=15,
            published_at="2026-03-12T09:00:00+00:00",
        )
        _set_rank_fixture(
            migrated_registry_database,
            slug=alpha,
            version="1.0.0",
            install_count=10,
            published_at="2026-03-12T09:00:00+00:00",
        )
        _set_rank_fixture(
            migrated_registry_database,
            slug=alpha,
            version="2.0.0",
            install_count=10,
            published_at="2026-03-13T09:00:00+00:00",
        )
        _set_rank_fixture(
            migrated_registry_database,
            slug=hidden,
            install_count=20,
            published_at="2026-03-14T09:00:00+00:00",
        )

        response = client.post(
            "/catalog/search?limit=2",
            json=request_body,
            headers=_headers("reader-token"),
        )
        invalid = client.post(
            "/catalog/search?limit=21",
            json=request_body,
            headers=_headers("reader-token"),
        )
        discovery = client.post(
            "/discovery",
            json=request_body,
            headers=_headers("reader-token"),
        )

    assert response.status_code == 200
    body = response.json()
    assert [(item["slug"], item["version"]) for item in body["skills"]] == [
        (beta, "1.0.0"),
        (alpha, "2.0.0"),
    ]
    assert hidden not in [item["slug"] for item in body["skills"]]
    assert invalid.status_code == 422
    assert discovery.status_code == 200
    assert isinstance(discovery.json()["candidates"][0], str)


@pytest.mark.integration
def test_exact_slug_discovery_and_catalog_search_ignore_mismatched_required_tags(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python-patterns-{uuid4().hex}"
    request_body = {"query": slug, "tags": [slug]}

    with TestClient(create_app()) as client:
        _publish(
            client,
            slug,
            _request(
                "0.1.0",
                intent="create_skill",
                raw_markdown="# Python Patterns\n\nIdiomatic Python development patterns.\n",
                name=slug,
                description="Pythonic idioms and refactoring guidance.",
                tags=["python", "patterns", "refactoring"],
            ),
        )

        discovery = client.post(
            "/discovery",
            json=request_body,
            headers=_headers("reader-token"),
        )
        catalog_search = client.post(
            "/catalog/search",
            json=request_body,
            headers=_headers("reader-token"),
        )

    assert discovery.status_code == 200
    assert discovery.json()["candidates"][0] == slug
    assert catalog_search.status_code == 200
    assert catalog_search.json()["skills"][0]["slug"] == slug


@pytest.mark.integration
@pytest.mark.parametrize("query_word", ["docs", "documentation", "writing"])
def test_catalog_search_word_queries_return_expected_documentation_card(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
    query_word: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)

    with TestClient(create_app()) as client:
        _publish(
            client,
            "documentation-writing",
            _request(
                "1.0.0",
                intent="create_skill",
                raw_markdown="# Documentation Writing\n\nWrite docs, guides, and references.\n",
                name="Documentation Writing",
                description="Write documentation, docs, guides, and API references.",
                tags=["documentation", "docs", "writing"],
            ),
        )
        response = client.post(
            "/catalog/search",
            json={"query": query_word},
            headers=_headers("reader-token"),
        )

    assert response.status_code == 200
    assert "documentation-writing" in [item["slug"] for item in response.json()["skills"]]
