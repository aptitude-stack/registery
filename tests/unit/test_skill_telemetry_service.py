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

    def list_user_starred_skill_slugs(self, *, user_subject: str) -> tuple[str, ...]:
        return tuple(
            slug
            for (stored_user, slug), is_starred in getattr(self, "_user_stars", {}).items()
            if stored_user == user_subject and is_starred
        )

    def apply_user_star_events(
        self,
        *,
        user_subject: str,
        events: tuple[StarEvent, ...],
    ) -> tuple[SkillStarCount, ...]:
        if not hasattr(self, "_user_stars"):
            self._user_stars: dict[tuple[str, str], bool] = {}
        missing = tuple(event.slug for event in events if event.slug not in self._counts)
        if missing:
            raise UnknownStarEventSkillsError(slugs=missing)

        results: list[SkillStarCount] = []
        for event in events:
            key = (user_subject, event.slug)
            was_starred = self._user_stars.get(key, False)
            if event.action == "star" and not was_starred:
                self._user_stars[key] = True
                self._counts[event.slug] += 1
            elif event.action == "unstar" and was_starred:
                self._user_stars[key] = False
                self._counts[event.slug] = max(0, self._counts[event.slug] - 1)
            results.append(SkillStarCount(slug=event.slug, star_count=self._counts[event.slug]))
        return tuple(results)


def _caller() -> CallerIdentity:
    return CallerIdentity(token_id="telemetry-token", scopes=("telemetry",))


def test_record_user_star_events_preserves_event_order() -> None:
    repository = FakeTelemetryRepository(initial_counts={"python-lint": 0, "python-test": 0})
    service = SkillTelemetryService(repository=repository)
    events = (
        StarEvent(slug="python-lint", action="star"),
        StarEvent(slug="python-test", action="star"),
        StarEvent(slug="python-lint", action="unstar"),
        StarEvent(slug="python-lint", action="star"),
    )
    result = service.record_user_star_events(caller=_caller(), user_subject="user", events=events)
    assert [(r.slug, r.star_count) for r in result] == [
        ("python-lint", 1),
        ("python-test", 1),
        ("python-lint", 0),
        ("python-lint", 1),
    ]


def test_record_star_events_clamps_at_zero() -> None:
    repository = FakeTelemetryRepository(initial_counts={"python-lint": 0})
    service = SkillTelemetryService(repository=repository)

    result = service.record_user_star_events(
        user_subject="user",
        caller=_caller(),
        events=(StarEvent(slug="python-lint", action="unstar"),),
    )

    assert result == (SkillStarCount(slug="python-lint", star_count=0),)


def test_record_star_events_rejects_empty_batch() -> None:
    service = SkillTelemetryService(repository=FakeTelemetryRepository())
    with pytest.raises(EmptyStarEventBatchError):
        service.record_user_star_events(user_subject="user", caller=_caller(), events=())


def test_record_star_events_rejects_oversized_batch() -> None:
    service = SkillTelemetryService(repository=FakeTelemetryRepository())
    events = tuple(
        StarEvent(slug=f"python-lint-{index}", action="star")
        for index in range(MAX_STAR_EVENT_BATCH_SIZE + 1)
    )
    with pytest.raises(StarEventBatchTooLargeError) as info:
        service.record_user_star_events(user_subject="user", caller=_caller(), events=events)
    assert info.value.limit == MAX_STAR_EVENT_BATCH_SIZE
    assert info.value.received == MAX_STAR_EVENT_BATCH_SIZE + 1


def test_record_star_events_propagates_unknown_slug_error() -> None:
    repository = FakeTelemetryRepository(initial_counts={"python-lint": 0})
    service = SkillTelemetryService(repository=repository)

    with pytest.raises(UnknownStarEventSkillsError) as info:
        service.record_user_star_events(
            user_subject="user",
            caller=_caller(),
            events=(
                StarEvent(slug="python-lint", action="star"),
                StarEvent(slug="python-missing", action="star"),
            ),
        )
    assert "python-missing" in info.value.slugs


def test_record_user_star_events_is_idempotent_per_user() -> None:
    repository = FakeTelemetryRepository(initial_counts={"python-lint": 0})
    service = SkillTelemetryService(repository=repository)

    first = service.record_user_star_events(
        caller=_caller(),
        user_subject="test1@example.com",
        events=(StarEvent(slug="python-lint", action="star"),),
    )
    duplicate = service.record_user_star_events(
        caller=_caller(),
        user_subject="test1@example.com",
        events=(StarEvent(slug="python-lint", action="star"),),
    )
    second_user = service.record_user_star_events(
        caller=_caller(),
        user_subject="test2@example.com",
        events=(StarEvent(slug="python-lint", action="star"),),
    )
    duplicate_unstar = service.record_user_star_events(
        caller=_caller(),
        user_subject="test1@example.com",
        events=(
            StarEvent(slug="python-lint", action="unstar"),
            StarEvent(slug="python-lint", action="unstar"),
        ),
    )

    assert first == (SkillStarCount(slug="python-lint", star_count=1),)
    assert duplicate == (SkillStarCount(slug="python-lint", star_count=1),)
    assert second_user == (SkillStarCount(slug="python-lint", star_count=2),)
    assert duplicate_unstar[-1] == SkillStarCount(slug="python-lint", star_count=1)
    assert repository.list_user_starred_skill_slugs(user_subject="test1@example.com") == ()
    assert repository.list_user_starred_skill_slugs(user_subject="test2@example.com") == (
        "python-lint",
    )
