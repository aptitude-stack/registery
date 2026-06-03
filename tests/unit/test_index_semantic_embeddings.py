"""Unit tests for the semantic embedding indexing entrypoint."""

from __future__ import annotations

import logging

import pytest

from app.core.settings import Settings
from scripts.index_semantic_embeddings import build_indexer

DATABASE_URL = "postgresql+psycopg://u:p@127.0.0.1:5432/db"


@pytest.mark.unit
def test_build_indexer_warns_and_skips_without_openai_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL=DATABASE_URL,
        SEMANTIC_DISCOVERY_MODE="hybrid",
    )

    with caplog.at_level(logging.WARNING):
        indexer = build_indexer(settings=settings)

    assert indexer is None
    assert "skipping semantic indexing" in caplog.text
