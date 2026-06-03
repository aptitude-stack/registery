"""Verify deploy-time OpenAI embedding connectivity and configuration."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.settings import Settings, get_settings, reset_settings_cache  # noqa: E402
from app.integrations.openai_embeddings import OpenAIEmbeddingProvider  # noqa: E402

CHECK_TEXT = "aptitude registry semantic deployment check"
CHECK_ATTEMPTS = 3
CHECK_TIMEOUT_MS = 5_000


class EmbeddingProvider(Protocol):
    def embed_query(
        self,
        *,
        text: str,
        model: str,
        dimensions: int,
        timeout_ms: int,
    ) -> tuple[float, ...]:
        """Return one embedding vector for the supplied text."""


class EmbeddingProviderFactory(Protocol):
    def __call__(self, *, api_key: str) -> EmbeddingProvider:
        """Build an embedding provider from the configured API key."""


@dataclass(frozen=True)
class CheckResult:
    exit_code: int
    message: str


def run_check(
    *,
    settings: Settings,
    provider_factory: EmbeddingProviderFactory = OpenAIEmbeddingProvider,
) -> CheckResult:
    """Send one embedding request using the configured production settings."""
    if not settings.openai_api_key:
        return CheckResult(
            exit_code=0,
            message="OpenAI embedding check warning: OPENAI_API_KEY is not configured.",
        )

    timeout_ms = max(settings.semantic_query_timeout_ms, CHECK_TIMEOUT_MS)
    provider = provider_factory(api_key=settings.openai_api_key)
    last_error: Exception | None = None
    for _attempt in range(CHECK_ATTEMPTS):
        try:
            vector = provider.embed_query(
                text=CHECK_TEXT,
                model=settings.semantic_embedding_model,
                dimensions=settings.semantic_embedding_dimensions,
                timeout_ms=timeout_ms,
            )
            break
        except Exception as exc:  # noqa: BLE001 - deploy check should report provider failures clearly.
            last_error = exc
    else:
        assert last_error is not None
        return CheckResult(
            exit_code=0,
            message=(
                "OpenAI embedding check warning: provider check failed "
                f"for model={settings.semantic_embedding_model!r}, "
                f"dimensions={settings.semantic_embedding_dimensions}: "
                f"{type(last_error).__name__}: {last_error}"
            ),
        )

    return CheckResult(
        exit_code=0,
        message=(
            "OpenAI embedding check passed "
            f"for model={settings.semantic_embedding_model!r}, "
            f"dimensions={settings.semantic_embedding_dimensions}, "
            f"vector_dimensions={len(vector)}."
        ),
    )


def main() -> int:
    reset_settings_cache()
    result = run_check(settings=get_settings())
    print(result.message, file=sys.stderr if result.exit_code else sys.stdout)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
