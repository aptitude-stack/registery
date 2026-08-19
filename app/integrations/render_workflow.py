"""Render workflow adapter for semantic embedding indexing."""

from __future__ import annotations

import os
from typing import Any

from app.core.semantic_defaults import (
    DEFAULT_SEMANTIC_INDEX_BATCH_SIZE,
    DEFAULT_SEMANTIC_INDEX_MAX_BATCHES,
    DEFAULT_SEMANTIC_RECLAIM_AFTER_SECONDS,
)

DEFAULT_SEMANTIC_INDEX_WORKFLOW_TASK = (
    "aptitude-registry-semantic-indexing/index_semantic_embeddings"
)


def start_semantic_embedding_workflow(
    *,
    task_slug: str | None = None,
    batch_size: int = DEFAULT_SEMANTIC_INDEX_BATCH_SIZE,
    max_batches: int = DEFAULT_SEMANTIC_INDEX_MAX_BATCHES,
    reclaim_after_seconds: int = DEFAULT_SEMANTIC_RECLAIM_AFTER_SECONDS,
) -> Any:
    """Start one bounded Render workflow run for pending embedding rows."""
    from render_sdk import Render

    return Render().workflows.run_task(
        task_slug
        or os.getenv("RENDER_SEMANTIC_INDEX_WORKFLOW_TASK", DEFAULT_SEMANTIC_INDEX_WORKFLOW_TASK),
        {
            "batch_size": batch_size,
            "max_batches": max_batches,
            "reclaim_after_seconds": reclaim_after_seconds,
        },
    )
