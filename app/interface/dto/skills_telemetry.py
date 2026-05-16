"""Public DTOs for aggregate skill telemetry endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.core.skills.telemetry import MAX_STAR_EVENT_BATCH_SIZE
from app.interface.validation import SLUG_PATTERN

StarEventActionLiteral = Literal["star", "unstar"]


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


class StarCountResponse(BaseModel):
    """Post-update aggregate star count for one skill identity."""

    slug: str
    star_count: int


class StarEventBatchResponse(BaseModel):
    """Response envelope for a successful star event batch."""

    accepted: int
    counts: list[StarCountResponse]
