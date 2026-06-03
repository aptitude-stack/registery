"""Enterprise control-plane DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.governance import PromotionChannel, ReviewState, TrustTier
from app.core.skills.normalization import normalize_search_text
from app.interface.dto.skills_shared import normalize_optional_text, normalize_required_text
from app.interface.validation import SEMVER_PATTERN, SLUG_PATTERN


class OrganizationCreateRequest(BaseModel):
    """Request to create one organization."""

    slug: str = Field(pattern=SLUG_PATTERN, max_length=128)
    display_name: str = Field(min_length=1, max_length=200)

    model_config = ConfigDict(extra="forbid")

    @field_validator("slug", "display_name")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return normalize_required_text(value)


class OrganizationResponse(BaseModel):
    """Organization response."""

    slug: str
    display_name: str
    created_at: datetime


class NamespaceCreateRequest(BaseModel):
    """Request to create one namespace."""

    slug: str = Field(pattern=SLUG_PATTERN, max_length=128)
    organization_slug: str = Field(pattern=SLUG_PATTERN, max_length=128)
    visibility: Literal["public", "private"] = "private"

    model_config = ConfigDict(extra="forbid")


class NamespaceResponse(BaseModel):
    """Namespace response."""

    slug: str
    organization_slug: str
    visibility: str
    created_at: datetime


class PolicyPackUpsertRequest(BaseModel):
    """Request to create or update a policy pack."""

    description: str | None = Field(default=None, max_length=500)
    rules: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class PolicyPackResponse(BaseModel):
    """Policy-pack response."""

    slug: str
    description: str | None
    rules: dict[str, Any]


class SkillOwnershipUpdateRequest(BaseModel):
    """Request to move a skill into a namespace."""

    namespace: str = Field(pattern=SLUG_PATTERN, max_length=128)

    model_config = ConfigDict(extra="forbid")


class SkillOwnershipResponse(BaseModel):
    """Skill namespace ownership response."""

    slug: str
    namespace: str


class VersionGovernanceUpdateRequest(BaseModel):
    """Request to update mutable enterprise version governance state."""

    review_state: ReviewState | None = None
    promotion_channel: PromotionChannel | None = None
    trust_tier: TrustTier | None = None
    policy_pack_slug: str | None = Field(default=None, pattern=SLUG_PATTERN, max_length=128)
    note: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")


class VersionGovernanceResponse(BaseModel):
    """Mutable enterprise governance response."""

    slug: str
    version: str
    lifecycle_status: str
    trust_tier: TrustTier
    namespace: str
    artifact_origin: str
    review_state: ReviewState
    promotion_channel: PromotionChannel
    policy_pack_slug: str | None = None


class TrustEvidenceCreateRequest(BaseModel):
    """Request to append trust evidence."""

    evidence_type: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=1, max_length=200)
    digest: str | None = Field(default=None, min_length=7, max_length=128)
    uri: str | None = Field(default=None, min_length=1, max_length=500)
    payload: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("evidence_type", "subject")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("digest", "uri")
    @classmethod
    def validate_optional_text_fields(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class TrustEvidenceResponse(BaseModel):
    """Trust evidence response without raw payload contents."""

    slug: str
    version: str = Field(pattern=SEMVER_PATTERN)
    evidence_type: str
    subject: str
    digest: str | None
    uri: str | None
    created_at: datetime


class CoUsageObservationImportRequest(BaseModel):
    """Trusted resolver co-usage observation import request."""

    source: str = Field(min_length=1, max_length=100)
    source_digest: str = Field(min_length=64, max_length=64)
    observed_at: datetime
    skill_slugs: list[str] = Field(min_length=1, max_length=100)

    model_config = ConfigDict(extra="forbid")

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("source_digest")
    @classmethod
    def validate_source_digest(cls, value: str) -> str:
        digest = value.strip().lower()
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("source_digest must be a 64-character lowercase sha256 hex digest.")
        return digest

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observed_at must include a timezone offset.")
        return value

    @field_validator("skill_slugs")
    @classmethod
    def validate_skill_slugs(cls, value: list[str]) -> list[str]:
        normalized = []
        for item in value:
            slug = normalize_search_text(item)
            if slug is None:
                raise ValueError("skill_slugs must not contain blank values.")
            normalized.append(slug)
        if len(set(normalized)) != len(normalized):
            raise ValueError("skill_slugs must not contain duplicates.")
        return normalized


class CoUsageObservationImportResponse(BaseModel):
    """Summary returned after trusted co-usage observation import."""

    imported: bool
    observations_accepted: int
    pairs_rebuilt: int
    edges_activated: int
    edges_deactivated: int
    duplicate: bool = False
