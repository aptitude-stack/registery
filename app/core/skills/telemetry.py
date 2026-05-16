"""Aggregate skill telemetry service for star and similar counter events."""

from __future__ import annotations

from collections import OrderedDict
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
    """Apply aggregate skill telemetry events without per-user state."""

    def __init__(
        self,
        *,
        repository: SkillTelemetryPort,
        max_batch_size: int = MAX_STAR_EVENT_BATCH_SIZE,
    ) -> None:
        self._repository = repository
        self._max_batch_size = max_batch_size

    def record_star_events(
        self,
        *,
        caller: CallerIdentity,
        events: Iterable[StarEvent],
    ) -> tuple[SkillStarCount, ...]:
        """Apply a batch of star/unstar events and return the post-update counts.

        Duplicate slugs in the same batch are coalesced into one net delta to keep
        the persistence update atomic per slug. The returned tuple has one entry
        per unique slug in original encounter order.
        """
        del caller  # The caller scope is enforced at the route layer.

        materialized = tuple(events)
        if not materialized:
            raise EmptyStarEventBatchError()
        if len(materialized) > self._max_batch_size:
            raise StarEventBatchTooLargeError(
                limit=self._max_batch_size,
                received=len(materialized),
            )

        deltas = _coalesce_events(materialized)
        return self._repository.apply_star_count_deltas(deltas=deltas)


def _coalesce_events(events: tuple[StarEvent, ...]) -> tuple[tuple[str, int], ...]:
    """Combine repeated slug events into a single net delta, preserving order."""
    accumulator: OrderedDict[str, int] = OrderedDict()
    for event in events:
        delta = 1 if event.action == "star" else -1
        accumulator[event.slug] = accumulator.get(event.slug, 0) + delta
    return tuple(accumulator.items())
