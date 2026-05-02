"""Core advisory search service and domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.audit_events import build_search_audit_event
from app.core.governance import (
    ALL_REVIEW_STATES,
    CallerIdentity,
    GovernancePolicy,
    LifecycleStatus,
    TrustTier,
)
from app.core.ports import AuditPort, SearchCandidatesRequest, SkillCatalogRepository
from app.intelligence.search_ranking import (
    build_search_audit_payload,
    build_search_explanation,
    normalize_search_request,
)


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
        repository: SkillCatalogRepository,
        audit_recorder: AuditPort,
        governance_policy: GovernancePolicy,
    ) -> None:
        self._repository = repository
        self._audit_recorder = audit_recorder
        self._governance_policy = governance_policy

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
        stored_results = self._repository.search_candidates(
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
