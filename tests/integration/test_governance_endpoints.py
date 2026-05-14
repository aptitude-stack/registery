"""Integration tests for governance endpoints."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.main import create_app
from tests.conftest import DEFAULT_AUTH_SERVICE_TOKENS
from tests.integration.skill_endpoint_helpers import (
    _headers,
    _publish,
    _publish_response,
    _query_audit_events,
    _request,
    _test_skill_request,
    _token_record,
    _update_status,
)


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
def test_enterprise_namespace_review_promotion_and_trust_evidence_workflow(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    private_reader_secret = "dev-private-reader-secret"
    token_records = [
        *DEFAULT_AUTH_SERVICE_TOKENS,
        _token_record(
            token_id="private-reader",
            secret=private_reader_secret,
            scopes=["read"],
            namespace_grants=[
                {
                    "namespace": "acme.private",
                    "roles": ["read"],
                    "promotion_channels": ["prod"],
                }
            ],
        ),
    ]
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    monkeypatch.setenv("AUTH_SERVICE_TOKENS_JSON", json.dumps(token_records))
    suffix = uuid4().hex
    slug = f"python.imported.{suffix}"
    private_headers = {"Authorization": f"Bearer private-reader.{private_reader_secret}"}

    with TestClient(create_app()) as client:
        organization = client.post(
            "/admin/organizations",
            json={"slug": "acme", "display_name": "Acme Corp"},
            headers=_headers("admin-token"),
        )
        namespace = client.post(
            "/admin/namespaces",
            json={"slug": "acme.private", "organization_slug": "acme", "visibility": "private"},
            headers=_headers("admin-token"),
        )
        published = _publish(
            client,
            slug,
            _request(
                "1.0.0",
                intent="create_skill",
                name="Imported Review Candidate",
                description="Third-party imported artifact awaiting review",
                tags=["python", "imported-review"],
                trust_tier="untrusted",
                provenance=None,
            )
            | {
                "governance": {
                    "trust_tier": "untrusted",
                    "namespace": "acme.private",
                    "artifact_origin": "imported",
                    "provenance": None,
                }
            },
            token="admin-token",
        )
        hidden_discovery = client.post(
            "/discovery",
            json={"name": "Imported Review Candidate"},
            headers=private_headers,
        )
        hidden_metadata = client.get(f"/skills/{slug}/1.0.0", headers=private_headers)
        promoted = client.patch(
            f"/admin/skills/{slug}/1.0.0/governance",
            json={
                "review_state": "approved",
                "promotion_channel": "prod",
                "note": "review approved",
            },
            headers=_headers("admin-token"),
        )
        evidence = client.post(
            f"/admin/skills/{slug}/1.0.0/trust-evidence",
            json={
                "evidence_type": "attestation",
                "subject": "build-pipeline",
                "digest": "aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899",
                "uri": "https://example.com/attestations/build.json",
                "payload": {"pipeline": "ci", "run_id": "123"},
            },
            headers=_headers("admin-token"),
        )
        visible_discovery = client.post(
            "/discovery",
            json={"name": "Imported Review Candidate"},
            headers=private_headers,
        )
        metadata = client.get(f"/skills/{slug}/1.0.0", headers=private_headers)
        content = client.get(f"/skills/{slug}/1.0.0/content", headers=private_headers)

    audit_events = _query_audit_events(migrated_registry_database)
    event_types = [event["event_type"] for event in audit_events]

    assert organization.status_code == 201, organization.text
    assert namespace.status_code == 201, namespace.text
    assert published["namespace"] == "acme.private"
    assert published["artifact_origin"] == "imported"
    assert published["review_state"] == "pending_review"
    assert published["promotion_channel"] == "dev"
    assert hidden_discovery.status_code == 200
    assert slug not in hidden_discovery.json()["candidates"]
    assert hidden_metadata.status_code == 403
    assert hidden_metadata.json()["error"]["code"] == "POLICY_REVIEW_STATE_FORBIDDEN"
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["review_state"] == "approved"
    assert promoted.json()["promotion_channel"] == "prod"
    assert evidence.status_code == 201, evidence.text
    assert visible_discovery.status_code == 200
    assert slug in visible_discovery.json()["candidates"]
    assert metadata.status_code == 200
    assert metadata.json()["review_state"] == "approved"
    assert content.status_code == 200
    assert content.headers["ETag"] == published["content"]["checksum"]["digest"]
    assert "enterprise.namespace_created" in event_types
    assert "enterprise.version_visibility_denied" in event_types
    assert "enterprise.version_governance_updated" in event_types
    assert "enterprise.trust_evidence_added" in event_types


@pytest.mark.integration
def test_audit_events_cover_publish_discovery_exact_reads_and_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
    migrated_integration_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_integration_database)
    slug = "test.python.audit-fixture"
    denied_slug = f"{slug}.policy"

    with TestClient(create_app()) as client:
        publish_response = _publish_response(
            client,
            slug,
            _test_skill_request(
                "1.0.0",
                name="Python Audit Fixture",
                description="Test-only fixture used to validate publish and read audit coverage.",
                trust_tier="internal",
                provenance={
                    "repo_url": "https://github.com/example/skills",
                    "commit_sha": "0123456789abcdef0123456789abcdef01234567",
                    "tree_path": f"skills/{slug}",
                    "publisher_identity": "ci/example-release",
                },
            ),
        )
        denied_publish = _publish_response(
            client,
            denied_slug,
            _request("1.0.0", trust_tier="internal"),
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

    audit_events = _query_audit_events(migrated_integration_database)

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
