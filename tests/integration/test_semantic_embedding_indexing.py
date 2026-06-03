"""Integration tests for semantic embedding indexing workflow state."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.ports import SkillEmbeddingIndexRecord
from app.core.semantic_defaults import (
    DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS,
    DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
    DEFAULT_SEMANTIC_RECLAIM_AFTER_SECONDS,
)
from app.main import create_app
from app.persistence.db import get_session_factory
from app.persistence.skill_registry_repository import SQLAlchemySkillCatalogRepository
from tests.integration.skill_endpoint_helpers import _publish, _request


@pytest.mark.integration
def test_embedding_indexer_claims_indexes_and_ignores_old_index_keys(
    migrated_registry_database: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    monkeypatch.setenv("SEMANTIC_EMBEDDING_INDEX_KEY", DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY)
    slug = f"python-semantic-indexing-{uuid4().hex}"

    with TestClient(create_app()) as client:
        _publish(
            client,
            slug,
            _request(
                "1.0.0",
                name="Python Semantic Identity",
                description="Static checks for Python services",
                tags=["python", "quality"],
            ),
        )
        repository = SQLAlchemySkillCatalogRepository(
            get_session_factory(),
            semantic_embedding_index_key=DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
        )

        inserted = repository.backfill_pending_skill_embeddings(
            embedding_model=DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
            embedding_dimensions=DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS,
        )
        work_items = repository.claim_skill_embedding_work(
            embedding_model=DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
            limit=1,
            reclaim_after_seconds=DEFAULT_SEMANTIC_RECLAIM_AFTER_SECONDS,
        )

        assert inserted == 0
        assert len(work_items) == 1
        work_item = work_items[0]
        assert work_item.source_text == "static checks for python services python quality"
        assert "python-semantic-indexing" not in work_item.source_text
        assert work_item.embedding_model == DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY

        repository.index_skill_embedding(
            record=SkillEmbeddingIndexRecord(
                skill_version_fk=work_item.skill_version_fk,
                embedding_model=DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
                embedding_dimensions=DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS,
                source_checksum_digest=work_item.source_checksum_digest,
                embedding_vector=tuple(0.01 for _ in range(DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS)),
            )
        )

    engine = create_engine(migrated_registry_database)
    try:
        with engine.connect() as connection:
            rows = (
                connection.execute(
                    text(
                        """
                        SELECT
                            embedding_model,
                            index_status,
                            embedding_vector IS NOT NULL AS has_vector
                        FROM skill_search_embeddings
                        JOIN skill_versions
                            ON skill_versions.id = skill_search_embeddings.skill_version_fk
                        JOIN skills
                            ON skills.id = skill_versions.skill_fk
                        WHERE skills.slug = :slug
                        ORDER BY embedding_model
                        """
                    ),
                    {"slug": slug},
                )
                .mappings()
                .all()
            )
    finally:
        engine.dispose()

    assert rows == [
        {
            "embedding_model": DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
            "index_status": "indexed",
            "has_vector": True,
        }
    ]


@pytest.mark.integration
def test_embedding_indexer_reclaims_stale_processing_rows_and_records_failures(
    migrated_registry_database: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    monkeypatch.setenv("SEMANTIC_EMBEDDING_INDEX_KEY", DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY)
    slug = f"python-semantic-failure-{uuid4().hex}"

    with TestClient(create_app()) as client:
        _publish(
            client,
            slug,
            _request(
                "1.0.0",
                name="Python Semantic Failure",
                description="Semantic failure handling",
                tags=["python", "quality"],
            ),
        )
        repository = SQLAlchemySkillCatalogRepository(
            get_session_factory(),
            semantic_embedding_index_key=DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
        )
        first_claim = repository.claim_skill_embedding_work(
            embedding_model=DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
            limit=1,
            reclaim_after_seconds=DEFAULT_SEMANTIC_RECLAIM_AFTER_SECONDS,
        )
        assert len(first_claim) == 1
        assert (
            repository.claim_skill_embedding_work(
                embedding_model=DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
                limit=1,
                reclaim_after_seconds=DEFAULT_SEMANTIC_RECLAIM_AFTER_SECONDS,
            )
            == ()
        )

        engine = create_engine(migrated_registry_database)
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        UPDATE skill_search_embeddings
                        SET updated_at = CURRENT_TIMESTAMP - INTERVAL '2 hours'
                        WHERE skill_version_fk = :skill_version_fk
                          AND embedding_model = :embedding_model
                        """
                    ),
                    {
                        "skill_version_fk": first_claim[0].skill_version_fk,
                        "embedding_model": DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
                    },
                )
        finally:
            engine.dispose()

        second_claim = repository.claim_skill_embedding_work(
            embedding_model=DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
            limit=1,
            reclaim_after_seconds=DEFAULT_SEMANTIC_RECLAIM_AFTER_SECONDS,
        )
        assert len(second_claim) == 1
        repository.mark_skill_embedding_failed(
            skill_version_fk=second_claim[0].skill_version_fk,
            embedding_model=DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
            error="provider timeout while indexing embedding row",
        )

    engine = create_engine(migrated_registry_database)
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        """
                        SELECT index_status, last_error, embedding_vector IS NULL AS missing_vector
                        FROM skill_search_embeddings
                        WHERE skill_version_fk = :skill_version_fk
                          AND embedding_model = :embedding_model
                        """
                    ),
                    {
                        "skill_version_fk": first_claim[0].skill_version_fk,
                        "embedding_model": DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
                    },
                )
                .mappings()
                .one()
            )
    finally:
        engine.dispose()

    assert row["index_status"] == "failed"
    assert row["last_error"] == "provider timeout while indexing embedding row"
    assert row["missing_vector"] is True
