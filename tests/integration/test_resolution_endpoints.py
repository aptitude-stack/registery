"""Integration tests for resolution endpoints."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.integration.skill_endpoint_helpers import (
    _bundle,
    _headers,
    _publish,
    _query_embedding_statuses,
    _request,
    _update_status,
)


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
    assert _query_embedding_statuses(migrated_registry_database, slug=source_slug) == ["pending"]

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
                "namespace": "public",
                "artifact_origin": "internal",
                "review_state": "approved",
                "promotion_channel": "prod",
                "policy_pack_slug": None,
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
    assert content.headers["content-type"].startswith("application/zstd")
    assert content.headers["ETag"] == published["content"]["checksum"]["digest"]
    assert content.headers["Cache-Control"] == "public, immutable"
    assert content.headers["Content-Length"] == str(len(_bundle("# v2\n")))
    assert content.content == _bundle("# v2\n")


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
            "namespace": "public",
            "artifact_origin": "internal",
            "review_state": "approved",
            "promotion_channel": "prod",
            "policy_pack_slug": None,
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
    assert archived_content_admin.content == _bundle("# Python Lint\n\nLint Python files.\n")
