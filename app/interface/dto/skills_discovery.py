"""Discovery-surface DTOs for skill APIs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.skills.normalization import normalize_search_text
from app.interface.dto.skills_shared import normalize_required_text, normalize_unique_tags
from app.interface.validation import SEMVER_PATTERN, SLUG_PATTERN


class SkillCoordinateRequest(BaseModel):
    """Exact immutable skill coordinate supplied as discovery context."""

    slug: str = Field(
        min_length=1,
        max_length=128,
        pattern=SLUG_PATTERN,
        description="Stable public slug of a context skill.",
    )
    version: str = Field(
        min_length=1,
        pattern=SEMVER_PATTERN,
        description="Exact immutable semantic version of a context skill.",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("slug", mode="before")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Coordinate slug must be a string.")
        normalized = normalize_search_text(value)
        if normalized is None:
            raise ValueError("Coordinate slug must not be blank.")
        return normalized

    @field_validator("version", mode="before")
    @classmethod
    def normalize_version(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Coordinate version must be a string.")
        return normalize_required_text(value)


class SkillDiscoveryRequest(BaseModel):
    """Body-based discovery request."""

    query: str = Field(min_length=1, max_length=200)
    tags: list[str] = Field(default_factory=list)
    context_skills: list[SkillCoordinateRequest] = Field(default_factory=list, max_length=50)

    model_config = ConfigDict(extra="forbid")

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("tags")
    @classmethod
    def normalize_discovery_tags(cls, value: list[str]) -> list[str]:
        return normalize_unique_tags(value)

    @field_validator("context_skills")
    @classmethod
    def normalize_context_skills(
        cls, value: list[SkillCoordinateRequest]
    ) -> list[SkillCoordinateRequest]:
        normalized: list[SkillCoordinateRequest] = []
        seen: set[tuple[str, str]] = set()
        for coordinate in value:
            key = (coordinate.slug, coordinate.version)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(coordinate)
        return normalized


class SkillDiscoveryResponse(BaseModel):
    """Ordered candidate slugs returned by discovery."""

    candidates: list[str]
