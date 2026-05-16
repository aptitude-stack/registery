"""Unit tests for the aggregate skill telemetry service."""

from __future__ import annotations

import pytest

from app.core.governance import CallerIdentity
from app.core.skills.models import (
    EmptyStarEventBatchError,
    SkillStarCount,
    StarEvent,
    StarEventBatchTooLargeError,
    UnknownStarEventSkillsError,
)
from app.core.skills.telemetry import (
    MAX_STAR_EVENT_BATCH_SIZE,
    SkillTelemetryService,
)


class FakeTelemetryRepository:
    """In-memory star count store with the same observable behavior as Postgres."""

    def __init__(self, *, initial_counts: dict[str, int] | None = None) -> None:
        self._counts: dict[str, int] = dict(initial_counts or {})
        self.calls: list[tuple[tuple[str, int], ...]] = []

    def apply_star_count_deltas(
        self,
        *,
        deltas: tuple[tuple[str, int], ...],
    ) -> tuple[SkillStarCount, ...]:
        self.calls.append(deltas)
        missing = tuple(slug for slug, _ in deltas if slug not in self._counts)
        if missing:
            raise UnknownStarEventSkillsError(slugs=missing)
        results: list[SkillStarCount] = []
        for slug, delta in deltas:
            current = self._counts[slug] + delta
            new_value = current if current > 0 else 0
            self._counts[slug] = new_value
            results.append(SkillStarCount(slug=slug, star_count=new_value))
        return tuple(results)


def _caller() -> CallerIdentity:
    return CallerIdentity(token_id="telemetry-token", scopes=("telemetry",))


def test_record_star_events_returns_post_update_counts() -> None:
    repository = FakeTelemetryRepository(initial_counts={"python.lint": 3, "python.test": 1})
    service = SkillTelemetryService(repository=repository)

    result = service.record_star_events(
        caller=_caller(),
        events=(
            StarEvent(slug="python.lint", action="star"),
            StarEvent(slug="python.test", action="unstar"),
        ),
    )

    assert result == (
        SkillStarCount(slug="python.lint", star_count=4),
        SkillStarCount(slug="python.test", star_count=0),
    )
    assert repository.calls == [(("python.lint", 1), ("python.test", -1))]


def test_record_star_events_coalesces_duplicate_slugs_in_order() -> None:
    repository = FakeTelemetryRepository(initial_counts={"python.lint": 0, "python.test": 5})
    service = SkillTelemetryService(repository=repository)

    result = service.record_star_events(
        caller=_caller(),
        events=(
            StarEvent(slug="python.lint", action="star"),
            StarEvent(slug="python.test", action="unstar"),
            StarEvent(slug="python.lint", action="unstar"),
            StarEvent(slug="python.lint", action="star"),
        ),
    )

    # python.lint events net to +1, python.test stays at -1.
    assert repository.calls == [(("python.lint", 1), ("python.test", -1))]
    assert result == (
        SkillStarCount(slug="python.lint", star_count=1),
        SkillStarCount(slug="python.test", star_count=4),
    )


def test_record_star_events_clamps_at_zero() -> None:
    repository = FakeTelemetryRepository(initial_counts={"python.lint": 0})
    service = SkillTelemetryService(repository=repository)

    result = service.record_star_events(
        caller=_caller(),
        events=(StarEvent(slug="python.lint", action="unstar"),),
    )

    assert result == (SkillStarCount(slug="python.lint", star_count=0),)


def test_record_star_events_rejects_empty_batch() -> None:
    service = SkillTelemetryService(repository=FakeTelemetryRepository())
    with pytest.raises(EmptyStarEventBatchError):
        service.record_star_events(caller=_caller(), events=())


def test_record_star_events_rejects_oversized_batch() -> None:
    service = SkillTelemetryService(repository=FakeTelemetryRepository())
    events = tuple(
        StarEvent(slug=f"python.lint-{index}", action="star")
        for index in range(MAX_STAR_EVENT_BATCH_SIZE + 1)
    )
    with pytest.raises(StarEventBatchTooLargeError) as info:
        service.record_star_events(caller=_caller(), events=events)
    assert info.value.limit == MAX_STAR_EVENT_BATCH_SIZE
    assert info.value.received == MAX_STAR_EVENT_BATCH_SIZE + 1


def test_record_star_events_propagates_unknown_slug_error() -> None:
    repository = FakeTelemetryRepository(initial_counts={"python.lint": 0})
    service = SkillTelemetryService(repository=repository)

    with pytest.raises(UnknownStarEventSkillsError) as info:
        service.record_star_events(
            caller=_caller(),
            events=(
                StarEvent(slug="python.lint", action="star"),
                StarEvent(slug="python.missing", action="star"),
            ),
        )
    assert "python.missing" in info.value.slugs
