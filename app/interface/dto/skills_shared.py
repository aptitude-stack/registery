"""Shared DTO helpers and response models for skill APIs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
)

from app.core.governance import TrustTier
from app.interface.validation import MARKER_PATTERN


def normalize_unique_tags(value: list[str]) -> list[str]:
    """Return non-empty tags in first-seen order without duplicates."""
    seen: set[str] = set()
    normalized: list[str] = []
    for item in value:
        tag = item.strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        normalized.append(tag)
    return normalized


def normalize_required_text(value: str) -> str:
    """Trim required text fields and reject blank values."""
    normalized = value.strip()
    if not normalized:
        raise ValueError("Value must not be blank.")
    return normalized


def normalize_optional_text(value: str | None) -> str | None:
    """Trim optional text fields and reject blank-but-present values."""
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError("Value must not be blank.")
    return normalized


def validate_dependency_markers(value: list[str]) -> list[str]:
    """Validate authored dependency markers against the public pattern."""
    for marker in value:
        if MARKER_PATTERN.fullmatch(marker) is None:
            raise ValueError(
                "Dependency markers must contain only letters, numbers, '.', '_', ':', or '-'."
            )
    return value


class ChecksumResponse(BaseModel):
    """Checksum metadata attached to stored content or versions."""

    algorithm: str = Field(description="Checksum algorithm used by the service.")
    digest: str = Field(description="Hex digest returned by the service.")


class SkillContentSummaryResponse(BaseModel):
    """Compact bundle metadata returned without the full bundle payload."""

    checksum: ChecksumResponse
    media_type: str = Field(description="Media type of the stored immutable artifact.")
    size_bytes: int = Field(description="Byte length of the stored immutable artifact.")


class AssessmentFinding(BaseModel):
    """One sanitized security finding safe for public version metadata."""

    check: StrictStr = Field(min_length=1, max_length=1000)
    severity: Literal["low", "medium", "high", "critical"]
    explanation: StrictStr = Field(min_length=1, max_length=1000)

    model_config = ConfigDict(extra="forbid")


class AssessmentMaturity(BaseModel):
    """Quality and performance summary published with a skill version."""

    validation_passed: StrictBool
    validation_score: float = Field(ge=0, le=1)
    upskill_score: float | None = Field(default=None, ge=0, le=1)
    upskill_status: StrictStr = Field(min_length=1, max_length=1000)
    test_case_count: StrictInt = Field(ge=0)
    models_tested: list[StrictStr] = Field(default_factory=list, max_length=100)
    baseline_success_rate: float | None = Field(default=None, ge=0, le=1)
    skilled_success_rate: float | None = Field(default=None, ge=0, le=1)
    warnings: list[StrictStr] = Field(default_factory=list, max_length=100)
    warnings_omitted: StrictInt = Field(default=0, ge=0)
    models_omitted: StrictInt = Field(default=0, ge=0)

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "validation_score",
        "upskill_score",
        "baseline_success_rate",
        "skilled_success_rate",
        mode="before",
    )
    @classmethod
    def validate_numeric_scores(cls, value: object) -> object:
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise ValueError("Assessment scores must be numbers or null.")
        return value

    @field_validator("models_tested", "warnings")
    @classmethod
    def validate_text_lists(cls, value: list[str]) -> list[str]:
        if any(not isinstance(item, str) or not item.strip() for item in value):
            raise ValueError("Assessment text lists must contain non-empty strings.")
        if any(len(item) > 1000 for item in value):
            raise ValueError("Assessment text items must be at most 1000 characters.")
        return value


class AssessmentSecurity(BaseModel):
    """Security decision and sanitized findings published with a version."""

    scanned: StrictBool
    decision: Literal["allow", "review_required", "block"] | None = None
    checks_run: list[StrictStr] = Field(default_factory=list, max_length=100)
    checks_omitted: StrictInt = Field(default=0, ge=0)
    findings: list[AssessmentFinding] = Field(default_factory=list, max_length=100)
    findings_omitted: StrictInt = Field(default=0, ge=0)

    model_config = ConfigDict(extra="forbid")

    @field_validator("checks_run")
    @classmethod
    def validate_checks(cls, value: list[str]) -> list[str]:
        if any(not isinstance(item, str) or not item.strip() for item in value):
            raise ValueError("Assessment checks must contain non-empty strings.")
        if any(len(item) > 1000 for item in value):
            raise ValueError("Assessment text items must be at most 1000 characters.")
        return value


class SkillAssessment(BaseModel):
    """Strict public assessment contract for one immutable skill version."""

    schema_version: StrictInt
    assessed_at: datetime
    maturity: AssessmentMaturity
    security: AssessmentSecurity

    model_config = ConfigDict(extra="forbid")

    @field_validator("schema_version")
    @classmethod
    def require_supported_schema_version(cls, value: int) -> int:
        if value != 1:
            raise ValueError("Only assessment schema version 1 is supported.")
        return value

    @field_validator("assessed_at", mode="before")
    @classmethod
    def require_timestamp_text(cls, value: object) -> object:
        if not isinstance(value, str):
            raise ValueError("Assessment timestamp must be an ISO-8601 string.")
        return value

    @field_validator("assessed_at")
    @classmethod
    def require_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Assessment timestamp must include a UTC offset.")
        if value.utcoffset() != timedelta(0):
            raise ValueError("Assessment timestamp must be in UTC.")
        return value.astimezone(UTC)


class SkillMetadataResponse(BaseModel):
    """Full normalized metadata block returned by immutable metadata reads."""

    name: str
    description: str | None
    tags: list[str]
    token_estimate: int | None = None
    maturity_score: float | None = None
    security_score: float | None = None
    overall_score: float | None = None
    assessment: SkillAssessment | None = None


class TrustContextResponse(BaseModel):
    """Server-derived trust context returned with advisory provenance."""

    trust_tier: TrustTier
    policy_profile: str


class ProvenanceResponse(BaseModel):
    """Minimal provenance returned by immutable version reads."""

    repo_url: str
    commit_sha: str
    tree_path: str | None = None
    publisher_identity: str | None = None
    trust_context: TrustContextResponse | None = None
