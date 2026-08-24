"""Shared DTO helpers and response models for skill APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

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


class SkillMetadataResponse(BaseModel):
    """Full normalized metadata block returned by immutable metadata reads."""

    name: str
    description: str | None
    tags: list[str]
    inputs_schema: dict[str, Any] | None = None
    outputs_schema: dict[str, Any] | None = None
    token_estimate: int | None = None
    maturity_score: float | None = None
    security_score: float | None = None
    overall_score: float | None = None


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
