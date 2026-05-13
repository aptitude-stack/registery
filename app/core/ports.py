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
class SearchSemanticCandidatesRequest:
    """Governance-safe semantic retrieval request sent to persistence."""

    query_embedding: tuple[float, ...]
    embedding_model: str
    embedding_dimensions: int
    required_tags: tuple[str, ...]
    fresh_within_days: int | None
    max_content_size_bytes: int | None
    lifecycle_statuses: tuple[LifecycleStatus, ...]
    trust_tiers: tuple[TrustTier, ...]
    namespaces: tuple[str, ...] | None
    promotion_channels: tuple[PromotionChannel, ...] | None
    review_states: tuple[ReviewState, ...]
    limit: int
    hnsw_ef_search: int


@dataclass(frozen=True, slots=True)
class CoUsageBoostRequest:
    """Candidate/context pair request for bounded co-usage boosts."""

    context_skill_slugs: tuple[str, ...]
    candidate_slugs: tuple[str, ...]
    boost_cap: float


@dataclass(frozen=True, slots=True)
class SkillEmbeddingIndexRecord:
    """One derived embedding ready to mark as indexed."""

    skill_version_fk: int
    embedding_model: str
    embedding_dimensions: int
    source_checksum_digest: str
    embedding_vector: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class SkillEmbeddingWorkItem:
    """One claimed semantic embedding row ready for provider indexing."""

    skill_version_fk: int
    embedding_model: str
    embedding_dimensions: int
    source_checksum_digest: str
    source_text: str


@dataclass(frozen=True, slots=True)
class CoUsageObservationImportRecord:
    """One trusted resolver outcome used to rebuild co-usage aggregates."""

    source: str
    source_digest: str
    observed_at: datetime
    skill_slugs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StoredSkillSearchCandidate:
    """Persistence projection for one ranked search candidate."""

    skill_version_fk: int
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
    semantic_distance: float | None = None


class SkillRegistryPersistenceError(RuntimeError):
    """Raised for non-domain-specific persistence failures."""


class DuplicateSkillVersionPersistenceError(SkillRegistryPersistenceError):
    """Raised when the immutable `(slug, version)` already exists."""


class DuplicateSkillSlugPersistenceError(SkillRegistryPersistenceError):
    """Raised when the stable skill slug already exists."""


class SkillPublishPort(Protocol):
    """Persistence capability for immutable publish operations."""

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


class SkillExactReadPort(Protocol):
    """Persistence capability for exact immutable metadata and content reads."""

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


class SkillFetchPort(SkillExactReadPort, Protocol):
    """Persistence capability for exact fetch plus install telemetry."""

    def record_install(self, *, slug: str, version: str) -> None:
        """Record one successful skill install/download for an exact coordinate."""


class SkillResolutionPort(Protocol):
    """Persistence capability for exact authored dependency reads."""

    def get_relationship_source(
        self,
        *,
        slug: str,
        version: str,
    ) -> SkillRelationshipSource | None:
        """Return exact authored relationships for one immutable coordinate."""


class SkillDiscoverySearchPort(Protocol):
    """Persistence capability for discovery candidate retrieval."""

    def search_candidates(
        self,
        *,
        request: SearchCandidatesRequest,
    ) -> tuple[StoredSkillSearchCandidate, ...]:
        """Return ranked skill candidates for the provided discovery request."""

    def search_semantic_candidates(
        self,
        *,
        request: SearchSemanticCandidatesRequest,
    ) -> tuple[StoredSkillSearchCandidate, ...]:
        """Return semantically similar candidates within governance-safe filters."""

    def backfill_pending_skill_embeddings(
        self,
        *,
        embedding_model: str,
        embedding_dimensions: int,
    ) -> int:
        """Create missing pending semantic embedding rows for indexed skill documents."""

    def claim_skill_embedding_work(
        self,
        *,
        embedding_model: str,
        limit: int,
        reclaim_after_seconds: int,
    ) -> tuple[SkillEmbeddingWorkItem, ...]:
        """Claim pending, stale, or abandoned semantic embedding rows for indexing."""

    def get_co_usage_boosts(self, *, request: CoUsageBoostRequest) -> dict[str, float]:
        """Return bounded co-usage boosts for visible candidate slugs."""


class SkillGovernanceAdminPort(Protocol):
    """Persistence capability for mutable governance administration."""

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


class SkillRegistryPort(
    SkillPublishPort,
    SkillExactReadPort,
    SkillGovernanceAdminPort,
    Protocol,
):
    """Persistence capability set used by the registry write/admin service."""


class SkillCatalogRepository(
    SkillRegistryPort,
    SkillFetchPort,
    SkillDiscoverySearchPort,
    SkillResolutionPort,
    Protocol,
):
    """Compatibility composition for the SQLAlchemy catalog adapter."""


class AuditPort(Protocol):
    """Audit recording contract used by core services."""

    def record_event(self, *, event_type: str, payload: dict[str, Any] | None = None) -> None:
        """Persist a domain audit event."""


class EmbeddingProviderPort(Protocol):
    """Embedding generation contract used by semantic discovery."""

    def embed_query(
        self,
        *,
        text: str,
        model: str,
        dimensions: int,
        timeout_ms: int,
    ) -> tuple[float, ...]:
        """Return one query embedding for semantic candidate expansion."""


class EmbeddingIndexPort(Protocol):
    """Embedding indexing contract for derived semantic discovery rows."""

    def backfill_pending_skill_embeddings(
        self,
        *,
        embedding_model: str,
        embedding_dimensions: int,
    ) -> int:
        """Create missing pending semantic embedding rows for indexed skill documents."""

    def claim_skill_embedding_work(
        self,
        *,
        embedding_model: str,
        limit: int,
        reclaim_after_seconds: int,
    ) -> tuple[SkillEmbeddingWorkItem, ...]:
        """Claim pending, stale, or abandoned semantic embedding rows for indexing."""

    def index_skill_embedding(self, *, record: SkillEmbeddingIndexRecord) -> None:
        """Persist one validated indexed skill embedding."""

    def mark_skill_embedding_failed(
        self,
        *,
        skill_version_fk: int,
        embedding_model: str,
        error: str,
    ) -> None:
        """Record indexing failure without affecting publish success."""


class CoUsageObservationImportPort(Protocol):
    """Dormant import contract for future trusted resolver co-usage evidence."""

    def import_observation_run(self, *, record: CoUsageObservationImportRecord) -> None:
        """Import one selected-skill outcome for aggregate rebuilds."""


class ServiceTokenLookupPort(Protocol):
    """Lookup contract for governed service-token records."""

    def get_token(self, *, token_id: str) -> ServiceTokenRecord | None:
        """Return one governed service-token record by token id."""


class DatabaseReadinessPort(Protocol):
    """Contract for probing database readiness from the core layer."""

    def ping(self) -> tuple[bool, str | None]:
        """Return `(is_ready, detail)`."""
