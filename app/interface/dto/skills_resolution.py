"""Resolution-surface DTOs for skill APIs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.interface.validation import SEMVER_PATTERN, SLUG_PATTERN, VERSION_CONSTRAINT_PATTERN


class DependencySelectorResponse(BaseModel):
    """Direct dependency selector returned by resolution."""

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
        pattern=VERSION_CONSTRAINT_PATTERN.pattern,
        description="Comma-separated semver comparators.",
    )
    optional: bool | None = Field(default=None)
    markers: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class SkillDependencyResolutionResponse(BaseModel):
    """Exact direct dependency declarations for one immutable version."""

    slug: str
    version: str
    depends_on: list[DependencySelectorResponse]
