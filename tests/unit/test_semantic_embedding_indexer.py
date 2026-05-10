"""Unit tests for semantic embedding indexing orchestration."""

from __future__ import annotations

import pytest

from app.core.ports import SkillEmbeddingIndexRecord, SkillEmbeddingWorkItem
from app.core.skills.embedding_indexing import SemanticEmbeddingIndexer


class _IndexPort:
    def __init__(self, work_items: tuple[SkillEmbeddingWorkItem, ...]) -> None:
        self.work_items = work_items
        self.backfills: list[tuple[str, int]] = []
        self.claims: list[tuple[str, int, int]] = []
        self.indexed: list[SkillEmbeddingIndexRecord] = []
        self.failed: list[tuple[int, str, str]] = []

    def backfill_pending_skill_embeddings(
        self,
        *,
        embedding_model: str,
        embedding_dimensions: int,
    ) -> int:
        self.backfills.append((embedding_model, embedding_dimensions))
        return 2

    def claim_skill_embedding_work(
        self,
        *,
        embedding_model: str,
        limit: int,
        reclaim_after_seconds: int,
    ) -> tuple[SkillEmbeddingWorkItem, ...]:
        self.claims.append((embedding_model, limit, reclaim_after_seconds))
        return self.work_items

    def index_skill_embedding(self, *, record: SkillEmbeddingIndexRecord) -> None:
        self.indexed.append(record)

    def mark_skill_embedding_failed(
        self,
        *,
        skill_version_fk: int,
        embedding_model: str,
        error: str,
    ) -> None:
        self.failed.append((skill_version_fk, embedding_model, error))


class _Provider:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[tuple[str, str, int, int]] = []

    def embed_query(
        self,
        *,
        text: str,
        model: str,
        dimensions: int,
        timeout_ms: int,
    ) -> tuple[float, ...]:
        self.calls.append((text, model, dimensions, timeout_ms))
        if self.should_fail:
            raise TimeoutError("provider timed out")
        return tuple(0.1 for _ in range(dimensions))


@pytest.mark.unit
def test_indexer_backfills_claims_and_indexes_valid_work() -> None:
    work = SkillEmbeddingWorkItem(
        skill_version_fk=10,
        embedding_model="openai:text-embedding-3-small:description-tags-v1",
        embedding_dimensions=3,
        source_checksum_digest="a" * 64,
        source_text="static checks python",
    )
    index_port = _IndexPort((work,))
    provider = _Provider()
    indexer = SemanticEmbeddingIndexer(
        index_port=index_port,
        embedding_provider=provider,
        provider_model="text-embedding-3-small",
        embedding_index_key=work.embedding_model,
        embedding_dimensions=3,
        timeout_ms=250,
    )

    result = indexer.run_batch(batch_size=25, reclaim_after_seconds=3600)

    assert result.backfilled == 2
    assert result.claimed == 1
    assert result.indexed == 1
    assert result.failed == 0
    assert provider.calls == [("static checks python", "text-embedding-3-small", 3, 250)]
    assert index_port.indexed == [
        SkillEmbeddingIndexRecord(
            skill_version_fk=10,
            embedding_model=work.embedding_model,
            embedding_dimensions=3,
            source_checksum_digest="a" * 64,
            embedding_vector=(0.1, 0.1, 0.1),
        )
    ]


@pytest.mark.unit
def test_indexer_marks_empty_sources_failed_without_provider_call() -> None:
    work = SkillEmbeddingWorkItem(
        skill_version_fk=11,
        embedding_model="openai:text-embedding-3-small:description-tags-v1",
        embedding_dimensions=3,
        source_checksum_digest="b" * 64,
        source_text="",
    )
    index_port = _IndexPort((work,))
    provider = _Provider()
    indexer = SemanticEmbeddingIndexer(
        index_port=index_port,
        embedding_provider=provider,
        provider_model="text-embedding-3-small",
        embedding_index_key=work.embedding_model,
        embedding_dimensions=3,
        timeout_ms=250,
    )

    result = indexer.run_batch(batch_size=25, reclaim_after_seconds=3600)

    assert result.indexed == 0
    assert result.failed == 1
    assert provider.calls == []
    assert index_port.failed == [(11, work.embedding_model, "empty semantic source")]


@pytest.mark.unit
def test_indexer_marks_provider_failures_failed() -> None:
    work = SkillEmbeddingWorkItem(
        skill_version_fk=12,
        embedding_model="openai:text-embedding-3-small:description-tags-v1",
        embedding_dimensions=3,
        source_checksum_digest="c" * 64,
        source_text="static checks python",
    )
    index_port = _IndexPort((work,))
    indexer = SemanticEmbeddingIndexer(
        index_port=index_port,
        embedding_provider=_Provider(should_fail=True),
        provider_model="text-embedding-3-small",
        embedding_index_key=work.embedding_model,
        embedding_dimensions=3,
        timeout_ms=250,
    )

    result = indexer.run_batch(batch_size=25, reclaim_after_seconds=3600)

    assert result.indexed == 0
    assert result.failed == 1
    assert index_port.failed == [(12, work.embedding_model, "TimeoutError: provider timed out")]
