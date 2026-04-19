"""Typed application service container for runtime wiring."""

from __future__ import annotations

from dataclasses import dataclass

from app.audit.recorder import SQLAlchemyAuditRecorder
from app.core.auth import AuthService, InMemoryServiceTokenLookup
from app.core.governance import GovernancePolicy
from app.core.settings import Settings
from app.core.skills.discovery import SkillDiscoveryService
from app.core.skills.fetch import SkillFetchService
from app.core.skills.registry import SkillRegistryService
from app.core.skills.resolution import SkillResolutionService
from app.observability.readiness import ReadinessService
from app.persistence.db import SQLAlchemyDatabaseReadinessProbe, get_session_factory, init_engine
from app.persistence.skill_registry_repository import SQLAlchemySkillCatalogRepository


@dataclass(frozen=True, slots=True)
class ServiceContainer:
    """Process-scoped services created during application startup."""

    auth_service: AuthService
    readiness_service: ReadinessService
    skill_registry_service: SkillRegistryService
    skill_discovery_service: SkillDiscoveryService
    skill_fetch_service: SkillFetchService
    skill_resolution_service: SkillResolutionService


def build_service_container(*, settings: Settings) -> ServiceContainer:
    """Create the process-scoped service graph for the application."""
    init_engine(settings.database_url)
    session_factory = get_session_factory()
    catalog_repository = SQLAlchemySkillCatalogRepository(session_factory=session_factory)
    audit_recorder = SQLAlchemyAuditRecorder(session_factory=session_factory)
    governance_policy = GovernancePolicy(profile=settings.active_policy)
    return ServiceContainer(
        auth_service=AuthService(
            token_lookup=InMemoryServiceTokenLookup(records=settings.service_token_records),
        ),
        readiness_service=ReadinessService(
            database_probe=SQLAlchemyDatabaseReadinessProbe(),
        ),
        skill_registry_service=SkillRegistryService(
            repository=catalog_repository,
            audit_recorder=audit_recorder,
            governance_policy=governance_policy,
        ),
        skill_discovery_service=SkillDiscoveryService(
            repository=catalog_repository,
            audit_recorder=audit_recorder,
            governance_policy=governance_policy,
        ),
        skill_fetch_service=SkillFetchService(
            repository=catalog_repository,
            audit_recorder=audit_recorder,
            governance_policy=governance_policy,
        ),
        skill_resolution_service=SkillResolutionService(
            repository=catalog_repository,
            audit_recorder=audit_recorder,
            governance_policy=governance_policy,
        ),
    )
