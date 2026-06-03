"""Run one or more semantic embedding indexing batches."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if TYPE_CHECKING:
    from app.core.settings import Settings
    from app.core.skills.embedding_indexing import SemanticEmbeddingIndexer

from app.core.skills.embedding_indexing import SemanticEmbeddingIndexingResult  # noqa: E402

logger = logging.getLogger(__name__)


def main() -> None:
    from app.core.settings import get_settings, reset_settings_cache
    from app.persistence.db import dispose_engine

    args = _parse_args()
    reset_settings_cache()
    settings = get_settings()
    indexer = build_indexer(settings=settings)
    if indexer is None:
        print(
            _result_json(
                SemanticEmbeddingIndexingResult(backfilled=0, claimed=0, indexed=0, failed=0)
            )
        )
        dispose_engine()
        return

    total = SemanticEmbeddingIndexingResult(backfilled=0, claimed=0, indexed=0, failed=0)
    for _ in range(args.max_batches):
        result = indexer.run_batch(
            batch_size=args.batch_size,
            reclaim_after_seconds=args.reclaim_after_seconds,
        )
        total = SemanticEmbeddingIndexingResult(
            backfilled=total.backfilled + result.backfilled,
            claimed=total.claimed + result.claimed,
            indexed=total.indexed + result.indexed,
            failed=total.failed + result.failed,
        )
        if result.claimed == 0:
            break

    print(_result_json(total))
    dispose_engine()


def build_indexer(*, settings: Settings) -> SemanticEmbeddingIndexer | None:
    """Build the shared semantic indexing service for CLI/workflow entrypoints."""
    from app.core.skills.embedding_indexing import SemanticEmbeddingIndexer
    from app.integrations.openai_embeddings import OpenAIEmbeddingProvider
    from app.persistence.db import get_session_factory, init_engine
    from app.persistence.skill_registry_repository import SQLAlchemySkillCatalogRepository

    if settings.openai_api_key is None:
        logger.warning("OPENAI_API_KEY is not configured; skipping semantic indexing.")
        return None
    init_engine(
        settings.database_url,
        application_name=f"{settings.app_name}-{settings.app_env}-semantic-indexer",
    )
    repository = SQLAlchemySkillCatalogRepository(
        get_session_factory(),
        semantic_embedding_index_key=settings.semantic_embedding_index_key,
        semantic_embedding_dimensions=settings.semantic_embedding_dimensions,
    )
    provider = OpenAIEmbeddingProvider(api_key=settings.openai_api_key)
    return SemanticEmbeddingIndexer(
        index_port=repository,
        embedding_provider=provider,
        provider_model=settings.semantic_embedding_model,
        embedding_index_key=settings.semantic_embedding_index_key,
        embedding_dimensions=settings.semantic_embedding_dimensions,
        timeout_ms=settings.semantic_query_timeout_ms,
    )


def _result_json(result: SemanticEmbeddingIndexingResult) -> str:
    return json.dumps(
        {
            "backfilled": result.backfilled,
            "claimed": result.claimed,
            "indexed": result.indexed,
            "failed": result.failed,
        },
        sort_keys=True,
    )


def _parse_args() -> argparse.Namespace:
    from app.core.semantic_defaults import (
        DEFAULT_SEMANTIC_INDEX_BATCH_SIZE,
        DEFAULT_SEMANTIC_INDEX_MAX_BATCHES,
        DEFAULT_SEMANTIC_RECLAIM_AFTER_SECONDS,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_SEMANTIC_INDEX_BATCH_SIZE)
    parser.add_argument("--max-batches", type=int, default=DEFAULT_SEMANTIC_INDEX_MAX_BATCHES)
    parser.add_argument(
        "--reclaim-after-seconds",
        type=int,
        default=DEFAULT_SEMANTIC_RECLAIM_AFTER_SECONDS,
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
