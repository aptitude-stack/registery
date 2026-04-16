"""Unit tests for exact dependency resolution behavior."""

from __future__ import annotations

import pytest

from app.core.governance import (
    CallerIdentity,
    GovernancePolicy,
    PolicyViolation,
    build_default_policy_profile,
)
from app.core.skills.models import (
    SkillRelationshipSelector,
    SkillRelationshipSource,
    SkillVersionNotFoundError,
)
from app.core.skills.resolution import SkillResolutionService


class FakeAuditRecorder:
    """Collect audit events emitted by the resolution service."""

    def __init__(self) -> None:
        self.events: list[str] = []

    def record_event(self, *, event_type: str, payload: dict[str, object] | None = None) -> None:
        del payload
        self.events.append(event_type)


class FakeCatalogRepository:
    """Stub relationship source repository keyed by exact coordinate."""

    def __init__(self, *sources: SkillRelationshipSource) -> None:
        self._sources = {(item.slug, item.version): item for item in sources}

    def get_relationship_source(
        self,
        *,
        slug: str,
        version: str,
    ) -> SkillRelationshipSource | None:
        return self._sources.get((slug, version))


@pytest.mark.unit
def test_get_direct_dependencies_returns_only_depends_on_selectors() -> None:
    audit_recorder = FakeAuditRecorder()
    source = SkillRelationshipSource(
        slug="python.source",
        version="1.0.0",
        lifecycle_status="published",
        trust_tier="internal",
        relationships=(
            SkillRelationshipSelector(
                slug="python.dep",
                version="2.0.0",
                version_constraint=None,
                optional=True,
                markers=("linux",),
            ),
        ),
    )
    service = SkillResolutionService(
        repository=FakeCatalogRepository(source),
        audit_recorder=audit_recorder,
        governance_policy=GovernancePolicy(profile=build_default_policy_profile()),
    )

    result = service.get_direct_dependencies(
        caller=CallerIdentity(token="reader", scopes=frozenset({"read"})),
        slug="python.source",
        version="1.0.0",
    )

    assert result.slug == "python.source"
    assert result.version == "1.0.0"
    assert len(result.depends_on) == 1
    assert result.depends_on[0].slug == "python.dep"
    assert result.depends_on[0].version == "2.0.0"
    assert result.depends_on[0].optional is True
    assert result.depends_on[0].markers == ("linux",)
    assert audit_recorder.events == ["skill.version_resolution_read"]


@pytest.mark.unit
def test_get_direct_dependencies_raises_not_found_for_unknown_coordinate() -> None:
    service = SkillResolutionService(
        repository=FakeCatalogRepository(),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=GovernancePolicy(profile=build_default_policy_profile()),
    )

    with pytest.raises(SkillVersionNotFoundError):
        service.get_direct_dependencies(
            caller=CallerIdentity(token="reader", scopes=frozenset({"read"})),
            slug="python.missing",
            version="9.9.9",
        )


@pytest.mark.unit
def test_get_direct_dependencies_audits_denied_exact_reads() -> None:
    audit_recorder = FakeAuditRecorder()
    service = SkillResolutionService(
        repository=FakeCatalogRepository(
            SkillRelationshipSource(
                slug="python.source",
                version="1.0.0",
                lifecycle_status="archived",
                trust_tier="internal",
                relationships=(),
            )
        ),
        audit_recorder=audit_recorder,
        governance_policy=GovernancePolicy(profile=build_default_policy_profile()),
    )

    with pytest.raises(PolicyViolation):
        service.get_direct_dependencies(
            caller=CallerIdentity(token="reader", scopes=frozenset({"read"})),
            slug="python.source",
            version="1.0.0",
        )

    assert audit_recorder.events == ["skill.version_exact_read_denied"]
