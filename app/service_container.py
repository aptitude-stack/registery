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
from app.integrations.openai_embeddings import OpenAIEmbeddingProvider
from app.observability.readiness import ReadinessService
from app.observability.telemetry import instrument_database_engine
from app.persistence.db import (
    SQLAlchemyDatabaseReadinessProbe,
    get_engine,
    get_session_factory,
    init_engine,
)
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
    init_engine(
        settings.database_url,
        application_name=f"{settings.app_name}-{settings.app_env}",
    )
    engine = get_engine()
    if engine is not None:
        instrument_database_engine(engine)
    session_factory = get_session_factory()
    catalog_repository = SQLAlchemySkillCatalogRepository(
        session_factory=session_factory,
        semantic_embedding_index_key=settings.semantic_embedding_index_key,
        semantic_embedding_dimensions=settings.semantic_embedding_dimensions,
    )
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
            semantic_discovery_mode=settings.semantic_discovery_mode,
            embedding_provider=_build_embedding_provider(settings=settings),
            semantic_embedding_model=settings.semantic_embedding_model,
            semantic_embedding_index_key=settings.semantic_embedding_index_key,
            semantic_embedding_dimensions=settings.semantic_embedding_dimensions,
            semantic_candidate_limit=settings.semantic_candidate_limit,
            semantic_query_timeout_ms=settings.semantic_query_timeout_ms,
            semantic_hnsw_ef_search=settings.semantic_hnsw_ef_search,
            co_usage_ranking_enabled=settings.co_usage_ranking_enabled,
            co_usage_boost_cap=settings.co_usage_boost_cap,
            co_usage_context_limit=settings.co_usage_context_limit,
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


def _build_embedding_provider(*, settings: Settings) -> OpenAIEmbeddingProvider | None:
    if settings.semantic_discovery_mode == "off":
        return None
    if settings.semantic_embedding_provider == "openai" and settings.openai_api_key is not None:
        return OpenAIEmbeddingProvider(api_key=settings.openai_api_key)
    return None
