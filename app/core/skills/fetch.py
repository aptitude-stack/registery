"""Core exact fetch service for immutable metadata and bundle reads."""

from __future__ import annotations

from app.core.audit_events import build_version_list_audit_event
from app.core.governance import CallerIdentity, GovernancePolicy
from app.core.ports import AuditPort, SkillFetchPort

from .discovery import SkillDiscoveryRequest, SkillDiscoveryService
from .exact_read import ExactReadAuditInfo, enforce_and_audit_exact_read
from .models import (
    SkillContentRecord,
    SkillNotFoundError,
    SkillVersionDetail,
    SkillVersionList,
    SkillVersionNotFoundError,
    SkillVersionSummary,
)
from .version_ordering import select_current_default_version, sort_versions_for_listing


class SkillFetchService:
    """Read-only service for exact immutable metadata and bundle access."""

    def __init__(
        self,
        *,
        repository: SkillFetchPort,
        audit_recorder: AuditPort,
        governance_policy: GovernancePolicy,
        discovery_service: SkillDiscoveryService | None = None,
    ) -> None:
        self._repository = repository
        self._audit_recorder = audit_recorder
        self._governance_policy = governance_policy
        self._discovery_service = discovery_service

    def get_version_metadata(
        self,
        *,
        caller: CallerIdentity,
        slug: str,
        version: str,
    ) -> SkillVersionDetail:
        """Return immutable version metadata for one exact coordinate."""
        stored = self._repository.get_version_detail(slug=slug, version=version)
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
                namespace=stored.namespace,
                review_state=stored.review_state,
                promotion_channel=stored.promotion_channel,
                policy_pack=stored.policy_pack,
            ),
            surface="metadata",
        )
        return stored

    def get_content(
        self,
        *,
        caller: CallerIdentity,
        slug: str,
        version: str,
    ) -> SkillContentRecord:
        """Return immutable bundle content for one exact coordinate."""
        stored = self._repository.get_version_content(slug=slug, version=version)
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
                namespace=stored.namespace,
                review_state=stored.review_state,
                promotion_channel=stored.promotion_channel,
                policy_pack=stored.policy_pack,
            ),
            surface="content",
        )
        self._repository.record_install(slug=stored.slug, version=stored.version)
        return stored

    def list_versions(
        self,
        *,
        caller: CallerIdentity,
        slug: str,
    ) -> SkillVersionList:
        """Return visible immutable versions for one skill identity."""
        stored_versions = self._repository.list_versions(slug=slug)
        if not stored_versions:
            raise SkillNotFoundError(slug=slug)

        visible_versions = tuple(
            stored
            for stored in stored_versions
            if self._governance_policy.is_visible_in_list(
                caller=caller,
                lifecycle_status=stored.lifecycle_status,
                namespace=stored.namespace,
                review_state=stored.review_state,
                promotion_channel=stored.promotion_channel,
                trust_tier=stored.trust_tier,
                policy_pack=stored.policy_pack,
            )
        )
        if not visible_versions:
            raise SkillNotFoundError(slug=slug)

        visible_versions = sort_versions_for_listing(visible_versions)
        current_default = select_current_default_version(visible_versions)
        versions = tuple(
            SkillVersionSummary(
                version=stored.version,
                lifecycle_status=stored.lifecycle_status,
                trust_tier=stored.trust_tier,
                namespace=stored.namespace,
                artifact_origin=stored.artifact_origin,
                review_state=stored.review_state,
                promotion_channel=stored.promotion_channel,
                policy_pack_slug=None if stored.policy_pack is None else stored.policy_pack.slug,
                published_at=stored.published_at,
                is_current_default=current_default is not None
                and stored.version == current_default.version,
            )
            for stored in visible_versions
        )
        audit_event = build_version_list_audit_event(
            caller=caller,
            policy_profile=self._governance_policy.profile_name,
            slug=slug,
            result_count=len(versions),
        )
        self._audit_recorder.record_event(
            event_type=audit_event.event_type,
            payload=audit_event.payload,
        )
        return SkillVersionList(slug=slug, versions=versions)

    def list_top_installed(
        self,
        *,
        caller: CallerIdentity,
        limit: int,
    ) -> tuple[SkillVersionDetail, ...]:
        """Return top installed current-default versions visible to the caller."""
        candidates = self._repository.list_top_installed_versions(limit=max(limit * 4, limit))
        visible: list[SkillVersionDetail] = []
        for stored in candidates:
            if self._governance_policy.is_visible_in_list(
                caller=caller,
                lifecycle_status=stored.lifecycle_status,
                namespace=stored.namespace,
                review_state=stored.review_state,
                promotion_channel=stored.promotion_channel,
                trust_tier=stored.trust_tier,
                policy_pack=stored.policy_pack,
            ):
                visible.append(stored)
            if len(visible) >= limit:
                break
        return tuple(visible)

    def search_catalog(
        self,
        *,
        caller: CallerIdentity,
        request: SkillDiscoveryRequest,
        limit: int,
    ) -> tuple[SkillVersionDetail, ...]:
        """Return card-ready current-default skill metadata in discovery order."""
        if self._discovery_service is None:
            raise RuntimeError("Skill discovery service is not configured.")

        candidate_slugs = self._discovery_service.discover_candidates(
            caller=caller,
            request=request,
        )
        details: list[SkillVersionDetail] = []
        for slug in candidate_slugs:
            stored_versions = self._repository.list_versions(slug=slug)
            visible_versions = tuple(
                stored
                for stored in stored_versions
                if self._governance_policy.is_visible_in_list(
                    caller=caller,
                    lifecycle_status=stored.lifecycle_status,
                    namespace=stored.namespace,
                    review_state=stored.review_state,
                    promotion_channel=stored.promotion_channel,
                    trust_tier=stored.trust_tier,
                    policy_pack=stored.policy_pack,
                )
            )
            current_default = select_current_default_version(visible_versions)
            if current_default is None:
                continue

            detail = self._repository.get_version_detail(
                slug=slug,
                version=current_default.version,
            )
            if detail is None:
                continue
            if self._governance_policy.is_visible_in_list(
                caller=caller,
                lifecycle_status=detail.lifecycle_status,
                namespace=detail.namespace,
                review_state=detail.review_state,
                promotion_channel=detail.promotion_channel,
                trust_tier=detail.trust_tier,
                policy_pack=detail.policy_pack,
            ):
                details.append(detail)
            if len(details) >= limit:
                break
        return tuple(details)
