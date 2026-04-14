"""Core exact dependency-resolution service for immutable skill versions."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.governance import CallerIdentity, GovernancePolicy
from app.core.ports import AuditPort, SkillCatalogRepository

from .exact_read import ExactReadAuditInfo, enforce_and_audit_exact_read
from .models import SkillRelationshipSelector, SkillVersionNotFoundError


@dataclass(frozen=True, slots=True)
class ResolvedSkillDependencies:
    """Direct authored dependency selectors for one immutable skill version."""

    slug: str
    version: str
    depends_on: tuple[SkillRelationshipSelector, ...]


class SkillResolutionService:
    """Read-only exact dependency service with no solving behavior."""

    def __init__(
        self,
        *,
        repository: SkillCatalogRepository,
        audit_recorder: AuditPort,
        governance_policy: GovernancePolicy,
    ) -> None:
        self._repository = repository
        self._audit_recorder = audit_recorder
        self._governance_policy = governance_policy

    def get_direct_dependencies(
        self,
        *,
        caller: CallerIdentity,
        slug: str,
        version: str,
    ) -> ResolvedSkillDependencies:
        """Return authored direct `depends_on` selectors for one exact version."""
        stored = self._repository.get_relationship_source(slug=slug, version=version)
        if stored is None:
            raise SkillVersionNotFoundError(slug=slug, version=version)
        enforce_and_audit_exact_read(
            caller=caller,
            governance_policy=self._governance_policy,
            audit_recorder=self._audit_recorder,
            audit_info=ExactReadAuditInfo(
                slug=stored.slug,
                version=stored.version,
                lifecycle_status=stored.lifecycle_status,
                trust_tier=stored.trust_tier,
            ),
            surface="resolution",
        )

        resolved = ResolvedSkillDependencies(
            slug=stored.slug,
            version=stored.version,
            depends_on=stored.relationships,
        )
        return resolved
