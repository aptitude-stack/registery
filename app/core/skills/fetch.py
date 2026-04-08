"""Core exact fetch service for immutable metadata and markdown reads."""

from __future__ import annotations

from app.core.audit_events import build_version_list_audit_event
from app.core.governance import CallerIdentity, GovernancePolicy
from app.core.ports import AuditPort, SkillInstallCounterPort, SkillVersionReadPort

from .exact_read import ExactReadAuditInfo, enforce_and_audit_exact_read
from .models import (
    SHA256_ALGORITHM,
    SkillChecksum,
    SkillContentDocument,
    SkillNotFoundError,
    SkillVersionDetail,
    SkillVersionList,
    SkillVersionNotFoundError,
)
from .projections import to_skill_version_detail, to_skill_version_summary
from .version_ordering import select_current_default_version, sort_versions_for_listing


class SkillFetchService:
    """Read-only service for exact immutable metadata and markdown access."""

    def __init__(
        self,
        *,
        version_reader: SkillVersionReadPort,
        audit_recorder: AuditPort,
        governance_policy: GovernancePolicy,
        install_counter: SkillInstallCounterPort,
    ) -> None:
        self._version_reader = version_reader
        self._audit_recorder = audit_recorder
        self._governance_policy = governance_policy
        self._install_counter = install_counter

    def get_version_metadata(
        self,
        *,
        caller: CallerIdentity,
        slug: str,
        version: str,
    ) -> SkillVersionDetail:
        """Return immutable version metadata for one exact coordinate."""
        stored = self._version_reader.get_version(slug=slug, version=version)
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
            surface="metadata",
        )
        detail = to_skill_version_detail(stored=stored)
        return detail

    def get_content(
        self,
        *,
        caller: CallerIdentity,
        slug: str,
        version: str,
    ) -> SkillContentDocument:
        """Return immutable markdown content for one exact coordinate."""
        stored = self._version_reader.get_version_content(slug=slug, version=version)
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
            surface="content",
        )
        document = SkillContentDocument(
            raw_markdown=stored.raw_markdown,
            checksum=SkillChecksum(
                algorithm=SHA256_ALGORITHM,
                digest=stored.checksum_digest,
            ),
            size_bytes=stored.size_bytes,
        )
        self._install_counter.record_install(slug=stored.slug, version=stored.version)
        return document

    def list_versions(
        self,
        *,
        caller: CallerIdentity,
        slug: str,
    ) -> SkillVersionList:
        """Return visible immutable versions for one skill identity."""
        stored_versions = self._version_reader.list_versions(slug=slug)
        if not stored_versions:
            raise SkillNotFoundError(slug=slug)

        visible_versions = tuple(
            stored
            for stored in stored_versions
            if self._governance_policy.is_visible_in_list(
                caller=caller,
                lifecycle_status=stored.lifecycle_status,
            )
        )
        if not visible_versions:
            raise SkillNotFoundError(slug=slug)

        visible_versions = sort_versions_for_listing(visible_versions)
        current_default = select_current_default_version(visible_versions)
        versions = tuple(
            to_skill_version_summary(
                stored=stored,
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
