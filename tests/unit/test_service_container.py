"""Unit tests for service container runtime wiring."""

from __future__ import annotations

import logging

import pytest

from app.core.settings import Settings
from app.service_container import _build_embedding_provider

DATABASE_URL = "postgresql+psycopg://u:p@127.0.0.1:5432/db"


@pytest.mark.unit
def test_semantic_provider_missing_key_warns_and_uses_lexical_only_fallback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL=DATABASE_URL,
        SEMANTIC_DISCOVERY_MODE="hybrid",
    )

    with caplog.at_level(logging.WARNING):
        provider = _build_embedding_provider(settings=settings)

    assert provider is None
    assert "using lexical-only fallback" in caplog.text
