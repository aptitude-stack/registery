"""Integration tests for the registry API surface."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text

from alembic import command
from app.main import create_app
from app.persistence.db import get_session_factory


@pytest.fixture
def migrated_registry_database(clean_integration_database: str) -> str:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", clean_integration_database)
    command.upgrade(config, "head")
    return clean_integration_database


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _request(
    version: str,
    *,
    intent: str = "create_skill",
    raw_markdown: str = "# Python Lint\n\nLint Python files.\n",
    name: str = "Python Lint",
    description: str = "Linting skill",
    tags: list[str] | None = None,
    trust_tier: str = "untrusted",
    provenance: dict[str, str] | None = None,
    depends_on: list[dict[str, object]] | None = None,
    extends: list[dict[str, object]] | None = None,
    conflicts_with: list[dict[str, object]] | None = None,
    overlaps_with: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "intent": intent,
        "version": version,
        "content": {
            "raw_markdown": raw_markdown,
        },
        "metadata": {
            "name": name,
            "description": description,
            "tags": tags or ["python", "lint"],
            "inputs_schema": {"type": "object"},
            "outputs_schema": {"type": "object"},
            "token_estimate": 128,
            "maturity_score": 0.9,
            "security_score": 0.95,
        },
        "governance": {
            "trust_tier": trust_tier,
            "provenance": provenance,
        },
        "relationships": {
            "depends_on": depends_on or [],
            "extends": extends or [],
            "conflicts_with": conflicts_with or [],
            "overlaps_with": overlaps_with or [],
        },
    }


def _publish(
    client: TestClient,
    slug: str,
    payload: dict[str, object],
    *,
    token: str = "publisher-token",
) -> dict[str, object]:
    response = client.post(f"/skills/{slug}", json=payload, headers=_headers(token))
    assert response.status_code == 201, response.text
    return response.json()


def _update_status(
    client: TestClient,
    *,
    slug: str,
    version: str,
    status: str,
    token: str = "admin-token",
    note: str | None = None,
) -> dict[str, object]:
    response = client.patch(
        f"/skills/{slug}/{version}/status",
        json={"status": status, "note": note},
        headers=_headers(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _query_storage_counts(database_url: str, *, slug: str) -> dict[str, int]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        """
                        SELECT
                            COUNT(*) AS version_count,
                            COUNT(DISTINCT skill_versions.content_fk) AS distinct_content_fk_count
                        FROM skill_versions
                        JOIN skills ON skills.id = skill_versions.skill_fk
                        WHERE skills.slug = :slug
                        """
                    ),
                    {"slug": slug},
                )
                .mappings()
                .one()
            )
            content_count = connection.execute(
                text("SELECT COUNT(*) FROM skill_contents")
            ).scalar_one()
            return {
                "version_count": int(row["version_count"]),
                "distinct_content_fk_count": int(row["distinct_content_fk_count"]),
                "content_count": int(content_count),
            }
    finally:
        engine.dispose()


def _query_install_counts(database_url: str, *, slug: str) -> dict[str, int]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        """
                        SELECT
                            skills.install_count AS skill_install_count,
                            COALESCE(MIN(skill_search_documents.usage_count), 0) AS min_usage_count,
                            COALESCE(MAX(skill_search_documents.usage_count), 0) AS max_usage_count
                        FROM skills
                        LEFT JOIN skill_versions
                            ON skill_versions.skill_fk = skills.id
                        LEFT JOIN skill_search_documents
                            ON skill_search_documents.skill_version_fk = skill_versions.id
                        WHERE skills.slug = :slug
                        GROUP BY skills.install_count
                        """
                    ),
                    {"slug": slug},
                )
                .mappings()
                .one()
            )
            return {
                "skill_install_count": int(row["skill_install_count"]),
                "min_usage_count": int(row["min_usage_count"]),
                "max_usage_count": int(row["max_usage_count"]),
            }
    finally:
        engine.dispose()


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
def test_publish_discovery_resolution_and_exact_fetch(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    suffix = uuid4().hex
    dependency_slug = f"python.dep.{suffix}"
    source_slug = f"python.source.{suffix}"

    with TestClient(create_app()) as client:
        _publish(
            client,
            dependency_slug,
            _request(
                "1.0.0",
                intent="create_skill",
                name="Python Dependency",
                description="Base dependency",
            ),
        )
        published = _publish(
            client,
            source_slug,
            _request(
                "2.0.0",
                intent="create_skill",
                raw_markdown="# v2\n",
                name="Python Hard Cut Source",
                description="Hard cut discovery candidate",
                tags=["python", "lint", "hard-cut"],
                trust_tier="internal",
                provenance={
                    "repo_url": "https://github.com/example/skills",
                    "commit_sha": "aabbccddeeff00112233445566778899aabbccdd",
                    "tree_path": f"skills/{source_slug}",
                    "publisher_identity": "ci/example-release",
                },
                depends_on=[{"slug": dependency_slug, "version": "1.0.0"}],
                extends=[{"slug": "python.base", "version": "1.0.0"}],
            ),
        )

        discovery = client.post(
            "/discovery",
            json={
                "name": "  Python Hard Cut Source  ",
                "description": "  Hard cut discovery candidate  ",
                "tags": ["python", "hard-cut", "python"],
            },
            headers=_headers("reader-token"),
        )
        resolution = client.get(
            f"/resolution/{source_slug}/2.0.0",
            headers=_headers("reader-token"),
        )
        versions = client.get(
            f"/skills/{source_slug}",
            headers=_headers("reader-token"),
        )
        metadata = client.get(
            f"/skills/{source_slug}/2.0.0",
            headers=_headers("reader-token"),
        )
        content = client.get(
            f"/skills/{source_slug}/2.0.0/content",
            headers=_headers("reader-token"),
        )

    assert "relationships" not in published
    assert "content_download_path" not in published
    assert "rendered_summary" not in published["content"]
    assert "headers" not in published["metadata"]
    assert published["install_count"] == 0

    assert discovery.status_code == 200
    assert discovery.json()["candidates"] == [source_slug]

    assert resolution.status_code == 200
    resolution_body = resolution.json()
    assert resolution_body == {
        "slug": source_slug,
        "version": "2.0.0",
        "depends_on": [
            {
                "slug": dependency_slug,
                "version": "1.0.0",
                "version_constraint": None,
                "optional": None,
                "markers": [],
            }
        ],
    }

    assert versions.status_code == 200
    assert versions.json() == {
        "slug": source_slug,
        "versions": [
            {
                "version": "2.0.0",
                "lifecycle_status": "published",
                "trust_tier": "internal",
                "published_at": published["published_at"],
                "is_current_default": True,
            }
        ],
    }

    assert metadata.status_code == 200
    metadata_body = metadata.json()
    assert "headers" not in metadata_body["metadata"]
    assert metadata_body["slug"] == source_slug
    assert metadata_body["version"] == "2.0.0"
    assert "relationships" not in metadata_body
    assert "content_download_path" not in metadata_body
    assert "rendered_summary" not in metadata_body["content"]
    assert metadata_body["install_count"] == 0
    assert metadata_body["provenance"] == {
        "repo_url": "https://github.com/example/skills",
        "commit_sha": "aabbccddeeff00112233445566778899aabbccdd",
        "tree_path": f"skills/{source_slug}",
        "publisher_identity": "ci/example-release",
        "trust_context": {
            "trust_tier": "internal",
            "policy_profile": "default",
        },
    }
    assert published["provenance"] == metadata_body["provenance"]

    assert content.status_code == 200
    assert content.headers["content-type"].startswith("text/markdown; charset=utf-8")
    assert content.headers["ETag"] == published["content"]["checksum"]["digest"]
    assert content.headers["Cache-Control"] == "public, immutable"
    assert content.headers["Content-Length"] == str(len(b"# v2\n"))
    assert content.text == "# v2\n"


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
def test_publish_rejects_rendered_summary_field(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)

    with TestClient(create_app()) as client:
        payload = _request("1.0.0")
        payload["content"]["rendered_summary"] = "Legacy summary field"

        response = client.post(
            "/skills/python.legacy-summary",
            json=payload,
            headers=_headers("publisher-token"),
        )

    assert response.status_code == 422, response.text


@pytest.mark.integration
def test_publish_rejects_metadata_headers_field(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)

    with TestClient(create_app()) as client:
        payload = _request("1.0.0")
        payload["metadata"]["headers"] = {"runtime": "python"}

        response = client.post(
            "/skills/python.legacy-headers",
            json=payload,
            headers=_headers("publisher-token"),
        )

    assert response.status_code == 422, response.text


@pytest.mark.integration
def test_publish_reuses_digest_backed_content_rows_for_identical_content(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python.dedup.{uuid4().hex}"

    with TestClient(create_app()) as client:
        first = _publish(
            client,
            slug,
            _request(
                "1.0.0",
                intent="create_skill",
                raw_markdown="# Shared Content\n",
                description="First publish of shared content",
            ),
        )
        second = _publish(
            client,
            slug,
            _request(
                "2.0.0",
                intent="publish_version",
                raw_markdown="# Shared Content\n",
                description="Second publish of shared content",
            ),
        )

    counts = _query_storage_counts(migrated_registry_database, slug=slug)

    assert first["content"]["checksum"]["digest"] == second["content"]["checksum"]["digest"]
    assert first["version_checksum"]["digest"] != second["version_checksum"]["digest"]
    assert first["provenance"] is None
    assert second["provenance"] is None
    assert counts == {
        "version_count": 2,
        "distinct_content_fk_count": 1,
        "content_count": 1,
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
def test_publish_distinct_content_creates_distinct_rows_and_exact_fetch_returns_markdown(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python.distinct.{uuid4().hex}"

    with TestClient(create_app()) as client:
        first = _publish(
            client,
            slug,
            _request(
                "1.0.0",
                intent="create_skill",
                raw_markdown="# v1\n",
                description="First distinct version",
            ),
        )
        second = _publish(
            client,
            slug,
            _request(
                "2.0.0",
                intent="publish_version",
                raw_markdown="# v2\n",
                description="Second distinct version",
            ),
        )
        response = client.get(
            f"/skills/{slug}/2.0.0/content",
            headers=_headers("reader-token"),
        )

    counts = _query_storage_counts(migrated_registry_database, slug=slug)
    assert response.status_code == 200
    assert first["content"]["checksum"]["digest"] != second["content"]["checksum"]["digest"]
    assert counts == {
        "version_count": 2,
        "distinct_content_fk_count": 2,
        "content_count": 2,
    }
    assert response.headers["ETag"] == second["content"]["checksum"]["digest"]
    assert response.text == "# v2\n"


@pytest.mark.integration
def test_authentication_and_scope_failures_are_enforced(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python.auth.{uuid4().hex}"
    payload = _request("1.0.0", intent="create_skill")

    with TestClient(create_app()) as client:
        missing = client.post(f"/skills/{slug}", json=payload)
        invalid = client.post(
            f"/skills/{slug}",
            json=payload,
            headers=_headers("not-a-real-token"),
        )
        insufficient = client.post(
            f"/skills/{slug}",
            json=payload,
            headers=_headers("reader-token"),
        )
        discovery_missing = client.post(
            "/discovery",
            json={"name": "Python Lint"},
        )

    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "INVALID_AUTH_TOKEN"
    assert insufficient.status_code == 403
    assert insufficient.json()["error"]["code"] == "INSUFFICIENT_SCOPE"
    assert discovery_missing.status_code == 401
    assert discovery_missing.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.integration
def test_publish_enforces_trust_tier_policy(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    suffix = uuid4().hex

    with TestClient(create_app()) as client:
        internal_without_provenance = client.post(
            f"/skills/python.internal.{suffix}",
            json=_request("1.0.0", trust_tier="internal"),
            headers=_headers("publisher-token"),
        )
        verified_without_admin = client.post(
            f"/skills/python.verified.{suffix}",
            json=_request(
                "1.0.0",
                intent="create_skill",
                trust_tier="verified",
                provenance={
                    "repo_url": "https://github.com/example/skills",
                    "commit_sha": "aabbccddeeff00112233445566778899aabbccdd",
                    "tree_path": "skills/python.verified",
                },
            ),
            headers=_headers("publisher-token"),
        )
        verified_with_admin = client.post(
            f"/skills/python.verified-admin.{suffix}",
            json=_request(
                "1.0.0",
                intent="create_skill",
                trust_tier="verified",
                provenance={
                    "repo_url": "https://github.com/example/skills",
                    "commit_sha": "bbccddeeff00112233445566778899aabbccdde0",
                    "tree_path": "skills/python.verified-admin",
                },
            ),
            headers=_headers("admin-token"),
        )

    assert internal_without_provenance.status_code == 403
    assert internal_without_provenance.json()["error"]["code"] == "POLICY_PROVENANCE_REQUIRED"
    assert verified_without_admin.status_code == 403
    assert verified_without_admin.json()["error"]["code"] == "POLICY_PUBLISH_FORBIDDEN"
    assert verified_with_admin.status_code == 201
    assert verified_with_admin.json()["trust_tier"] == "verified"


@pytest.mark.integration
def test_status_transitions_recompute_current_default(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python.lifecycle.{uuid4().hex}"

    with TestClient(create_app()) as client:
        _publish(client, slug, _request("1.0.0", intent="create_skill"))
        _publish(client, slug, _request("2.0.0", intent="publish_version"))

        deprecated = _update_status(client, slug=slug, version="2.0.0", status="deprecated")
        archived = _update_status(client, slug=slug, version="1.0.0", status="archived")
        invalid_transition = client.patch(
            f"/skills/{slug}/1.0.0/status",
            json={"status": "published"},
            headers=_headers("admin-token"),
        )

    assert deprecated["status"] == "deprecated"
    assert deprecated["is_current_default"] is False
    assert archived["status"] == "archived"
    assert archived["is_current_default"] is False
    assert invalid_transition.status_code == 403
    assert invalid_transition.json()["error"]["code"] == "POLICY_STATUS_TRANSITION_FORBIDDEN"


@pytest.mark.integration
def test_version_list_and_status_update_use_same_default_ordering(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python.default-ordering.{uuid4().hex}"

    with TestClient(create_app()) as client:
        _publish(client, slug, _request("1.0.0", intent="create_skill"))
        _publish(client, slug, _request("2.0.0", intent="publish_version"))

    engine = create_engine(migrated_registry_database)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE skill_versions
                    SET published_at = TIMESTAMP WITH TIME ZONE '2026-03-10 08:30:00+00'
                    WHERE skill_fk = (SELECT id FROM skills WHERE slug = :slug)
                    """
                ),
                {"slug": slug},
            )
    finally:
        engine.dispose()

    with TestClient(create_app()) as client:
        _update_status(client, slug=slug, version="1.0.0", status="deprecated")
        status_update = _update_status(client, slug=slug, version="2.0.0", status="deprecated")
        versions = client.get(f"/skills/{slug}", headers=_headers("reader-token"))

    assert status_update["is_current_default"] is False
    assert versions.status_code == 200
    assert versions.json()["versions"][0]["version"] == "1.0.0"
    assert versions.json()["versions"][0]["is_current_default"] is True


@pytest.mark.integration
def test_governance_applies_to_discovery_resolution_and_exact_fetch(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    suffix = uuid4().hex
    published_slug = f"python.discovery.published.{suffix}"
    deprecated_slug = f"python.discovery.deprecated.{suffix}"
    archived_slug = f"python.discovery.archived.{suffix}"
    internal_slug = f"python.discovery.internal.{suffix}"

    with TestClient(create_app()) as client:
        _publish(
            client,
            published_slug,
            _request(
                "1.0.0",
                intent="create_skill",
                name="Python Discovery Published",
                description="Published discovery candidate",
            ),
        )
        _publish(
            client,
            deprecated_slug,
            _request(
                "1.0.0",
                intent="create_skill",
                name="Python Discovery Deprecated",
                description="Deprecated discovery candidate",
            ),
        )
        _publish(
            client,
            archived_slug,
            _request(
                "1.0.0",
                intent="create_skill",
                name="Python Discovery Archived",
                description="Archived discovery candidate",
            ),
        )
        _publish(
            client,
            internal_slug,
            _request(
                "1.0.0",
                intent="create_skill",
                name="Python Discovery Internal",
                description="Internal discovery candidate",
                trust_tier="internal",
                provenance={
                    "repo_url": "https://github.com/example/skills",
                    "commit_sha": "ddeeff00112233445566778899aabbccddeeff00",
                    "tree_path": f"skills/{internal_slug}",
                },
            ),
        )

        _update_status(client, slug=deprecated_slug, version="1.0.0", status="deprecated")
        _update_status(client, slug=archived_slug, version="1.0.0", status="archived")

        published_discovery = client.post(
            "/discovery",
            json={"name": "Python Discovery"},
            headers=_headers("reader-token"),
        )
        archived_resolution_forbidden = client.get(
            f"/resolution/{archived_slug}/1.0.0",
            headers=_headers("reader-token"),
        )
        archived_resolution_admin = client.get(
            f"/resolution/{archived_slug}/1.0.0",
            headers=_headers("admin-token"),
        )
        archived_versions_forbidden = client.get(
            f"/skills/{archived_slug}",
            headers=_headers("reader-token"),
        )
        archived_versions_admin = client.get(
            f"/skills/{archived_slug}",
            headers=_headers("admin-token"),
        )
        archived_metadata_forbidden = client.get(
            f"/skills/{archived_slug}/1.0.0",
            headers=_headers("reader-token"),
        )
        archived_metadata_admin = client.get(
            f"/skills/{archived_slug}/1.0.0",
            headers=_headers("admin-token"),
        )
        archived_content_forbidden = client.get(
            f"/skills/{archived_slug}/1.0.0/content",
            headers=_headers("reader-token"),
        )
        archived_content_admin = client.get(
            f"/skills/{archived_slug}/1.0.0/content",
            headers=_headers("admin-token"),
        )

    assert published_discovery.status_code == 200
    assert set(published_discovery.json()["candidates"]) == {
        published_slug,
        internal_slug,
    }
    assert deprecated_slug not in published_discovery.json()["candidates"]
    assert archived_slug not in published_discovery.json()["candidates"]

    assert archived_resolution_forbidden.status_code == 403
    assert archived_resolution_forbidden.json()["error"]["code"] == "POLICY_EXACT_READ_FORBIDDEN"
    assert archived_resolution_admin.status_code == 200
    assert archived_resolution_admin.json()["slug"] == archived_slug

    assert archived_versions_forbidden.status_code == 404
    assert archived_versions_forbidden.json()["error"]["code"] == "SKILL_NOT_FOUND"
    assert archived_versions_admin.status_code == 200
    assert archived_versions_admin.json()["versions"] == [
        {
            "version": "1.0.0",
            "lifecycle_status": "archived",
            "trust_tier": "untrusted",
            "published_at": archived_versions_admin.json()["versions"][0]["published_at"],
            "is_current_default": False,
        }
    ]

    assert archived_metadata_forbidden.status_code == 403
    assert archived_metadata_forbidden.json()["error"]["code"] == "POLICY_EXACT_READ_FORBIDDEN"
    assert archived_metadata_admin.status_code == 200
    assert archived_metadata_admin.json()["slug"] == archived_slug

    assert archived_content_forbidden.status_code == 403
    assert archived_content_forbidden.json()["error"]["code"] == "POLICY_EXACT_READ_FORBIDDEN"
    assert archived_content_admin.status_code == 200
    assert archived_content_admin.text.startswith("# Python Lint")


@pytest.mark.integration
def test_discovery_queries_search_documents_without_touching_skill_contents(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python.discovery.metadata-only.{uuid4().hex}"

    with TestClient(create_app()) as client:
        _publish(
            client,
            slug,
            _request(
                "1.0.0",
                intent="create_skill",
                raw_markdown="# Metadata Only Discovery\n",
                name="Metadata Only Discovery",
                description="Search document should satisfy discovery",
            ),
        )

        engine = get_session_factory().kw["bind"]
        executed_selects: list[str] = []

        def _capture_selects(
            _conn: Any,
            _cursor: Any,
            statement: str,
            _parameters: Any,
            _context: Any,
            _executemany: bool,
        ) -> None:
            normalized_statement = " ".join(statement.split())
            if normalized_statement.upper().startswith(("SELECT", "WITH")):
                executed_selects.append(normalized_statement)

        event.listen(engine, "before_cursor_execute", _capture_selects)
        try:
            response = client.post(
                "/discovery",
                json={"name": "Metadata Only Discovery"},
                headers=_headers("reader-token"),
            )
        finally:
            event.remove(engine, "before_cursor_execute", _capture_selects)

    assert response.status_code == 200
    assert response.json()["candidates"] == [slug]
    assert any("skill_search_documents" in statement for statement in executed_selects)
    assert all("skill_contents" not in statement for statement in executed_selects)


@pytest.mark.integration
def test_publish_rejects_invalid_dependency_constraint(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python.invalid.{uuid4().hex}"

    with TestClient(create_app()) as client:
        response = client.post(
            f"/skills/{slug}",
            json=_request(
                "1.0.0",
                intent="create_skill",
                depends_on=[{"slug": "python.base", "version_constraint": "latest"}],
            ),
            headers=_headers("publisher-token"),
        )

    assert response.status_code == 422


@pytest.mark.integration
def test_publish_backfills_normalized_search_documents_with_governance(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python.searchdoc.{uuid4().hex}"

    with TestClient(create_app()) as client:
        _publish(
            client,
            slug,
            _request(
                "1.0.0",
                intent="create_skill",
                raw_markdown="# Search Doc\n",
                trust_tier="internal",
                provenance={
                    "repo_url": "https://github.com/example/skills",
                    "commit_sha": "ccddeeff00112233445566778899aabbccddeeff",
                    "tree_path": f"skills/{slug}",
                },
            ),
        )

    engine = create_engine(migrated_registry_database)
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        """
                        SELECT
                            slug,
                            normalized_slug,
                            content_size_bytes,
                            lifecycle_status,
                            trust_tier
                        FROM skill_search_documents
                        WHERE slug = :slug
                        """
                    ),
                    {"slug": slug},
                )
                .mappings()
                .one()
            )
            assert row["slug"] == slug
            assert row["normalized_slug"] == slug
            assert row["content_size_bytes"] == len(b"# Search Doc\n")
            assert row["lifecycle_status"] == "published"
            assert row["trust_tier"] == "internal"
    finally:
        engine.dispose()


@pytest.mark.integration
def test_publish_intent_requires_existing_or_missing_slug_as_declared(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python.intent.{uuid4().hex}"

    with TestClient(create_app()) as client:
        create_skill = client.post(
            f"/skills/{slug}",
            json=_request("1.0.0", intent="create_skill"),
            headers=_headers("publisher-token"),
        )
        create_again = client.post(
            f"/skills/{slug}",
            json=_request("2.0.0", intent="create_skill"),
            headers=_headers("publisher-token"),
        )
        publish_existing = client.post(
            f"/skills/{slug}",
            json=_request("2.0.0", intent="publish_version"),
            headers=_headers("publisher-token"),
        )
        publish_missing = client.post(
            f"/skills/{slug}.missing",
            json=_request("1.0.0", intent="publish_version"),
            headers=_headers("publisher-token"),
        )

    assert create_skill.status_code == 201
    assert create_again.status_code == 409
    assert create_again.json()["error"]["code"] == "SKILL_ALREADY_EXISTS"
    assert publish_existing.status_code == 201
    assert publish_missing.status_code == 404
    assert publish_missing.json()["error"]["code"] == "SKILL_NOT_FOUND"


@pytest.mark.integration
def test_audit_events_cover_publish_discovery_exact_reads_and_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python.audit.{uuid4().hex}"

    with TestClient(create_app()) as client:
        publish_response = client.post(
            f"/skills/{slug}",
            json=_request(
                "1.0.0",
                intent="create_skill",
                trust_tier="internal",
                provenance={
                    "repo_url": "https://github.com/example/skills",
                    "commit_sha": "0123456789abcdef0123456789abcdef01234567",
                    "tree_path": f"skills/{slug}",
                    "publisher_identity": "ci/example-release",
                },
            ),
            headers=_headers("publisher-token"),
        )
        denied_publish = client.post(
            f"/skills/{slug}.policy",
            json=_request("1.0.0", trust_tier="internal"),
            headers=_headers("publisher-token"),
        )
        discovery = client.post(
            "/discovery",
            json={"name": "Python Lint"},
            headers=_headers("reader-token"),
        )
        resolution = client.get(
            f"/resolution/{slug}/1.0.0",
            headers=_headers("reader-token"),
        )
        versions = client.get(
            f"/skills/{slug}",
            headers=_headers("reader-token"),
        )
        metadata = client.get(
            f"/skills/{slug}/1.0.0",
            headers=_headers("reader-token"),
        )
        content = client.get(
            f"/skills/{slug}/1.0.0/content",
            headers=_headers("reader-token"),
        )
        archived = client.patch(
            f"/skills/{slug}/1.0.0/status",
            json={"status": "archived"},
            headers=_headers("admin-token"),
        )
        denied_status = client.patch(
            f"/skills/{slug}/1.0.0/status",
            json={"status": "published"},
            headers=_headers("admin-token"),
        )
        denied_metadata = client.get(
            f"/skills/{slug}/1.0.0",
            headers=_headers("reader-token"),
        )

    assert publish_response.status_code == 201
    assert denied_publish.status_code == 403
    assert discovery.status_code == 200
    assert resolution.status_code == 200
    assert versions.status_code == 200
    assert metadata.status_code == 200
    assert content.status_code == 200
    assert archived.status_code == 200
    assert denied_status.status_code == 403
    assert denied_metadata.status_code == 403

    audit_events = _query_audit_events(migrated_registry_database)
    event_types = [event["event_type"] for event in audit_events]

    assert "skill.version_published" in event_types
    assert "skill.version_publish_denied" in event_types
    assert "skill.search_performed" in event_types
    assert "skill.version_resolution_read" in event_types
    assert "skill.version_list_read" in event_types
    assert "skill.version_metadata_read" in event_types
    assert "skill.version_content_read" in event_types
    assert "skill.version_status_updated" in event_types
    assert "skill.version_status_update_denied" in event_types
    assert "skill.version_exact_read_denied" in event_types

    publish_event = next(
        event for event in audit_events if event["event_type"] == "skill.version_published"
    )
    denied_publish_event = next(
        event for event in audit_events if event["event_type"] == "skill.version_publish_denied"
    )
    denied_read_event = next(
        event for event in audit_events if event["event_type"] == "skill.version_exact_read_denied"
    )

    assert publish_event["payload"]["publisher_identity"] == "ci/example-release"
    assert publish_event["payload"]["policy_profile_at_publish"] == "default"
    assert denied_publish_event["payload"]["reason_code"] == "POLICY_PROVENANCE_REQUIRED"
    assert denied_read_event["payload"]["surface"] == "metadata"
