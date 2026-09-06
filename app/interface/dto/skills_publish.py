"""Publish-surface DTOs for skill APIs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.governance import ArtifactOrigin, TrustTier
from app.core.skills.models import PublishIntent
from app.interface.dto.skills_shared import (
    SkillAssessment,
    normalize_optional_text,
    normalize_required_text,
    normalize_unique_tags,
    validate_dependency_markers,
)
from app.interface.validation import SEMVER_PATTERN, SLUG_PATTERN, VERSION_CONSTRAINT_PATTERN


class DependencySelectorRequest(BaseModel):
    """Direct dependency selector authored for one version."""

    slug: str = Field(
        min_length=1,
        max_length=128,
        pattern=SLUG_PATTERN,
        description="Stable public slug of the dependency skill.",
    )
    version: str | None = Field(
        default=None,
        pattern=SEMVER_PATTERN,
        description="Exact immutable dependency version.",
    )
    version_constraint: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Comma-separated semver comparators.",
    )
    optional: bool | None = Field(
        default=None,
        description="Whether consumers may omit this dependency at runtime.",
    )
    markers: list[str] = Field(
        default_factory=list,
        description="Execution markers preserved exactly as authored.",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("markers")
    @classmethod
    def validate_markers(cls, value: list[str]) -> list[str]:
        return validate_dependency_markers(value)

    @model_validator(mode="after")
    def validate_version_selector(self) -> DependencySelectorRequest:
        if (self.version is None) == (self.version_constraint is None):
            raise ValueError(
                "Dependency selector must include exactly one of `version` or `version_constraint`."
            )
        if self.version_constraint is not None and (
            VERSION_CONSTRAINT_PATTERN.fullmatch(self.version_constraint) is None
        ):
            raise ValueError(
                "Dependency selector `version_constraint` must be a comma-separated list "
                "of semver comparators."
            )
        return self


class ExactRelationshipSelectorRequest(BaseModel):
    """Exact immutable relationship selector for non-dependency edges."""

    slug: str = Field(
        min_length=1,
        max_length=128,
        pattern=SLUG_PATTERN,
        description="Stable public slug of the related skill.",
    )
    version: str = Field(
        pattern=SEMVER_PATTERN,
        description="Exact immutable semantic version of the related skill.",
    )

    model_config = ConfigDict(extra="forbid")


class SkillVersionMetadataRequest(BaseModel):
    """Structured query metadata provided at publish time."""

    name: str = Field(min_length=1, max_length=200, description="Human-readable skill name.")
    description: str | None = Field(
        default=None,
        description="Optional human-readable summary of the skill.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Free-form tags used for categorization and discovery.",
    )
    token_estimate: int | None = Field(
        default=None,
        ge=0,
        description="Approximate token footprint for ranking/filtering.",
    )
    maturity_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Normalized maturity score in the range [0, 1].",
    )
    security_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Normalized security score in the range [0, 1].",
    )
    overall_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Normalized overall score in the range [0, 1].",
    )
    assessment: SkillAssessment | None = Field(
        default=None,
        description="Sanitized quality and security assessment for this immutable version.",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return normalize_unique_tags(value)


class SkillVersionRelationshipsRequest(BaseModel):
    """Grouped authored relationships provided at publish time."""

    depends_on: list[DependencySelectorRequest] = Field(default_factory=list)
    extends: list[ExactRelationshipSelectorRequest] = Field(default_factory=list)
    conflicts_with: list[ExactRelationshipSelectorRequest] = Field(default_factory=list)
    overlaps_with: list[ExactRelationshipSelectorRequest] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class ProvenanceRequest(BaseModel):
    """Minimal publish-time provenance metadata."""

    repo_url: str = Field(min_length=1, max_length=500)
    commit_sha: str = Field(min_length=7, max_length=64, pattern=r"^[0-9A-Fa-f]+$")
    tree_path: str | None = Field(default=None, min_length=1, max_length=500)
    publisher_identity: str | None = Field(default=None, min_length=1, max_length=200)

    model_config = ConfigDict(extra="forbid")

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("commit_sha")
    @classmethod
    def validate_commit_sha(cls, value: str) -> str:
        return normalize_required_text(value).lower()

    @field_validator("tree_path", "publisher_identity")
    @classmethod
    def validate_optional_fields(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class SkillGovernanceRequest(BaseModel):
    """Governance metadata supplied at publish time."""

    trust_tier: TrustTier = "untrusted"
    provenance: ProvenanceRequest | None = None
    namespace: str = Field(default="public", min_length=1, max_length=128)
    artifact_origin: ArtifactOrigin = "internal"
    policy_pack_slug: str | None = Field(default=None, min_length=1, max_length=128)

    model_config = ConfigDict(extra="forbid")

    @field_validator("namespace", "policy_pack_slug")
    @classmethod
    def validate_optional_text_fields(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class SkillVersionCreateRequest(BaseModel):
    """Structured publish metadata for one immutable version under a slug path."""

    intent: PublishIntent = Field(
        description=(
            "Whether this publish creates a new skill identity or adds a version "
            "to an existing skill."
        )
    )
    version: str = Field(
        pattern=SEMVER_PATTERN,
        description="Immutable semantic version being published.",
    )
    metadata: SkillVersionMetadataRequest
    governance: SkillGovernanceRequest = Field(default_factory=SkillGovernanceRequest)
    relationships: SkillVersionRelationshipsRequest = Field(
        default_factory=SkillVersionRelationshipsRequest
    )

    model_config = ConfigDict(extra="forbid")
