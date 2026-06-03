"""Unit tests for service container runtime wiring."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.settings import Settings
from app.service_container import _build_embedding_provider

DATABASE_URL = "postgresql+psycopg://u:p@127.0.0.1:5432/db"


@pytest.mark.unit
def test_semantic_provider_missing_key_warns_and_uses_lexical_only_fallback() -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL=DATABASE_URL,
        SEMANTIC_DISCOVERY_MODE="hybrid",
    )

    with patch("app.service_container.logger.warning") as warning:
        provider = _build_embedding_provider(settings=settings)

    assert provider is None
    warning.assert_called_once_with(
        "semantic discovery configured without an embedding provider; using lexical-only fallback",
        extra={
            "event_type": "semantic.discovery.provider_unavailable",
            "semantic_mode": "hybrid",
            "semantic_provider": "openai",
        },
    )
