"""Render Workflow tasks for semantic embedding indexing."""

from __future__ import annotations

import sys
from pathlib import Path

from render_sdk import Workflows

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.semantic_defaults import (
    DEFAULT_SEMANTIC_INDEX_BATCH_SIZE,
    DEFAULT_SEMANTIC_INDEX_MAX_BATCHES,
    DEFAULT_SEMANTIC_RECLAIM_AFTER_SECONDS,
)

app = Workflows(default_timeout=7200, default_plan="starter")


@app.task(name="index_semantic_embeddings", timeout_seconds=7200, plan="starter")
def index_semantic_embeddings(
    batch_size: int = DEFAULT_SEMANTIC_INDEX_BATCH_SIZE,
    max_batches: int = DEFAULT_SEMANTIC_INDEX_MAX_BATCHES,
    reclaim_after_seconds: int = DEFAULT_SEMANTIC_RECLAIM_AFTER_SECONDS,
) -> dict[str, int]:
    """Index pending/stale semantic embedding rows in bounded batches."""
    from app.core.settings import get_settings, reset_settings_cache
    from app.persistence.db import dispose_engine
    from scripts.index_semantic_embeddings import build_indexer

    reset_settings_cache()
    settings = get_settings()
    indexer = build_indexer(settings=settings)
    totals = {"backfilled": 0, "claimed": 0, "indexed": 0, "failed": 0}
    try:
        for _ in range(max_batches):
            result = indexer.run_batch(
                batch_size=batch_size,
                reclaim_after_seconds=reclaim_after_seconds,
            )
            totals["backfilled"] += result.backfilled
            totals["claimed"] += result.claimed
            totals["indexed"] += result.indexed
            totals["failed"] += result.failed
            if result.claimed == 0:
                break
        return totals
    finally:
        dispose_engine()


if __name__ == "__main__":
    app.start()
