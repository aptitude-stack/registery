"""Integration tests for publish endpoints."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.skills.bundle_archive import MAX_SKILL_BUNDLE_SIZE_BYTES
from app.main import create_app
from tests.integration.skill_endpoint_helpers import (
    _bundle,
    _headers,
    _publish,
    _publish_response,
    _query_storage_counts,
    _request,
)


@pytest.mark.integration
def test_publish_starts_embedding_workflow_after_storage(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    started: list[None] = []
    monkeypatch.setattr(
        "app.interface.api.skills.start_semantic_embedding_workflow",
        lambda: started.append(None),
    )
    slug = f"python-embedding-trigger-{uuid4().hex}"

    with TestClient(create_app()) as client:
        response = _publish_response(client, slug, _request("1.0.0"))

    assert response.status_code == 201
    assert started == [None]
    assert _query_storage_counts(migrated_registry_database, slug=slug)["version_count"] == 1


@pytest.mark.integration
def test_publish_returns_created_when_embedding_workflow_start_fails(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)

    def fail_to_start() -> None:
        raise RuntimeError("Render unavailable")

    monkeypatch.setattr(
        "app.interface.api.skills.start_semantic_embedding_workflow",
        fail_to_start,
    )
    logged: list[str] = []
    monkeypatch.setattr(
        "app.interface.api.skills.logger.exception",
        lambda message, **_kwargs: logged.append(message),
    )
    slug = f"python-embedding-trigger-failure-{uuid4().hex}"

    with TestClient(create_app()) as client:
        response = _publish_response(client, slug, _request("1.0.0"))

    assert response.status_code == 201
    assert logged == ["failed to start semantic embedding workflow"]
    assert _query_storage_counts(migrated_registry_database, slug=slug)["version_count"] == 1


@pytest.mark.integration
def test_publish_rejects_rendered_summary_field(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)

    with TestClient(create_app()) as client:
        payload = _request("1.0.0")
        payload["content"] = {"raw_markdown": "# Python Lint\n"}

        response = _publish_response(client, "python-legacy-summary", payload)

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

        response = _publish_response(client, "python-legacy-headers", payload)

    assert response.status_code == 422, response.text


@pytest.mark.integration
def test_publish_reuses_digest_backed_content_rows_for_identical_content(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python-dedup-{uuid4().hex}"

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
def test_publish_distinct_content_creates_distinct_rows_and_exact_fetch_returns_bundle(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python-distinct-{uuid4().hex}"

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
    assert response.content == _bundle("# v2\n")


@pytest.mark.integration
def test_authentication_and_scope_failures_are_enforced(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python-auth-{uuid4().hex}"
    payload = _request("1.0.0", intent="create_skill")

    with TestClient(create_app()) as client:
        missing = _publish_response(client, slug, payload, token=None)
        malformed = _publish_response(client, slug, payload, token="not-a-real-token")
        invalid = _publish_response(
            client,
            slug,
            payload,
            token="unknown-token.dev-reader-secret",
        )
        insufficient = _publish_response(client, slug, payload, token="reader-token")
        discovery_missing = client.post(
            "/discovery",
            json={"query": "Python Lint"},
        )

    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert malformed.status_code == 401
    assert malformed.json()["error"]["code"] == "MALFORMED_AUTH_TOKEN"
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
        internal_without_provenance = _publish_response(
            client,
            f"python-internal-{suffix}",
            _request("1.0.0", trust_tier="internal"),
        )
        verified_without_admin = _publish_response(
            client,
            f"python-verified-{suffix}",
            _request(
                "1.0.0",
                intent="create_skill",
                trust_tier="verified",
                provenance={
                    "repo_url": "https://github.com/example/skills",
                    "commit_sha": "aabbccddeeff00112233445566778899aabbccdd",
                    "tree_path": "skills/python-verified",
                },
            ),
        )
        verified_with_admin = _publish_response(
            client,
            f"python-verified-admin-{suffix}",
            _request(
                "1.0.0",
                intent="create_skill",
                trust_tier="verified",
                provenance={
                    "repo_url": "https://github.com/example/skills",
                    "commit_sha": "bbccddeeff00112233445566778899aabbccdde0",
                    "tree_path": "skills/python-verified-admin",
                },
            ),
            token="admin-token",
        )

    assert internal_without_provenance.status_code == 403
    assert internal_without_provenance.json()["error"]["code"] == "POLICY_PROVENANCE_REQUIRED"
    assert verified_without_admin.status_code == 403
    assert verified_without_admin.json()["error"]["code"] == "POLICY_PUBLISH_FORBIDDEN"
    assert verified_with_admin.status_code == 201
    assert verified_with_admin.json()["trust_tier"] == "verified"


@pytest.mark.integration
def test_publish_rejects_invalid_dependency_constraint(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python-invalid-{uuid4().hex}"

    with TestClient(create_app()) as client:
        response = _publish_response(
            client,
            slug,
            _request(
                "1.0.0",
                intent="create_skill",
                depends_on=[{"slug": "python-base", "version_constraint": "latest"}],
            ),
        )

    assert response.status_code == 422


@pytest.mark.integration
def test_publish_rejects_invalid_bundle_structure(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python-invalid-bundle-{uuid4().hex}"

    with TestClient(create_app()) as client:
        payload = _request("1.0.0", intent="create_skill")
        metadata = dict(payload)
        metadata.pop("bundle_raw_markdown")
        response = client.post(
            f"/skills/{slug}",
            files={
                "metadata": (None, json.dumps(metadata), "application/json"),
                "bundle": ("skill.tar.zst", b"not-a-real-tar-zst-stream", "application/zstd"),
            },
            headers=_headers("publisher-token"),
        )

    assert response.status_code == 422


@pytest.mark.integration
def test_publish_rejects_oversized_bundle_before_persisting(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python-oversized-bundle-{uuid4().hex}"

    with TestClient(create_app()) as client:
        payload = _request("1.0.0", intent="create_skill")
        metadata = dict(payload)
        metadata.pop("bundle_raw_markdown")
        response = client.post(
            f"/skills/{slug}",
            files={
                "metadata": (None, json.dumps(metadata), "application/json"),
                "bundle": (
                    "skill.tar.zst",
                    b"x" * (MAX_SKILL_BUNDLE_SIZE_BYTES + 1),
                    "application/zstd",
                ),
            },
            headers=_headers("publisher-token"),
        )

    engine = create_engine(migrated_registry_database)
    try:
        with engine.connect() as connection:
            persisted_count = connection.execute(
                text("SELECT COUNT(*) FROM skills WHERE slug = :slug"),
                {"slug": slug},
            ).scalar_one()
    finally:
        engine.dispose()

    assert response.status_code == 422
    assert persisted_count == 0


@pytest.mark.integration
def test_publish_backfills_normalized_search_documents_with_governance(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python-searchdoc-{uuid4().hex}"
    raw_markdown = "# Search Doc\n"

    with TestClient(create_app()) as client:
        _publish(
            client,
            slug,
            _request(
                "1.0.0",
                intent="create_skill",
                raw_markdown=raw_markdown,
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
            assert row["content_size_bytes"] == len(_bundle(raw_markdown))
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
    slug = f"python-intent-{uuid4().hex}"

    with TestClient(create_app()) as client:
        create_skill = _publish_response(client, slug, _request("1.0.0", intent="create_skill"))
        create_again = _publish_response(client, slug, _request("2.0.0", intent="create_skill"))
        publish_existing = _publish_response(
            client, slug, _request("2.0.0", intent="publish_version")
        )
        publish_missing = _publish_response(
            client, f"{slug}-missing", _request("1.0.0", intent="publish_version")
        )

    assert create_skill.status_code == 201
    assert create_again.status_code == 409
    assert create_again.json()["error"]["code"] == "SKILL_ALREADY_EXISTS"
    assert publish_existing.status_code == 201
    assert publish_missing.status_code == 404
    assert publish_missing.json()["error"]["code"] == "SKILL_NOT_FOUND"
