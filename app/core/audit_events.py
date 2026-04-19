"""Typed audit event builders for registry operations."""

from __future__ import annotations

from typing import Any, Literal

from app.core.governance import CallerIdentity, LifecycleStatus, ProvenanceMetadata, TrustTier
from app.core.ports import AuditEventRecord
from app.observability.context import get_request_context

ExactReadSurface = Literal["resolution", "metadata", "content"]
AuditOutcome = Literal["allowed", "denied"]

_EXACT_READ_EVENT_TYPES: dict[ExactReadSurface, str] = {
    "resolution": "skill.version_resolution_read",
    "metadata": "skill.version_metadata_read",
    "content": "skill.version_content_read",
}


def build_publish_audit_event(
    *,
    caller: CallerIdentity,
    slug: str,
    version: str,
    trust_tier: TrustTier,
    provenance: ProvenanceMetadata | None,
    policy_profile: str,
    outcome: AuditOutcome,
    reason_code: str | None = None,
) -> AuditEventRecord:
    """Return a publish audit event with redacted actor context."""
    return AuditEventRecord(
        event_type=(
            "skill.version_published" if outcome == "allowed" else "skill.version_publish_denied"
        ),
        payload=_base_payload(
            caller=caller,
            policy_profile=policy_profile,
            outcome=outcome,
            slug=slug,
            version=version,
            trust_tier=trust_tier,
            lifecycle_status="published" if outcome == "allowed" else None,
            surface="publish",
            reason_code=reason_code,
            provenance=provenance,
        ),
    )


def build_lifecycle_audit_event(
    *,
    caller: CallerIdentity,
    slug: str,
    version: str,
    previous_status: LifecycleStatus,
    lifecycle_status: LifecycleStatus,
    trust_tier: TrustTier,
    policy_profile: str,
    note: str | None,
    outcome: AuditOutcome,
    reason_code: str | None = None,
) -> AuditEventRecord:
    """Return an audit event for lifecycle updates and policy denials."""
    payload = _base_payload(
        caller=caller,
        policy_profile=policy_profile,
        outcome=outcome,
        slug=slug,
        version=version,
        trust_tier=trust_tier,
        lifecycle_status=lifecycle_status,
        surface="lifecycle",
        reason_code=reason_code,
    )
    payload["previous_status"] = previous_status
    if note is not None:
        payload["note"] = note
    return AuditEventRecord(
        event_type=(
            "skill.version_status_updated"
            if outcome == "allowed"
            else "skill.version_status_update_denied"
        ),
        payload=payload,
    )


def build_search_audit_event(
    *,
    caller: CallerIdentity,
    policy_profile: str,
    payload: dict[str, Any],
) -> AuditEventRecord:
    """Return a discovery/search audit event."""
    search_payload = _base_payload(
        caller=caller,
        policy_profile=policy_profile,
        outcome="allowed",
        surface="discovery",
    )
    search_payload.update(payload)
    return AuditEventRecord(event_type="skill.search_performed", payload=search_payload)


def build_version_list_audit_event(
    *,
    caller: CallerIdentity,
    policy_profile: str,
    slug: str,
    result_count: int,
) -> AuditEventRecord:
    """Return an identity-level version list audit event."""
    payload = _base_payload(
        caller=caller,
        policy_profile=policy_profile,
        outcome="allowed",
        slug=slug,
        surface="list",
    )
    payload["result_count"] = result_count
    return AuditEventRecord(event_type="skill.version_list_read", payload=payload)


def build_exact_read_audit_event(
    *,
    caller: CallerIdentity,
    slug: str,
    version: str,
    lifecycle_status: LifecycleStatus,
    trust_tier: TrustTier,
    surface: ExactReadSurface,
    policy_profile: str,
) -> AuditEventRecord:
    """Return a successful exact-read audit event."""
    return AuditEventRecord(
        event_type=_EXACT_READ_EVENT_TYPES[surface],
        payload=_base_payload(
            caller=caller,
            policy_profile=policy_profile,
            outcome="allowed",
            slug=slug,
            version=version,
            trust_tier=trust_tier,
            lifecycle_status=lifecycle_status,
            surface=surface,
        ),
    )


def build_exact_read_denied_audit_event(
    *,
    caller: CallerIdentity,
    slug: str,
    version: str,
    lifecycle_status: LifecycleStatus,
    trust_tier: TrustTier,
    surface: ExactReadSurface,
    policy_profile: str,
    reason_code: str,
) -> AuditEventRecord:
    """Return a denied exact-read audit event."""
    return AuditEventRecord(
        event_type="skill.version_exact_read_denied",
        payload=_base_payload(
            caller=caller,
            policy_profile=policy_profile,
            outcome="denied",
            slug=slug,
            version=version,
            trust_tier=trust_tier,
            lifecycle_status=lifecycle_status,
            surface=surface,
            reason_code=reason_code,
        ),
    )


def _base_payload(
    *,
    caller: CallerIdentity,
    policy_profile: str,
    outcome: AuditOutcome,
    slug: str | None = None,
    version: str | None = None,
    trust_tier: TrustTier | None = None,
    lifecycle_status: LifecycleStatus | None = None,
    surface: str,
    reason_code: str | None = None,
    provenance: ProvenanceMetadata | None = None,
) -> dict[str, Any]:
    request_context = get_request_context()
    payload: dict[str, Any] = {
        "actor_token_id": caller.token_id,
        "actor_scopes": sorted(caller.scopes),
        "policy_profile": policy_profile,
        "surface": surface,
        "outcome": outcome,
        "request_id": request_context.request_id,
    }
    if slug is not None:
        payload["slug"] = slug
    if version is not None:
        payload["version"] = version
    if trust_tier is not None:
        payload["trust_tier"] = trust_tier
    if lifecycle_status is not None:
        payload["lifecycle_status"] = lifecycle_status
    if reason_code is not None:
        payload["reason_code"] = reason_code
    if provenance is not None:
        payload.update(_provenance_payload(provenance))
    else:
        payload["provenance_present"] = False
    return payload


def _provenance_payload(provenance: ProvenanceMetadata) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "provenance_present": True,
        "provenance_repo_url": provenance.repo_url,
        "provenance_commit_sha": provenance.commit_sha,
    }
    if provenance.tree_path is not None:
        payload["provenance_tree_path"] = provenance.tree_path
    if provenance.publisher_identity is not None:
        payload["publisher_identity"] = provenance.publisher_identity
    if provenance.policy_profile is not None:
        payload["policy_profile_at_publish"] = provenance.policy_profile
    return payload
