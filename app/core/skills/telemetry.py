"""Per-user star telemetry service."""

from __future__ import annotations

from collections.abc import Iterable

from app.core.governance import CallerIdentity
from app.core.ports import SkillTelemetryPort

from .models import (
    EmptyStarEventBatchError,
    SkillStarCount,
    StarEvent,
    StarEventBatchTooLargeError,
)

MAX_STAR_EVENT_BATCH_SIZE = 100


class SkillTelemetryService:
    """Apply aggregate and per-user skill telemetry events."""

    def __init__(
        self,
        *,
        repository: SkillTelemetryPort,
        max_batch_size: int = MAX_STAR_EVENT_BATCH_SIZE,
    ) -> None:
        self._repository = repository
        self._max_batch_size = max_batch_size

    def list_user_starred_skill_slugs(
        self,
        *,
        caller: CallerIdentity,
        user_subject: str,
    ) -> tuple[str, ...]:
        """Return skill slugs starred by the provided authenticated user subject."""
        del caller  # The caller scope is enforced at the route layer.
        return self._repository.list_user_starred_skill_slugs(user_subject=user_subject)

    def record_user_star_events(
        self,
        *,
        caller: CallerIdentity,
        user_subject: str,
        events: Iterable[StarEvent],
    ) -> tuple[SkillStarCount, ...]:
        """Apply star/unstar events idempotently for one user subject."""
        del caller  # The caller scope is enforced at the route layer.

        materialized = tuple(events)
        if not materialized:
            raise EmptyStarEventBatchError()
        if len(materialized) > self._max_batch_size:
            raise StarEventBatchTooLargeError(
                limit=self._max_batch_size,
                received=len(materialized),
            )

        return self._repository.apply_user_star_events(
            user_subject=user_subject,
            events=materialized,
        )
