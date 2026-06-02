"""Integration coverage for the discovery benchmark CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text


@pytest.mark.integration
def test_discovery_benchmark_cli_reports_recall_latency_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    prefix = "benchmark.semantic.integration."
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    monkeypatch.setenv("SEMANTIC_DISCOVERY_MODE", "off")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env = os.environ.copy()

    result = subprocess.run(
        [
            sys.executable,
            "scripts/benchmark_discovery_search.py",
            "--skills",
            "30",
            "--queries",
            "3",
            "--iterations",
            "1",
            "--limit",
            "5",
            "--ef-search",
            "40",
            "100",
            "--prefix",
            prefix,
        ],
        check=False,
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "semantic discovery degraded to lexical fallback" not in result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["config"]["skills"] == 30
    assert payload["config"]["queries"] == 3
    assert payload["semantic_hnsw"][0]["ef_search"] == 40
    assert payload["semantic_hnsw"][0]["recall_at_k"] >= 0.0
    assert payload["semantic_hnsw"][0]["quality"]["hit_rate_at_k"] >= 0.0
    assert payload["semantic_hnsw"][0]["quality"]["mrr_at_k"] >= 0.0
    assert payload["semantic_hnsw"][0]["quality"]["ndcg_at_k"] >= 0.0
    assert payload["semantic_hnsw"][0]["quality"]["relevant_recall_at_k"] >= 0.0
    assert payload["semantic_hnsw"][0]["latency"]["p95_ms"] >= 0.0
    assert {row["mode"] for row in payload["discovery"]} == {"off", "shadow", "hybrid"}
    assert any(
        row["mode"] == "hybrid" and row["cluster_recall_at_k"] > 0.0 for row in payload["discovery"]
    )
    assert all("quality" in row for row in payload["discovery"])
    assert any(row["quality"]["hit_rate_at_k"] > 0.0 for row in payload["discovery"])
    assert payload["cleanup"] == {"enabled": True, "deleted_skill_count": 30}

    engine = create_engine(migrated_registry_database)
    try:
        with engine.connect() as connection:
            remaining = connection.execute(
                text("SELECT COUNT(*) FROM skills WHERE slug LIKE :pattern"),
                {"pattern": f"{prefix}%"},
            ).scalar_one()
    finally:
        engine.dispose()

    assert remaining == 0
