"""Run one or more semantic embedding indexing batches."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if TYPE_CHECKING:
    from app.core.settings import Settings
    from app.core.skills.embedding_indexing import SemanticEmbeddingIndexer


def main() -> None:
    from app.core.settings import get_settings, reset_settings_cache
    from app.core.skills.embedding_indexing import SemanticEmbeddingIndexingResult
    from app.persistence.db import dispose_engine

    args = _parse_args()
    reset_settings_cache()
    settings = get_settings()
    indexer = build_indexer(settings=settings)

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

    print(
        json.dumps(
            {
                "backfilled": total.backfilled,
                "claimed": total.claimed,
                "indexed": total.indexed,
                "failed": total.failed,
            },
            sort_keys=True,
        )
    )
    dispose_engine()


def build_indexer(*, settings: Settings) -> SemanticEmbeddingIndexer:
    """Build the shared semantic indexing service for CLI/workflow entrypoints."""
    from app.core.skills.embedding_indexing import SemanticEmbeddingIndexer
    from app.integrations.openai_embeddings import OpenAIEmbeddingProvider
    from app.persistence.db import get_session_factory, init_engine
    from app.persistence.skill_registry_repository import SQLAlchemySkillCatalogRepository

    if settings.openai_api_key is None:
        raise RuntimeError("OPENAI_API_KEY is required to index semantic embeddings.")
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--max-batches", type=int, default=1)
    parser.add_argument("--reclaim-after-seconds", type=int, default=3600)
    return parser.parse_args()


if __name__ == "__main__":
    main()
