"""Unit tests for shared exact-read policy and audit orchestration."""

from __future__ import annotations

from app.core.governance import (
    CallerIdentity,
    GovernancePolicy,
    PolicyViolation,
    build_default_policy_profile,
)
from app.core.skills.exact_read import ExactReadAuditInfo, enforce_and_audit_exact_read


class FakeAuditRecorder:
    """Collect audit events emitted by the exact-read helper."""

    def __init__(self) -> None:
        self.events: list[str] = []

    def record_event(self, *, event_type: str, payload: dict[str, object] | None = None) -> None:
        del payload
        self.events.append(event_type)


def _governance_policy() -> GovernancePolicy:
    return GovernancePolicy(profile=build_default_policy_profile())


def _caller(*scopes: str) -> CallerIdentity:
    return CallerIdentity(token_id="token", scopes=frozenset(scopes))


def _audit_info(*, lifecycle_status: str = "published") -> ExactReadAuditInfo:
    return ExactReadAuditInfo(
        slug="python.lint",
        version="1.0.0",
        lifecycle_status=lifecycle_status,
        trust_tier="internal",
    )


def test_enforce_and_audit_exact_read_records_allowed_surface_event() -> None:
    audit_recorder = FakeAuditRecorder()

    enforce_and_audit_exact_read(
        caller=_caller("read"),
        governance_policy=_governance_policy(),
        audit_recorder=audit_recorder,
        audit_info=_audit_info(),
        surface="metadata",
    )

    assert audit_recorder.events == ["skill.version_metadata_read"]


def test_enforce_and_audit_exact_read_records_denial_and_reraises() -> None:
    audit_recorder = FakeAuditRecorder()

    try:
        enforce_and_audit_exact_read(
            caller=_caller("read"),
            governance_policy=_governance_policy(),
            audit_recorder=audit_recorder,
            audit_info=_audit_info(lifecycle_status="archived"),
            surface="content",
        )
    except PolicyViolation:
        pass
    else:
        raise AssertionError("Expected PolicyViolation for archived exact read.")

    assert audit_recorder.events == ["skill.version_exact_read_denied"]
