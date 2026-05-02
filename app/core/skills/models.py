"""Core skill registry domain models and errors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from app.core.governance import (
    ArtifactOrigin,
    LifecycleStatus,
    PolicyPack,
    PromotionChannel,
    ProvenanceMetadata,
    ReviewState,
    SkillGovernanceInput,
    TrustTier,
)

SHA256_ALGORITHM = "sha256"
PublishIntent = Literal["create_skill", "publish_version"]


@dataclass(frozen=True, slots=True)
class SkillRelationshipSelector:
    """Authored relationship selector preserved exactly as published."""

    slug: str
    version: str | None = None
    version_constraint: str | None = None
    optional: bool | None = None
    markers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SkillContentInput:
    """Publish-time bundle artifact content."""

    payload: bytes
    media_type: str


@dataclass(frozen=True, slots=True)
class SkillMetadataInput:
    """Publish-time structured metadata."""

    name: str
    description: str | None
    tags: tuple[str, ...]
    inputs_schema: dict[str, Any] | None = None
    outputs_schema: dict[str, Any] | None = None
    token_estimate: int | None = None
    maturity_score: float | None = None
    security_score: float | None = None


@dataclass(frozen=True, slots=True)
class SkillRelationshipsInput:
    """Grouped authored relationships for one immutable version."""

    depends_on: tuple[SkillRelationshipSelector, ...] = ()
    extends: tuple[SkillRelationshipSelector, ...] = ()
    conflicts_with: tuple[SkillRelationshipSelector, ...] = ()
    overlaps_with: tuple[SkillRelationshipSelector, ...] = ()


@dataclass(frozen=True, slots=True)
class CreateSkillVersionCommand:
    """Publish command for one immutable normalized version."""

    slug: str
    intent: PublishIntent
    version: str
    content: SkillContentInput
    metadata: SkillMetadataInput
    relationships: SkillRelationshipsInput
    governance: SkillGovernanceInput = SkillGovernanceInput()


@dataclass(frozen=True, slots=True)
class SkillChecksum:
    """Checksum metadata returned by API responses."""

    algorithm: str
    digest: str


@dataclass(frozen=True, slots=True)
class SkillContentSummary:
    """Compact artifact metadata returned without the full bundle payload."""

    checksum: SkillChecksum
    media_type: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class SkillContentDocument:
    """Full immutable bundle artifact document."""

    payload: bytes
    checksum: SkillChecksum
    media_type: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class SkillContentRecord:
    """Internal exact-read content record including governance state."""

    slug: str
    version: str
    payload: bytes
    checksum: SkillChecksum
    media_type: str
    size_bytes: int
    lifecycle_status: LifecycleStatus
    trust_tier: TrustTier
    namespace: str = "public"
    artifact_origin: ArtifactOrigin = "internal"
    review_state: ReviewState = "approved"
    promotion_channel: PromotionChannel = "prod"
    policy_pack: PolicyPack | None = None


@dataclass(frozen=True, slots=True)
class SkillMetadata:
    """Normalized structured metadata returned to clients."""

    name: str
    description: str | None
    tags: tuple[str, ...]
    inputs_schema: dict[str, Any] | None
    outputs_schema: dict[str, Any] | None
    token_estimate: int | None
    maturity_score: float | None
    security_score: float | None


@dataclass(frozen=True, slots=True)
class SkillVersionDetail:
    """Detailed immutable metadata projection without the bundle payload."""

    slug: str
    version: str
    install_count: int
    version_checksum: SkillChecksum
    content: SkillContentSummary
    metadata: SkillMetadata
    lifecycle_status: LifecycleStatus
    trust_tier: TrustTier
    provenance: ProvenanceMetadata | None
    published_at: datetime
    namespace: str = "public"
    artifact_origin: ArtifactOrigin = "internal"
    review_state: ReviewState = "approved"
    promotion_channel: PromotionChannel = "prod"
    policy_pack: PolicyPack | None = None


@dataclass(frozen=True, slots=True)
class SkillVersionSummary:
    """Identity-level summary for one immutable version."""

    version: str
    lifecycle_status: LifecycleStatus
    trust_tier: TrustTier
    published_at: datetime
    is_current_default: bool
    namespace: str = "public"
    artifact_origin: ArtifactOrigin = "internal"
    review_state: ReviewState = "approved"
    promotion_channel: PromotionChannel = "prod"
    policy_pack_slug: str | None = None


@dataclass(frozen=True, slots=True)
class SkillVersionListEntry:
    """Internal version-list row used before visibility/default selection."""

    slug: str
    version: str
    lifecycle_status: LifecycleStatus
    trust_tier: TrustTier
    published_at: datetime
    namespace: str = "public"
    artifact_origin: ArtifactOrigin = "internal"
    review_state: ReviewState = "approved"
    promotion_channel: PromotionChannel = "prod"
    policy_pack: PolicyPack | None = None


@dataclass(frozen=True, slots=True)
class SkillVersionList:
    """Visible immutable versions for one skill identity."""

    slug: str
    versions: tuple[SkillVersionSummary, ...]


@dataclass(frozen=True, slots=True)
class SkillRelationshipSource:
    """Internal exact-read relationship source including governance state."""

    slug: str
    version: str
    lifecycle_status: LifecycleStatus
    trust_tier: TrustTier
    relationships: tuple[SkillRelationshipSelector, ...]
    namespace: str = "public"
    artifact_origin: ArtifactOrigin = "internal"
    review_state: ReviewState = "approved"
    promotion_channel: PromotionChannel = "prod"
    policy_pack: PolicyPack | None = None


@dataclass(frozen=True, slots=True)
class SkillVersionStatusUpdate:
    """Lifecycle update result returned by the registry API."""

    slug: str
    version: str
    status: LifecycleStatus
    trust_tier: TrustTier
    lifecycle_changed_at: datetime
    is_current_default: bool


@dataclass(frozen=True, slots=True)
class SkillVersionGovernanceUpdate:
    """Enterprise governance update result returned by admin APIs."""

    slug: str
    version: str
    lifecycle_status: LifecycleStatus
    trust_tier: TrustTier
    namespace: str
    artifact_origin: ArtifactOrigin
    review_state: ReviewState
    promotion_channel: PromotionChannel
    policy_pack_slug: str | None


@dataclass(frozen=True, slots=True)
class OrganizationRecord:
    """Enterprise organization record."""

    slug: str
    display_name: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class NamespaceRecord:
    """Enterprise namespace record."""

    slug: str
    organization_slug: str
    visibility: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PolicyPackRecord:
    """Enterprise policy-pack record."""

    slug: str
    description: str | None
    rules: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SkillOwnershipUpdate:
    """Skill namespace ownership update result."""

    slug: str
    namespace: str


@dataclass(frozen=True, slots=True)
class TrustEvidenceRecord:
    """Trust evidence append result returned without raw payload contents."""

    slug: str
    version: str
    evidence_type: str
    subject: str
    digest: str | None
    uri: str | None
    created_at: datetime


class SkillRegistryError(RuntimeError):
    """Base domain error for immutable skill catalog operations."""


class DuplicateSkillVersionError(SkillRegistryError):
    """Raised when immutable skill version already exists."""

    def __init__(self, *, slug: str, version: str) -> None:
        super().__init__(f"Skill version already exists: {slug}@{version}")
        self.slug = slug
        self.version = version


class SkillAlreadyExistsError(SkillRegistryError):
    """Raised when the caller tries to create a skill under an existing slug."""

    def __init__(self, *, slug: str) -> None:
        super().__init__(f"Skill already exists: {slug}")
        self.slug = slug


class SkillNotFoundError(SkillRegistryError):
    """Raised when the caller tries to publish a version under a missing slug."""

    def __init__(self, *, slug: str) -> None:
        super().__init__(f"Skill not found: {slug}")
        self.slug = slug


class SkillVersionNotFoundError(SkillRegistryError):
    """Raised when requested immutable skill version does not exist."""

    def __init__(self, *, slug: str, version: str) -> None:
        super().__init__(f"Skill version not found: {slug}@{version}")
        self.slug = slug
        self.version = version
