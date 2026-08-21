"""Unit tests for core discovery/search orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

from app.core.governance import CallerIdentity, GovernancePolicy, build_default_policy_profile
from app.core.ports import (
    CoUsageBoostRequest,
    SearchCandidatesRequest,
    SearchSemanticCandidatesRequest,
    StoredSkillSearchCandidate,
)
from app.core.semantic_defaults import DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY
from app.core.skills import search as search_module
from app.core.skills.discovery import SkillDiscoveryRequest, SkillDiscoveryService
from app.core.skills.search import SkillSearchQuery, SkillSearchService


def _candidate(slug: str, *, lexical_score: float = 0.1) -> StoredSkillSearchCandidate:
    return StoredSkillSearchCandidate(
        skill_version_fk=1,
        slug=slug,
        version="1.0.0",
        name=slug,
        description=None,
        tags=(),
        lifecycle_status="published",
        trust_tier="internal",
        namespace="public",
        artifact_origin="internal",
        review_state="approved",
        promotion_channel="prod",
        policy_pack=None,
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        content_size_bytes=100,
        usage_count=0,
        exact_slug_match=False,
        exact_name_match=False,
        lexical_score=lexical_score,
        tag_overlap_count=0,
    )


class _AuditRecorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any] | None]] = []

    def record_event(self, *, event_type: str, payload: dict[str, Any] | None = None) -> None:
        self.events.append((event_type, payload))


class _Repository:
    def __init__(
        self,
        *,
        lexical: tuple[StoredSkillSearchCandidate, ...],
        semantic: tuple[StoredSkillSearchCandidate, ...] = (),
        boosts: dict[str, float] | None = None,
        semantic_should_fail: bool = False,
    ) -> None:
        self.lexical = lexical
        self.semantic = semantic
        self.boosts = boosts or {}
        self.semantic_should_fail = semantic_should_fail
        self.search_requests: list[SearchCandidatesRequest] = []
        self.semantic_requests: list[SearchSemanticCandidatesRequest] = []
        self.co_usage_requests: list[CoUsageBoostRequest] = []

    def search_candidates(
        self,
        *,
        request: SearchCandidatesRequest,
    ) -> tuple[StoredSkillSearchCandidate, ...]:
        self.search_requests.append(request)
        return self.lexical

    def search_semantic_candidates(
        self,
        *,
        request: SearchSemanticCandidatesRequest,
    ) -> tuple[StoredSkillSearchCandidate, ...]:
        self.semantic_requests.append(request)
        if self.semantic_should_fail:
            raise RuntimeError("semantic SQL failed")
        return self.semantic

    def get_co_usage_boosts(self, *, request: CoUsageBoostRequest) -> dict[str, float]:
        self.co_usage_requests.append(request)
        return self.boosts


class _EmbeddingProvider:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[str] = []

    def embed_query(
        self,
        *,
        text: str,
        model: str,
        dimensions: int,
        timeout_ms: int,
    ) -> tuple[float, ...]:
        self.calls.append(text)
        if self.should_fail:
            raise TimeoutError("embedding provider timeout")
        return tuple(0.1 for _ in range(dimensions))


def _service(
    repository: _Repository,
    *,
    semantic_mode: str = "off",
    embedding_provider: _EmbeddingProvider | None = None,
    co_usage_enabled: bool = False,
    audit_recorder: _AuditRecorder | None = None,
) -> SkillSearchService:
    return SkillSearchService(
        repository=repository,
        audit_recorder=audit_recorder or _AuditRecorder(),
        governance_policy=GovernancePolicy(profile=build_default_policy_profile()),
        semantic_discovery_mode=semantic_mode,
        embedding_provider=embedding_provider,
        co_usage_ranking_enabled=co_usage_enabled,
    )


def _discovery_service(
    repository: _Repository,
    *,
    semantic_mode: str = "off",
    embedding_provider: _EmbeddingProvider | None = None,
    co_usage_enabled: bool = False,
) -> SkillDiscoveryService:
    return SkillDiscoveryService(
        repository=repository,
        audit_recorder=_AuditRecorder(),
        governance_policy=GovernancePolicy(profile=build_default_policy_profile()),
        semantic_discovery_mode=semantic_mode,
        embedding_provider=embedding_provider,
        semantic_embedding_index_key=DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
        co_usage_ranking_enabled=co_usage_enabled,
    )


def _query(*, context_skills: tuple[str, ...] = ()) -> SkillSearchQuery:
    return SkillSearchQuery(
        q="python lint",
        tags=(),
        language=None,
        fresh_within_days=None,
        max_footprint_bytes=None,
        limit=20,
        context_skills=context_skills,
    )


@pytest.mark.unit
def test_semantic_discovery_off_keeps_lexical_only_path() -> None:
    provider = _EmbeddingProvider()
    repository = _Repository(lexical=(_candidate("python-lint"),))

    results = _service(repository, embedding_provider=provider).search(
        caller=CallerIdentity(token_id="reader", scopes=frozenset({"read"})),
        query=_query(),
    )

    assert tuple(item.slug for item in results) == ("python-lint",)
    assert provider.calls == []
    assert repository.semantic_requests == []


@pytest.mark.unit
def test_shadow_mode_does_not_change_lexical_response() -> None:
    provider = _EmbeddingProvider()
    repository = _Repository(
        lexical=(_candidate("python-lint"),),
        semantic=(_candidate("python-semantic"),),
    )

    results = _service(
        repository,
        semantic_mode="shadow",
        embedding_provider=provider,
    ).search(
        caller=CallerIdentity(token_id="reader", scopes=frozenset({"read"})),
        query=_query(),
    )

    assert tuple(item.slug for item in results) == ("python-lint",)
    assert provider.calls == ["python lint"]
    assert len(repository.semantic_requests) == 1


@pytest.mark.unit
def test_discovery_uses_query_for_lexical_and_semantic_search() -> None:
    provider = _EmbeddingProvider()
    repository = _Repository(lexical=(_candidate("python-lint"),))

    results = _discovery_service(
        repository,
        semantic_mode="hybrid",
        embedding_provider=provider,
    ).discover_candidates(
        caller=CallerIdentity(token_id="reader", scopes=frozenset({"read"})),
        request=SkillDiscoveryRequest(query="  Python Lint  ", tags=("python",)),
    )

    assert results == ("python-lint",)
    assert repository.search_requests[0].identity_query_text == "python lint"
    assert provider.calls == ["python lint"]


@pytest.mark.unit
def test_discovery_projects_context_coordinates_to_unique_slugs_for_co_usage() -> None:
    @dataclass(frozen=True)
    class _Coordinate:
        slug: str
        version: str

    repository = _Repository(
        lexical=(_candidate("python-docs", lexical_score=0.3), _candidate("python-pytest")),
        boosts={"python-pytest": 100.0},
    )

    results = _discovery_service(repository, co_usage_enabled=True).discover_candidates(
        caller=CallerIdentity(token_id="reader", scopes=frozenset({"read"})),
        request=SkillDiscoveryRequest(
            query="python",
            tags=(),
            context_skills=(
                _Coordinate(slug="python-lint", version="1.0.0"),
                _Coordinate(slug="python-lint", version="2.0.0"),
                _Coordinate(slug="python-format", version="1.0.0"),
            ),
        ),
    )

    assert results == ("python-pytest", "python-docs")
    assert repository.co_usage_requests[0].context_skill_slugs == (
        "python-lint",
        "python-format",
    )


@pytest.mark.unit
def test_search_sends_identity_and_full_text_queries_to_repository() -> None:
    repository = _Repository(lexical=(_candidate("documentation-writing"),))

    results = _service(repository).search(
        caller=CallerIdentity(token_id="reader", scopes=frozenset({"read"})),
        query=SkillSearchQuery(
            q="docs",
            tags=(),
            language=None,
            fresh_within_days=None,
            max_footprint_bytes=None,
            limit=20,
        ),
    )

    assert tuple(item.slug for item in results) == ("documentation-writing",)
    assert repository.search_requests[0].identity_query_text == "docs"
    assert repository.search_requests[0].full_text_query_text == "docs documentation"


@pytest.mark.unit
def test_hybrid_mode_degrades_to_lexical_when_embedding_provider_fails() -> None:
    repository = _Repository(lexical=(_candidate("python-lint"),))

    results = _service(
        repository,
        semantic_mode="hybrid",
        embedding_provider=_EmbeddingProvider(should_fail=True),
    ).search(
        caller=CallerIdentity(token_id="reader", scopes=frozenset({"read"})),
        query=_query(),
    )

    assert tuple(item.slug for item in results) == ("python-lint",)
    assert repository.semantic_requests == []


@pytest.mark.unit
def test_hybrid_mode_degrades_to_lexical_when_semantic_sql_fails() -> None:
    provider = _EmbeddingProvider()
    repository = _Repository(
        lexical=(_candidate("python-lint"),),
        semantic_should_fail=True,
    )

    results = _service(
        repository,
        semantic_mode="hybrid",
        embedding_provider=provider,
    ).search(
        caller=CallerIdentity(token_id="reader", scopes=frozenset({"read"})),
        query=_query(),
    )

    assert provider.calls == ["python lint"]
    assert len(repository.semantic_requests) == 1
    assert tuple(item.slug for item in results) == ("python-lint",)


@pytest.mark.unit
def test_hybrid_mode_records_semantic_failure_signal_when_semantic_sql_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _EmbeddingProvider()
    repository = _Repository(
        lexical=(_candidate("python-lint"),),
        semantic_should_fail=True,
    )
    log_extras: list[dict[str, object]] = []

    def record_warning(message: str, *, extra: dict[str, object]) -> None:
        log_extras.append(extra)

    monkeypatch.setattr(search_module.logger, "warning", record_warning)
    results = _service(
        repository,
        semantic_mode="hybrid",
        embedding_provider=provider,
    ).search(
        caller=CallerIdentity(token_id="reader", scopes=frozenset({"read"})),
        query=_query(),
    )

    assert tuple(item.slug for item in results) == ("python-lint",)
    assert log_extras[0]["event_type"] == "semantic.discovery.failed"


@pytest.mark.unit
def test_hybrid_mode_adds_semantic_candidates_after_lexical_candidates() -> None:
    repository = _Repository(
        lexical=(_candidate("python-lint", lexical_score=0.8),),
        semantic=(_candidate("python-static-analysis"),),
    )

    results = _service(
        repository,
        semantic_mode="hybrid",
        embedding_provider=_EmbeddingProvider(),
    ).search(
        caller=CallerIdentity(token_id="reader", scopes=frozenset({"read"})),
        query=_query(),
    )

    assert tuple(item.slug for item in results) == ("python-lint", "python-static-analysis")


@pytest.mark.unit
def test_co_usage_boosts_require_context_skills() -> None:
    repository = _Repository(
        lexical=(_candidate("python-docs", lexical_score=0.3), _candidate("python-pytest")),
        boosts={"python-pytest": 100.0},
    )

    results = _service(repository, co_usage_enabled=True).search(
        caller=CallerIdentity(token_id="reader", scopes=frozenset({"read"})),
        query=_query(context_skills=("python-lint",)),
    )

    assert tuple(item.slug for item in results) == ("python-pytest", "python-docs")
    assert repository.co_usage_requests[0].context_skill_slugs == ("python-lint",)


@pytest.mark.unit
def test_co_usage_boosts_are_not_requested_when_ranking_disabled_even_with_context() -> None:
    repository = _Repository(
        lexical=(_candidate("python-docs", lexical_score=0.3), _candidate("python-pytest")),
        boosts={"python-pytest": 0.05},
    )

    results = _service(repository, co_usage_enabled=False).search(
        caller=CallerIdentity(token_id="reader", scopes=frozenset({"read"})),
        query=_query(context_skills=("python-lint",)),
    )

    assert tuple(item.slug for item in results) == ("python-docs", "python-pytest")
    assert repository.co_usage_requests == []
