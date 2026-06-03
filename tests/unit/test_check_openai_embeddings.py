"""Unit tests for the deploy-time OpenAI embeddings check."""

from __future__ import annotations

from typing import Any

import pytest

from app.core.settings import Settings
from scripts.check_openai_embeddings import run_check

DATABASE_URL = "postgresql+psycopg://u:p@127.0.0.1:5432/db"


class _FakeProvider:
    def __init__(self, *, api_key: str, embedding: tuple[float, ...] = (0.1, 0.2, 0.3)) -> None:
        self.api_key = api_key
        self.embedding = embedding
        self.calls: list[dict[str, Any]] = []

    def embed_query(self, **kwargs: Any) -> tuple[float, ...]:
        self.calls.append(kwargs)
        return self.embedding


@pytest.mark.unit
def test_openai_embeddings_deploy_check_exercises_configured_model() -> None:
    provider = _FakeProvider(api_key="test-openai-key")
    settings = Settings(
        _env_file=None,
        DATABASE_URL=DATABASE_URL,
        OPENAI_API_KEY="test-openai-key",
        SEMANTIC_EMBEDDING_DIMENSIONS=3,
        SEMANTIC_QUERY_TIMEOUT_MS=250,
    )

    result = run_check(settings=settings, provider_factory=lambda *, api_key: provider)

    assert result.exit_code == 0
    assert "OpenAI embedding check passed" in result.message
    assert "test-openai-key" not in result.message
    assert provider.calls == [
        {
            "text": "aptitude registry semantic deployment check",
            "model": "text-embedding-3-small",
            "dimensions": 3,
            "timeout_ms": 5_000,
        }
    ]


@pytest.mark.unit
def test_openai_embeddings_deploy_check_warns_when_key_is_absent() -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL=DATABASE_URL,
        SEMANTIC_DISCOVERY_MODE="off",
    )

    result = run_check(
        settings=settings,
        provider_factory=lambda *, api_key: _FakeProvider(api_key=api_key),
    )

    assert result.exit_code == 0
    assert result.message == ("OpenAI embedding check warning: OPENAI_API_KEY is not configured.")


@pytest.mark.unit
def test_openai_embeddings_deploy_check_warns_for_provider_errors() -> None:
    class _FailingProvider(_FakeProvider):
        def embed_query(self, **kwargs: Any) -> tuple[float, ...]:
            raise RuntimeError("401 invalid api key")

    settings = Settings(
        _env_file=None,
        DATABASE_URL=DATABASE_URL,
        OPENAI_API_KEY="test-openai-key",
    )

    result = run_check(
        settings=settings,
        provider_factory=lambda *, api_key: _FailingProvider(api_key=api_key),
    )

    assert result.exit_code == 0
    assert "OpenAI embedding check warning" in result.message
    assert "RuntimeError: 401 invalid api key" in result.message
    assert "test-openai-key" not in result.message


@pytest.mark.unit
def test_openai_embeddings_deploy_check_retries_transient_provider_errors() -> None:
    class _FlakyProvider(_FakeProvider):
        def embed_query(self, **kwargs: Any) -> tuple[float, ...]:
            self.calls.append(kwargs)
            if len(self.calls) < 3:
                raise TimeoutError("provider timed out")
            return self.embedding

    provider = _FlakyProvider(api_key="test-openai-key")
    settings = Settings(
        _env_file=None,
        DATABASE_URL=DATABASE_URL,
        OPENAI_API_KEY="test-openai-key",
        SEMANTIC_EMBEDDING_DIMENSIONS=3,
    )

    result = run_check(settings=settings, provider_factory=lambda *, api_key: provider)

    assert result.exit_code == 0
    assert "OpenAI embedding check passed" in result.message
    assert len(provider.calls) == 3
