"""Unit tests for typed registry audit event builders."""

from __future__ import annotations

import pytest

from app.core.audit_events import (
    build_exact_read_denied_audit_event,
    build_lifecycle_audit_event,
    build_publish_audit_event,
    build_search_audit_event,
    build_version_list_audit_event,
)
from app.core.governance import CallerIdentity, ProvenanceMetadata
from app.observability.context import clear_request_context, set_request_context


def _caller() -> CallerIdentity:
    return CallerIdentity(token_id="publisher-token", scopes=frozenset({"publish", "read"}))


@pytest.mark.unit
def test_publish_audit_event_includes_redacted_actor_and_provenance_summary() -> None:
    event = build_publish_audit_event(
        caller=_caller(),
        slug="python.lint",
        version="1.2.3",
        trust_tier="internal",
        provenance=ProvenanceMetadata(
            repo_url="https://github.com/acme/python-lint",
            commit_sha="0123456789abcdef0123456789abcdef01234567",
            tree_path="skills/python/lint",
            publisher_identity="ci/acme-release",
            policy_profile="default",
        ),
        policy_profile="default",
        outcome="allowed",
    )

    assert event.event_type == "skill.version_published"
    assert event.payload is not None
    assert event.payload["actor_token_id"] == "publisher-token"
    assert event.payload["actor_scopes"] == ["publish", "read"]
    assert event.payload["publisher_identity"] == "ci/acme-release"
    assert event.payload["policy_profile_at_publish"] == "default"


@pytest.mark.unit
def test_lifecycle_denied_audit_event_captures_reason_code() -> None:
    event = build_lifecycle_audit_event(
        caller=_caller(),
        slug="python.lint",
        version="1.2.3",
        previous_status="archived",
        lifecycle_status="published",
        trust_tier="internal",
        policy_profile="default",
        note="reopen archived version",
        outcome="denied",
        reason_code="POLICY_STATUS_TRANSITION_FORBIDDEN",
    )

    assert event.event_type == "skill.version_status_update_denied"
    assert event.payload is not None
    assert event.payload["reason_code"] == "POLICY_STATUS_TRANSITION_FORBIDDEN"
    assert event.payload["previous_status"] == "archived"
    assert event.payload["lifecycle_status"] == "published"


@pytest.mark.unit
def test_exact_read_denied_event_tracks_surface_and_outcome() -> None:
    event = build_exact_read_denied_audit_event(
        caller=_caller(),
        slug="python.lint",
        version="1.2.3",
        lifecycle_status="archived",
        trust_tier="internal",
        surface="content",
        policy_profile="default",
        reason_code="POLICY_EXACT_READ_FORBIDDEN",
    )

    assert event.event_type == "skill.version_exact_read_denied"
    assert event.payload is not None
    assert event.payload["surface"] == "content"
    assert event.payload["outcome"] == "denied"
    assert event.payload["reason_code"] == "POLICY_EXACT_READ_FORBIDDEN"


@pytest.mark.unit
def test_search_audit_event_keeps_query_values_redacted() -> None:
    event = build_search_audit_event(
        caller=_caller(),
        policy_profile="default",
        payload={"query_present": True, "tag_count": 1, "result_count": 2},
    )

    assert event.event_type == "skill.search_performed"
    assert event.payload is not None
    assert event.payload["surface"] == "discovery"
    assert event.payload["query_present"] is True
    assert event.payload["result_count"] == 2


@pytest.mark.unit
def test_version_list_audit_event_tracks_slug_and_result_count() -> None:
    event = build_version_list_audit_event(
        caller=_caller(),
        policy_profile="default",
        slug="python.lint",
        result_count=2,
    )

    assert event.event_type == "skill.version_list_read"
    assert event.payload is not None
    assert event.payload["surface"] == "list"
    assert event.payload["slug"] == "python.lint"
    assert event.payload["result_count"] == 2


@pytest.mark.unit
def test_audit_events_include_request_id_from_observability_context() -> None:
    set_request_context(request_id="req-audit")
    try:
        event = build_publish_audit_event(
            caller=_caller(),
            slug="python.lint",
            version="1.2.3",
            trust_tier="internal",
            provenance=None,
            policy_profile="default",
            outcome="allowed",
        )
    finally:
        clear_request_context()

    assert event.payload is not None
    assert event.payload["request_id"] == "req-audit"
