"""Trigger the Render Workflow semantic embedding indexing task."""

from __future__ import annotations

import argparse
import json
import os

from render_sdk import Render

from app.core.semantic_defaults import (
    DEFAULT_SEMANTIC_INDEX_BATCH_SIZE,
    DEFAULT_SEMANTIC_INDEX_MAX_BATCHES,
    DEFAULT_SEMANTIC_RECLAIM_AFTER_SECONDS,
)

DEFAULT_TASK_SLUG = "aptitude-registry-semantic-indexing/index_semantic_embeddings"


def main() -> None:
    args = _parse_args()
    task_slug = args.task_slug or os.getenv(
        "RENDER_SEMANTIC_INDEX_WORKFLOW_TASK",
        DEFAULT_TASK_SLUG,
    )
    payload = {
        "batch_size": args.batch_size,
        "max_batches": args.max_batches,
        "reclaim_after_seconds": args.reclaim_after_seconds,
    }
    result = Render().workflows.run_task(task_slug, payload)
    print(
        json.dumps(
            {
                "task_slug": task_slug,
                "run_id": getattr(result, "id", None),
                "status": getattr(result, "status", None),
            },
            sort_keys=True,
        )
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-slug")
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
