"""Discovery-surface DTOs for skill APIs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.skills.normalization import normalize_search_text
from app.interface.dto.skills_shared import normalize_unique_tags


class SkillDiscoveryRequest(BaseModel):
    """Body-based discovery request."""

    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    context_skills: list[str] = Field(default_factory=list, max_length=50)

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Discovery `name` must not be blank.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("tags")
    @classmethod
    def normalize_discovery_tags(cls, value: list[str]) -> list[str]:
        return normalize_unique_tags(value)

    @field_validator("context_skills")
    @classmethod
    def normalize_context_skills(cls, value: list[str]) -> list[str]:
        normalized = [
            normalized_value
            for item in value
            if (normalized_value := normalize_search_text(item)) is not None
        ]
        return list(dict.fromkeys(normalized))


class SkillDiscoveryResponse(BaseModel):
    """Ordered candidate slugs returned by discovery."""

    candidates: list[str]
