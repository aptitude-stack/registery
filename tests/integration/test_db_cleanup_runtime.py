"""Behavioral regressions for counter ownership and body-free reads."""

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import aliased

from app.core.ports import (
    SearchCandidatesRequest,
    SearchSemanticCandidatesRequest,
    SkillEmbeddingIndexRecord,
)
from app.core.semantic_defaults import DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY
from app.core.skills.models import StarEvent
from app.main import create_app
from app.persistence.db import get_session_factory
from app.persistence.models import Skill
from app.persistence.skill_registry_repository import SQLAlchemySkillCatalogRepository
from tests.integration.skill_endpoint_helpers import _headers, _publish, _request


@pytest.mark.integration
def test_metadata_reads_omit_payload_and_new_versions_share_install_count(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    with TestClient(create_app()) as client:
        _publish(client, "cleanup-runtime", _request("1.0.0"))
        factory = get_session_factory()
        repository = SQLAlchemySkillCatalogRepository(session_factory=factory)
        original = repository.get_version_content(slug="cleanup-runtime", version="1.0.0")
        assert original is not None
        repository.record_install(slug="cleanup-runtime", version="1.0.0")
        _publish(client, "cleanup-runtime", _request("1.0.1", intent="publish_version"))
        vector = (0.01,) * 1536
        for work in repository.claim_skill_embedding_work(
            embedding_model=DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
            limit=10,
            reclaim_after_seconds=300,
        ):
            repository.index_skill_embedding(
                record=SkillEmbeddingIndexRecord(
                    skill_version_fk=work.skill_version_fk,
                    embedding_model=work.embedding_model,
                    embedding_dimensions=1536,
                    source_checksum_digest=work.source_checksum_digest,
                    embedding_vector=vector,
                )
            )
        queries: list[str] = []

        def capture(_conn: Any, _cursor: Any, statement: str, *_args: Any) -> None:
            if statement.lstrip().upper().startswith(("SELECT", "WITH")):
                queries.append(statement)

        engine = factory.kw["bind"]
        event.listen(engine, "before_cursor_execute", capture)
        try:
            assert repository.get_version_detail(slug="cleanup-runtime", version="1.0.1")
            assert repository.list_catalog_skill_versions()
            candidates = repository.search_candidates(
                request=SearchCandidatesRequest(
                    identity_query_text="cleanup-runtime",
                    full_text_query_text=None,
                    required_tags=(),
                    fresh_within_days=None,
                    max_content_size_bytes=None,
                    lifecycle_statuses=("published",),
                    trust_tiers=("untrusted",),
                    namespaces=None,
                    promotion_channels=None,
                    review_states=("approved",),
                    limit=10,
                )
            )
            semantic = repository.search_semantic_candidates(
                request=SearchSemanticCandidatesRequest(
                    query_embedding=vector,
                    embedding_model=DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
                    embedding_dimensions=1536,
                    required_tags=(),
                    fresh_within_days=None,
                    max_content_size_bytes=None,
                    lifecycle_statuses=("published",),
                    trust_tiers=("untrusted",),
                    namespaces=None,
                    promotion_channels=None,
                    review_states=("approved",),
                    limit=10,
                    hnsw_ef_search=100,
                )
            )
        finally:
            event.remove(engine, "before_cursor_execute", capture)
        assert {c.version: c.usage_count for c in candidates} == {"1.0.1": 1}
        assert {c.version: c.usage_count for c in semantic} == {"1.0.0": 1, "1.0.1": 1}
        assert all(".payload" not in sql for sql in queries)
        assert len(queries) <= 6  # Detail selectors + catalog + one search, no per-row counts.
        downloaded = repository.get_version_content(slug="cleanup-runtime", version="1.0.0")
        assert downloaded is not None and downloaded.payload == original.payload


@pytest.mark.integration
def test_concurrent_stars_have_one_row_per_user_and_computed_alias_counts(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    with TestClient(create_app()) as client:
        for slug in ("cleanup-star-a", "cleanup-star-b"):
            _publish(client, slug, _request("1.0.0"))
        factory = get_session_factory()
        repository = SQLAlchemySkillCatalogRepository(session_factory=factory)

        def star(index: int) -> None:
            slugs = ("cleanup-star-a", "cleanup-star-b")
            if index % 2:
                slugs = tuple(reversed(slugs))
            repository.apply_user_star_events(
                user_subject=f"user-{index % 2}",
                events=tuple(StarEvent(slug=s, action="star") for s in slugs),
            )

        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(star, range(8)))
        with factory() as session:
            skill = aliased(Skill)
            assert session.execute(
                select(skill.star_count).select_from(skill).order_by(skill.slug)
            ).scalars().all() == [2, 2]
        result = repository.apply_user_star_events(
            user_subject="user-0",
            events=(
                StarEvent(slug="cleanup-star-a", action="unstar"),
                StarEvent(slug="cleanup-star-a", action="unstar"),
            ),
        )
        assert [r.star_count for r in result] == [1, 1]
        response = client.get("/skills/cleanup-star-a/1.0.0", headers=_headers("reader-token"))
        assert response.json()["star_count"] == 1
