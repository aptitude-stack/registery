"""Core ports that define boundary contracts for infrastructure adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol

from app.core.governance import (
    ArtifactOrigin,
    CallerScope,
    LifecycleStatus,
    NamespaceGrant,
    PolicyPack,
    PromotionChannel,
    ProvenanceMetadata,
    ReviewState,
    TrustTier,
)
from app.core.skills.models import (
    NamespaceRecord,
    OrganizationRecord,
    PolicyPackRecord,
    SkillContentRecord,
    SkillOwnershipUpdate,
    SkillRelationshipSource,
    SkillVersionDetail,
    SkillVersionGovernanceUpdate,
    SkillVersionListEntry,
    SkillVersionStatusUpdate,
    TrustEvidenceRecord,
)

RelationshipEdgeType = Literal[
    "depends_on",
    "extends",
    "conflicts_with",
    "overlaps_with",
]


@dataclass(frozen=True, slots=True)
class AuditEventRecord:
    """One structured audit event produced by the core layer."""

    event_type: str
    payload: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ServiceTokenRecord:
    """One governed service-token record used for bearer authentication."""

    token_id: str
    secret_digest: str
    scopes: frozenset[CallerScope]
    active: bool
    namespace_grants: tuple[NamespaceGrant, ...] = ()
    expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ContentRecordInput:
    """Normalized bundle artifact persisted for one immutable version."""

    payload: bytes
    media_type: str
    size_bytes: int
    checksum_digest: str


@dataclass(frozen=True, slots=True)
class MetadataRecordInput:
    """Structured metadata persisted for one immutable version."""

    name: str
    description: str | None
    tags: tuple[str, ...]
    inputs_schema: dict[str, Any] | None
    outputs_schema: dict[str, Any] | None
    token_estimate: int | None
    maturity_score: float | None
    security_score: float | None


@dataclass(frozen=True, slots=True)
class RelationshipSelectorRecordInput:
    """One authored selector preserved exactly as published."""

    edge_type: RelationshipEdgeType
    ordinal: int
    slug: str
    version: str | None
    version_constraint: str | None
    optional: bool | None
    markers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GovernanceRecordInput:
    """Governance metadata persisted for one immutable version."""

    trust_tier: TrustTier
    provenance: ProvenanceMetadata | None
    namespace: str
    artifact_origin: ArtifactOrigin
    review_state: ReviewState
    promotion_channel: PromotionChannel
    policy_pack_slug: str | None


@dataclass(frozen=True, slots=True)
class CreateSkillVersionRecord:
    """Persistence payload for one immutable version creation."""

    slug: str
    version: str
    content: ContentRecordInput
    metadata: MetadataRecordInput
    governance: GovernanceRecordInput
    relationships: tuple[RelationshipSelectorRecordInput, ...]
    version_checksum_digest: str


@dataclass(frozen=True, slots=True)
class SearchCandidatesRequest:
    """Normalized discovery request sent to the persistence search adapter."""

    query_text: str | None
    required_tags: tuple[str, ...]
    fresh_within_days: int | None
    max_content_size_bytes: int | None
    lifecycle_statuses: tuple[LifecycleStatus, ...]
    trust_tiers: tuple[TrustTier, ...]
    namespaces: tuple[str, ...] | None
    promotion_channels: tuple[PromotionChannel, ...] | None
    review_states: tuple[ReviewState, ...]
    limit: int


@dataclass(frozen=True, slots=True)
class StoredSkillSearchCandidate:
    """Persistence projection for one ranked search candidate."""

    slug: str
    version: str
    name: str
    description: str | None
    tags: tuple[str, ...]
    lifecycle_status: LifecycleStatus
    trust_tier: TrustTier
    namespace: str
    artifact_origin: ArtifactOrigin
    review_state: ReviewState
    promotion_channel: PromotionChannel
    policy_pack: PolicyPack | None
    published_at: datetime
    content_size_bytes: int
    usage_count: int
    exact_slug_match: bool
    exact_name_match: bool
    lexical_score: float
    tag_overlap_count: int


class SkillRegistryPersistenceError(RuntimeError):
    """Raised for non-domain-specific persistence failures."""


class DuplicateSkillVersionPersistenceError(SkillRegistryPersistenceError):
    """Raised when the immutable `(slug, version)` already exists."""


class DuplicateSkillSlugPersistenceError(SkillRegistryPersistenceError):
    """Raised when the stable skill slug already exists."""


class SkillCatalogRepository(Protocol):
    """Unified persistence contract for the skill catalog."""

    def skill_exists(self, *, slug: str) -> bool:
        """Return whether a skill identity already exists."""

    def version_exists(self, *, slug: str, version: str) -> bool:
        """Return whether a skill version already exists."""

    def create_version(
        self,
        *,
        record: CreateSkillVersionRecord,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> SkillVersionDetail:
        """Create one immutable normalized version."""

    def get_version_detail(self, *, slug: str, version: str) -> SkillVersionDetail | None:
        """Return one immutable version detail for exact read or lifecycle paths."""

    def get_version_content(
        self,
        *,
        slug: str,
        version: str,
    ) -> SkillContentRecord | None:
        """Return one immutable content record for exact content reads."""

    def list_versions(self, *, slug: str) -> tuple[SkillVersionListEntry, ...]:
        """Return version-list rows for one skill identity."""

    def get_relationship_source(
        self,
        *,
        slug: str,
        version: str,
    ) -> SkillRelationshipSource | None:
        """Return exact authored relationships for one immutable coordinate."""

    def search_candidates(
        self,
        *,
        request: SearchCandidatesRequest,
    ) -> tuple[StoredSkillSearchCandidate, ...]:
        """Return ranked skill candidates for the provided discovery request."""

    def record_install(self, *, slug: str, version: str) -> None:
        """Record one successful skill install/download for an exact coordinate."""

    def update_version_status(
        self,
        *,
        slug: str,
        version: str,
        lifecycle_status: LifecycleStatus,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> SkillVersionStatusUpdate | None:
        """Update lifecycle state for one immutable version and return the new projection."""

    def create_organization(
        self,
        *,
        slug: str,
        display_name: str,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> OrganizationRecord:
        """Create one organization record."""

    def create_namespace(
        self,
        *,
        slug: str,
        organization_slug: str,
        visibility: str,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> NamespaceRecord:
        """Create one namespace record."""

    def upsert_policy_pack(
        self,
        *,
        slug: str,
        description: str | None,
        rules: dict[str, Any],
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> PolicyPackRecord:
        """Create or update one policy pack."""

    def update_skill_ownership(
        self,
        *,
        slug: str,
        namespace: str,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> SkillOwnershipUpdate | None:
        """Move a skill identity into a namespace."""

    def update_version_governance(
        self,
        *,
        slug: str,
        version: str,
        review_state: ReviewState | None = None,
        promotion_channel: PromotionChannel | None = None,
        trust_tier: TrustTier | None = None,
        policy_pack_slug: str | None = None,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> SkillVersionGovernanceUpdate | None:
        """Update mutable enterprise governance state for one immutable version."""

    def add_trust_evidence(
        self,
        *,
        slug: str,
        version: str,
        evidence_type: str,
        subject: str,
        digest: str | None,
        uri: str | None,
        payload: dict[str, Any] | None,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> TrustEvidenceRecord | None:
        """Append one trust evidence row to a version."""


class AuditPort(Protocol):
    """Audit recording contract used by core services."""

    def record_event(self, *, event_type: str, payload: dict[str, Any] | None = None) -> None:
        """Persist a domain audit event."""


class ServiceTokenLookupPort(Protocol):
    """Lookup contract for governed service-token records."""

    def get_token(self, *, token_id: str) -> ServiceTokenRecord | None:
        """Return one governed service-token record by token id."""


class DatabaseReadinessPort(Protocol):
    """Contract for probing database readiness from the core layer."""

    def ping(self) -> tuple[bool, str | None]:
        """Return `(is_ready, detail)`."""
