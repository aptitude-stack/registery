"""Core ports that define boundary contracts for infrastructure adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol

from app.core.governance import CallerScope, LifecycleStatus, ProvenanceMetadata, TrustTier
from app.core.skills.models import (
    SkillContentRecord,
    SkillRelationshipSource,
    SkillVersionDetail,
    SkillVersionListEntry,
    SkillVersionStatusUpdate,
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
