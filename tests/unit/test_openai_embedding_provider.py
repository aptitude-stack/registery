"""Unit tests for the OpenAI embedding provider adapter."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.integrations.openai_embeddings import OpenAIEmbeddingProvider


class _FakeEmbeddingsClient:
    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(data=[SimpleNamespace(embedding=self.embedding)])


class _FakeOpenAIClient:
    def __init__(self, embedding: list[float]) -> None:
        self.embeddings = _FakeEmbeddingsClient(embedding)


@pytest.mark.unit
def test_openai_provider_sends_model_dimensions_input_and_timeout() -> None:
    client = _FakeOpenAIClient([0.1, 0.2, 0.3])
    provider = OpenAIEmbeddingProvider(api_key="test-key", client=client)

    vector = provider.embed_query(
        text="static checks python",
        model="text-embedding-3-small",
        dimensions=3,
        timeout_ms=250,
    )

    assert vector == (0.1, 0.2, 0.3)
    assert client.embeddings.calls == [
        {
            "input": "static checks python",
            "model": "text-embedding-3-small",
            "dimensions": 3,
            "encoding_format": "float",
            "timeout": 0.25,
        }
    ]


@pytest.mark.unit
def test_openai_provider_rejects_malformed_vectors() -> None:
    provider = OpenAIEmbeddingProvider(
        api_key="test-key",
        client=_FakeOpenAIClient([0.1, float("nan")]),
    )

    with pytest.raises(ValueError, match="finite"):
        provider.embed_query(
            text="static checks python",
            model="text-embedding-3-small",
            dimensions=2,
            timeout_ms=250,
        )
