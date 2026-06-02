"""Unit tests for the discovery benchmark helper logic."""

from __future__ import annotations

import pytest

from scripts.benchmark_discovery_search import (
    BENCHMARK_PREFIX_BASE,
    build_benchmark_dataset,
    latency_summary,
    percentile,
    recall_at_k,
)


@pytest.mark.unit
def test_percentile_uses_nearest_rank() -> None:
    assert percentile([1.0, 2.0, 3.0, 4.0], 50) == 2.0
    assert percentile([1.0, 2.0, 3.0, 4.0], 95) == 4.0
    assert percentile([], 95) == 0.0


@pytest.mark.unit
def test_recall_at_k_compares_expected_top_k() -> None:
    assert recall_at_k(expected=("a", "b", "c"), actual=("b", "x", "a"), limit=2) == 0.5
    assert recall_at_k(expected=(), actual=("a",), limit=10) == 1.0


@pytest.mark.unit
def test_latency_summary_reports_named_percentiles() -> None:
    assert latency_summary([1.1234, 2.2345, 3.3456]) == {
        "p50_ms": 2.235,
        "p95_ms": 3.346,
        "p99_ms": 3.346,
    }


@pytest.mark.unit
def test_benchmark_dataset_is_deterministic_and_clustered() -> None:
    prefix = f"{BENCHMARK_PREFIX_BASE}.unit."
    first_skills, first_queries = build_benchmark_dataset(
        skill_count=6,
        query_count=3,
        dimensions=1536,
        seed=42,
        slug_prefix=prefix,
    )
    second_skills, second_queries = build_benchmark_dataset(
        skill_count=6,
        query_count=3,
        dimensions=1536,
        seed=42,
        slug_prefix=prefix,
    )

    assert first_skills == second_skills
    assert first_queries == second_queries
    assert [skill.cluster for skill in first_skills] == [0, 1, 2, 0, 1, 2]
    assert first_skills[0].slug == f"{prefix}skill-000000"
    assert first_skills[0].tags == ("benchmark", "semantic", "family-0")
    assert first_queries[0].text == "meaning oriented request family 0"
    assert first_queries[0].vector[0] == 1.0


@pytest.mark.unit
def test_benchmark_dataset_rejects_unsupported_dimensions() -> None:
    with pytest.raises(ValueError, match="supports only 1536 dimensions"):
        build_benchmark_dataset(
            skill_count=1,
            query_count=1,
            dimensions=3,
            seed=42,
            slug_prefix=f"{BENCHMARK_PREFIX_BASE}.bad.",
        )
