"""OpenAI embedding provider adapter."""

from __future__ import annotations

from typing import Any

from app.intelligence.discovery_signals import validate_embedding_vector


class OpenAIEmbeddingProvider:
    """Embedding provider backed by the official OpenAI Python SDK."""

    def __init__(self, *, api_key: str, client: Any | None = None) -> None:
        self._client = client if client is not None else self._build_client(api_key=api_key)

    @staticmethod
    def _build_client(*, api_key: str) -> Any:
        from openai import OpenAI

        return OpenAI(api_key=api_key)

    def embed_query(
        self,
        *,
        text: str,
        model: str,
        dimensions: int,
        timeout_ms: int,
    ) -> tuple[float, ...]:
        """Return one validated query embedding."""
        response = self._client.embeddings.create(
            input=text,
            model=model,
            dimensions=dimensions,
            encoding_format="float",
            timeout=timeout_ms / 1000,
        )
        if not response.data:
            raise ValueError("OpenAI embedding response did not contain data.")
        values = tuple(float(value) for value in response.data[0].embedding)
        return validate_embedding_vector(values, dimensions=dimensions)
