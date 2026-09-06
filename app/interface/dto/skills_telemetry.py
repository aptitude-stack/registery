"""Public DTOs for per-user star telemetry endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.core.skills.telemetry import MAX_STAR_EVENT_BATCH_SIZE
from app.interface.validation import SLUG_PATTERN

StarEventActionLiteral = Literal["star", "unstar"]
UserSubject = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=320)]


class StarEventRequest(BaseModel):
    """One star/unstar toggle event for a skill identity."""

    slug: Annotated[str, StringConstraints(pattern=SLUG_PATTERN)] = Field(
        description="Stable public slug of the skill identity.",
    )
    action: StarEventActionLiteral = Field(
        description="Whether the event represents a star or unstar toggle.",
    )


class StarEventBatchRequest(BaseModel):
    """Batch envelope for star toggle events emitted by the website."""

    events: Annotated[
        list[StarEventRequest],
        Field(min_length=1, max_length=MAX_STAR_EVENT_BATCH_SIZE),
    ]
    user_subject: UserSubject = Field(
        description="Trusted authenticated user subject for idempotent per-user stars.",
    )


class StarCountResponse(BaseModel):
    """Post-update aggregate star count for one skill identity."""

    slug: str
    star_count: int


class StarEventBatchResponse(BaseModel):
    """Response envelope for a successful star event batch."""

    accepted: int
    counts: list[StarCountResponse]


class UserStarredSkillsResponse(BaseModel):
    """Skill slugs currently starred by one authenticated user."""

    starred_slugs: list[str]
