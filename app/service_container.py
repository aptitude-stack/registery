"""Typed application service container for runtime wiring."""

from __future__ import annotations

from dataclasses import dataclass

from app.audit.recorder import SQLAlchemyAuditRecorder
from app.core.governance import GovernancePolicy
from app.core.settings import Settings
from app.core.skills.discovery import SkillDiscoveryService
from app.core.skills.fetch import SkillFetchService
from app.core.skills.registry import SkillRegistryService
from app.core.skills.resolution import SkillResolutionService
from app.observability.readiness import ReadinessService
from app.persistence.db import SQLAlchemyDatabaseReadinessProbe, get_session_factory, init_engine
from app.persistence.skill_registry_repository import SQLAlchemySkillRegistryRepository


@dataclass(frozen=True, slots=True)
class ServiceContainer:
    """Process-scoped services created during application startup."""

    readiness_service: ReadinessService
    skill_registry_service: SkillRegistryService
    skill_discovery_service: SkillDiscoveryService
    skill_fetch_service: SkillFetchService
    skill_resolution_service: SkillResolutionService


def build_service_container(*, settings: Settings) -> ServiceContainer:
    """Create the process-scoped service graph for the application."""
    init_engine(settings.database_url)
    session_factory = get_session_factory()
    registry_repository = SQLAlchemySkillRegistryRepository(session_factory=session_factory)
    audit_recorder = SQLAlchemyAuditRecorder(session_factory=session_factory)
    governance_policy = GovernancePolicy(profile=settings.active_policy)
    return ServiceContainer(
        readiness_service=ReadinessService(
            database_probe=SQLAlchemyDatabaseReadinessProbe(),
        ),
        skill_registry_service=SkillRegistryService(
            registry=registry_repository,
            audit_recorder=audit_recorder,
            governance_policy=governance_policy,
        ),
        skill_discovery_service=SkillDiscoveryService(
            search_port=registry_repository,
            audit_recorder=audit_recorder,
            governance_policy=governance_policy,
        ),
        skill_fetch_service=SkillFetchService(
            version_reader=registry_repository,
            audit_recorder=audit_recorder,
            governance_policy=governance_policy,
            install_counter=registry_repository,
        ),
        skill_resolution_service=SkillResolutionService(
            relationship_reader=registry_repository,
            audit_recorder=audit_recorder,
            governance_policy=governance_policy,
        ),
    )
