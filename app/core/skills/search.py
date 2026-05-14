"""Core advisory search service and domain models."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.audit_events import build_search_audit_event
from app.core.governance import (
    ALL_REVIEW_STATES,
    CallerIdentity,
    GovernancePolicy,
    LifecycleStatus,
    PromotionChannel,
    ReviewState,
    TrustTier,
)
from app.core.ports import (
    AuditPort,
    CoUsageBoostRequest,
    EmbeddingProviderPort,
    SearchCandidatesRequest,
    SearchSemanticCandidatesRequest,
    SkillDiscoverySearchPort,
    StoredSkillSearchCandidate,
)
from app.core.semantic_defaults import (
    DEFAULT_SEMANTIC_CANDIDATE_LIMIT,
    DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS,
    DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
    DEFAULT_SEMANTIC_EMBEDDING_MODEL,
    DEFAULT_SEMANTIC_HNSW_EF_SEARCH,
    DEFAULT_SEMANTIC_QUERY_TIMEOUT_MS,
)
from app.core.settings import SemanticDiscoveryMode
from app.intelligence.discovery_signals import (
    fuse_discovery_candidates,
    validate_embedding_vector,
)
from app.intelligence.search_ranking import (
    build_search_audit_payload,
    build_search_explanation,
    normalize_search_request,
)
from app.observability.metrics import observe_semantic_discovery_failure

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SkillSearchQuery:
    """External advisory search request owned by the core layer."""

    q: str | None
    tags: tuple[str, ...]
    language: str | None
    fresh_within_days: int | None
    max_footprint_bytes: int | None
    limit: int
    status: tuple[LifecycleStatus, ...] = ()
    trust_tier: tuple[TrustTier, ...] = ()
    context_skills: tuple[str, ...] = ()
    semantic_text: str | None = None
    semantic_text_is_explicit: bool = False


@dataclass(frozen=True, slots=True)
class SkillSearchResult:
    """Compact advisory search card returned to the API layer."""

    slug: str
    version: str
    name: str
    description: str | None
    tags: tuple[str, ...]
    lifecycle_status: LifecycleStatus
    trust_tier: TrustTier
    published_at: datetime
    freshness_days: int
    content_size_bytes: int
    usage_count: int
    matched_fields: tuple[str, ...]
    matched_tags: tuple[str, ...]
    reasons: tuple[str, ...]


class SkillSearchService:
    """Read-only search service for indexed candidate retrieval."""

    def __init__(
        self,
        *,
        repository: SkillDiscoverySearchPort,
        audit_recorder: AuditPort,
        governance_policy: GovernancePolicy,
        semantic_discovery_mode: SemanticDiscoveryMode = "off",
        embedding_provider: EmbeddingProviderPort | None = None,
        semantic_embedding_model: str = DEFAULT_SEMANTIC_EMBEDDING_MODEL,
        semantic_embedding_index_key: str = DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
        semantic_embedding_dimensions: int = DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS,
        semantic_candidate_limit: int = DEFAULT_SEMANTIC_CANDIDATE_LIMIT,
        semantic_query_timeout_ms: int = DEFAULT_SEMANTIC_QUERY_TIMEOUT_MS,
        semantic_hnsw_ef_search: int = DEFAULT_SEMANTIC_HNSW_EF_SEARCH,
        co_usage_ranking_enabled: bool = False,
        co_usage_boost_cap: float = 0.05,
        co_usage_context_limit: int = 10,
    ) -> None:
        self._repository = repository
        self._audit_recorder = audit_recorder
        self._governance_policy = governance_policy
        self._semantic_discovery_mode = semantic_discovery_mode
        self._embedding_provider = embedding_provider
        self._semantic_embedding_model = semantic_embedding_model
        self._semantic_embedding_index_key = semantic_embedding_index_key
        self._semantic_embedding_dimensions = semantic_embedding_dimensions
        self._semantic_candidate_limit = semantic_candidate_limit
        self._semantic_query_timeout_ms = semantic_query_timeout_ms
        self._semantic_hnsw_ef_search = semantic_hnsw_ef_search
        self._co_usage_ranking_enabled = co_usage_ranking_enabled
        self._co_usage_boost_cap = co_usage_boost_cap
        self._co_usage_context_limit = co_usage_context_limit

    def search(
        self,
        *,
        caller: CallerIdentity,
        query: SkillSearchQuery,
    ) -> tuple[SkillSearchResult, ...]:
        """Return compact, deterministically explained search candidates."""
        normalized_request = normalize_search_request(
            q=query.q,
            tags=query.tags,
            language=query.language,
            fresh_within_days=query.fresh_within_days,
            max_footprint_bytes=query.max_footprint_bytes,
            limit=query.limit,
        )
        lifecycle_statuses = self._governance_policy.resolve_discovery_statuses(
            caller=caller,
            requested_statuses=query.status,
        )
        trust_tiers = self._governance_policy.resolve_discovery_trust_tiers(
            requested_trust_tiers=query.trust_tier,
        )
        namespaces = self._governance_policy.resolve_discovery_namespaces(caller=caller)
        promotion_channels = self._governance_policy.resolve_discovery_promotion_channels(
            caller=caller,
        )
        lexical_results = self._repository.search_candidates(
            request=SearchCandidatesRequest(
                query_text=normalized_request.query_text,
                required_tags=normalized_request.effective_tags,
                fresh_within_days=normalized_request.fresh_within_days,
                max_content_size_bytes=normalized_request.max_footprint_bytes,
                lifecycle_statuses=lifecycle_statuses,
                trust_tiers=trust_tiers,
                namespaces=namespaces,
                promotion_channels=promotion_channels,
                review_states=ALL_REVIEW_STATES if caller.has_scope("review") else ("approved",),
                limit=normalized_request.limit,
            )
        )
        semantic_query_text = (
            query.semantic_text
            if query.semantic_text_is_explicit
            else (query.semantic_text or query.q)
        )
        semantic_results = self._semantic_candidates(
            query_text=normalize_search_request(
                q=semantic_query_text,
                tags=(),
                language=None,
                fresh_within_days=None,
                max_footprint_bytes=None,
                limit=normalized_request.limit,
            ).query_text,
            normalized_request_limit=normalized_request.limit,
            required_tags=normalized_request.effective_tags,
            fresh_within_days=normalized_request.fresh_within_days,
            max_content_size_bytes=normalized_request.max_footprint_bytes,
            lifecycle_statuses=lifecycle_statuses,
            trust_tiers=trust_tiers,
            namespaces=namespaces,
            promotion_channels=promotion_channels,
            review_states=ALL_REVIEW_STATES if caller.has_scope("review") else ("approved",),
        )
        stored_results = self._combine_candidates(
            lexical_results=lexical_results,
            semantic_results=semantic_results,
            context_skills=query.context_skills,
            limit=normalized_request.limit,
        )
        visible_results = tuple(
            item
            for item in stored_results
            if self._governance_policy.is_visible_in_list(
                caller=caller,
                lifecycle_status=item.lifecycle_status,
                namespace=item.namespace,
                review_state=item.review_state,
                promotion_channel=item.promotion_channel,
                trust_tier=item.trust_tier,
                policy_pack=item.policy_pack,
            )
        )
        current_time = datetime.now(UTC)

        results = tuple(
            SkillSearchResult(
                slug=item.slug,
                version=item.version,
                name=item.name,
                description=item.description,
                tags=item.tags,
                lifecycle_status=item.lifecycle_status,
                trust_tier=item.trust_tier,
                published_at=item.published_at,
                freshness_days=max((current_time - item.published_at).days, 0),
                content_size_bytes=item.content_size_bytes,
                usage_count=item.usage_count,
                matched_fields=explanation.matched_fields,
                matched_tags=explanation.matched_tags,
                reasons=explanation.reasons,
            )
            for item in visible_results
            for explanation in (
                build_search_explanation(
                    query_terms=normalized_request.query_terms,
                    requested_tags=normalized_request.effective_tags,
                    slug=item.slug,
                    name=item.name,
                    description=item.description,
                    tags=item.tags,
                    exact_slug_match=item.exact_slug_match,
                    exact_name_match=item.exact_name_match,
                    lexical_score=item.lexical_score,
                    tag_overlap_count=item.tag_overlap_count,
                ),
            )
        )

        event = build_search_audit_event(
            caller=caller,
            policy_profile=self._governance_policy.profile_name,
            payload=build_search_audit_payload(
                request=normalized_request,
                result_count=len(results),
            ),
        )
        self._audit_recorder.record_event(event_type=event.event_type, payload=event.payload)
        return results

    def _semantic_candidates(
        self,
        *,
        query_text: str | None,
        normalized_request_limit: int,
        required_tags: tuple[str, ...],
        fresh_within_days: int | None,
        max_content_size_bytes: int | None,
        lifecycle_statuses: tuple[LifecycleStatus, ...],
        trust_tiers: tuple[TrustTier, ...],
        namespaces: tuple[str, ...] | None,
        promotion_channels: tuple[PromotionChannel, ...] | None,
        review_states: tuple[ReviewState, ...],
    ) -> tuple[StoredSkillSearchCandidate, ...]:
        if (
            self._semantic_discovery_mode == "off"
            or query_text is None
            or self._embedding_provider is None
        ):
            return ()
        try:
            query_embedding = validate_embedding_vector(
                self._embedding_provider.embed_query(
                    text=query_text,
                    model=self._semantic_embedding_model,
                    dimensions=self._semantic_embedding_dimensions,
                    timeout_ms=self._semantic_query_timeout_ms,
                ),
                dimensions=self._semantic_embedding_dimensions,
            )
        except Exception as exc:
            self._record_semantic_failure(stage="provider", exc=exc)
            return ()

        try:
            return self._repository.search_semantic_candidates(
                request=SearchSemanticCandidatesRequest(
                    query_embedding=query_embedding,
                    embedding_model=self._semantic_embedding_index_key,
                    embedding_dimensions=self._semantic_embedding_dimensions,
                    required_tags=required_tags,
                    fresh_within_days=fresh_within_days,
                    max_content_size_bytes=max_content_size_bytes,
                    lifecycle_statuses=lifecycle_statuses,
                    trust_tiers=trust_tiers,
                    namespaces=namespaces,
                    promotion_channels=promotion_channels,
                    review_states=review_states,
                    limit=min(self._semantic_candidate_limit, normalized_request_limit),
                    hnsw_ef_search=self._semantic_hnsw_ef_search,
                )
            )
        except Exception as exc:
            self._record_semantic_failure(stage="repository", exc=exc)
            return ()

    def _record_semantic_failure(self, *, stage: str, exc: Exception) -> None:
        observe_semantic_discovery_failure(
            mode=self._semantic_discovery_mode,
            stage=stage,
            exception_type=type(exc).__name__,
        )
        logger.warning(
            "semantic discovery degraded to lexical fallback",
            extra={
                "event_type": "semantic.discovery.failed",
                "semantic_mode": self._semantic_discovery_mode,
                "semantic_stage": stage,
                "exception_type": type(exc).__name__,
            },
        )

    def _combine_candidates(
        self,
        *,
        lexical_results: tuple[StoredSkillSearchCandidate, ...],
        semantic_results: tuple[StoredSkillSearchCandidate, ...],
        context_skills: tuple[str, ...],
        limit: int,
    ) -> tuple[StoredSkillSearchCandidate, ...]:
        if self._semantic_discovery_mode == "shadow":
            semantic_results = ()
        co_usage_boosts: dict[str, float] = {}
        if self._co_usage_ranking_enabled and context_skills:
            candidate_slugs = tuple(
                dict.fromkeys(item.slug for item in (*lexical_results, *semantic_results))
            )
            co_usage_boosts = self._repository.get_co_usage_boosts(
                request=CoUsageBoostRequest(
                    context_skill_slugs=context_skills[: self._co_usage_context_limit],
                    candidate_slugs=candidate_slugs,
                    boost_cap=self._co_usage_boost_cap,
                )
            )
        return fuse_discovery_candidates(
            lexical_candidates=lexical_results,
            semantic_candidates=semantic_results,
            co_usage_boosts=co_usage_boosts,
            limit=limit,
            co_usage_boost_cap=self._co_usage_boost_cap,
        )
