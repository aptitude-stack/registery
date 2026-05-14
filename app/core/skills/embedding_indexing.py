"""Application service for indexing derived semantic embedding rows."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.ports import (
    EmbeddingIndexPort,
    EmbeddingProviderPort,
    SkillEmbeddingIndexRecord,
)
from app.intelligence.discovery_signals import validate_embedding_vector


@dataclass(frozen=True, slots=True)
class SemanticEmbeddingIndexingResult:
    """Summary of one semantic embedding indexing batch."""

    backfilled: int
    claimed: int
    indexed: int
    failed: int


class SemanticEmbeddingIndexer:
    """Coordinate backfill, provider embedding calls, and indexed-row writes."""

    def __init__(
        self,
        *,
        index_port: EmbeddingIndexPort,
        embedding_provider: EmbeddingProviderPort,
        provider_model: str,
        embedding_index_key: str,
        embedding_dimensions: int,
        timeout_ms: int,
    ) -> None:
        self._index_port = index_port
        self._embedding_provider = embedding_provider
        self._provider_model = provider_model
        self._embedding_index_key = embedding_index_key
        self._embedding_dimensions = embedding_dimensions
        self._timeout_ms = timeout_ms

    def run_batch(
        self,
        *,
        batch_size: int,
        reclaim_after_seconds: int,
    ) -> SemanticEmbeddingIndexingResult:
        """Backfill missing rows, claim one batch, and index each claimed item."""
        backfilled = self._index_port.backfill_pending_skill_embeddings(
            embedding_model=self._embedding_index_key,
            embedding_dimensions=self._embedding_dimensions,
        )
        work_items = self._index_port.claim_skill_embedding_work(
            embedding_model=self._embedding_index_key,
            limit=batch_size,
            reclaim_after_seconds=reclaim_after_seconds,
        )
        indexed = 0
        failed = 0
        for item in work_items:
            if not item.source_text:
                self._index_port.mark_skill_embedding_failed(
                    skill_version_fk=item.skill_version_fk,
                    embedding_model=item.embedding_model,
                    error="empty semantic source",
                )
                failed += 1
                continue
            try:
                embedding_vector = validate_embedding_vector(
                    self._embedding_provider.embed_query(
                        text=item.source_text,
                        model=self._provider_model,
                        dimensions=item.embedding_dimensions,
                        timeout_ms=self._timeout_ms,
                    ),
                    dimensions=item.embedding_dimensions,
                )
                self._index_port.index_skill_embedding(
                    record=SkillEmbeddingIndexRecord(
                        skill_version_fk=item.skill_version_fk,
                        embedding_model=item.embedding_model,
                        embedding_dimensions=item.embedding_dimensions,
                        source_checksum_digest=item.source_checksum_digest,
                        embedding_vector=embedding_vector,
                    )
                )
                indexed += 1
            except Exception as exc:
                self._index_port.mark_skill_embedding_failed(
                    skill_version_fk=item.skill_version_fk,
                    embedding_model=item.embedding_model,
                    error=_sanitize_error(exc),
                )
                failed += 1
        return SemanticEmbeddingIndexingResult(
            backfilled=backfilled,
            claimed=len(work_items),
            indexed=indexed,
            failed=failed,
        )


def _sanitize_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"[:500]
