"""Benchmark lexical, hybrid, and semantic discovery search."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.governance import (  # noqa: E402
    ALL_TRUST_TIERS,
    CallerIdentity,
    GovernancePolicy,
    build_default_policy_profile,
)
from app.core.semantic_defaults import (  # noqa: E402
    DEFAULT_SEMANTIC_CANDIDATE_LIMIT,
    DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS,
    DEFAULT_SEMANTIC_HNSW_EF_SEARCH,
    DEFAULT_SEMANTIC_QUERY_TIMEOUT_MS,
)
from app.core.skills.search import SkillSearchQuery, SkillSearchService  # noqa: E402
from app.intelligence.discovery_signals import (  # noqa: E402
    build_source_checksum_digest,
    serialize_embedding_vector,
    validate_embedding_vector,
)
from app.persistence.db import (  # noqa: E402
    dispose_engine,
    get_engine,
    get_session_factory,
    init_engine,
)
from app.persistence.skill_registry_repository import SQLAlchemySkillCatalogRepository  # noqa: E402

BENCHMARK_PREFIX_BASE = "benchmark-semantic"
DEFAULT_SKILL_COUNT = 1000
DEFAULT_QUERY_COUNT = 20
DEFAULT_LIMIT = 10
DEFAULT_SEED = 1337
DEFAULT_ITERATIONS = 5
DEFAULT_EF_SEARCH_VALUES = (40, 100, 200, 400)
BENCHMARK_TAG = "benchmark"


@dataclass(frozen=True, slots=True)
class BenchmarkSkill:
    slug: str
    name: str
    description: str
    tags: tuple[str, ...]
    cluster: int
    vector: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkQuery:
    text: str
    cluster: int
    vector: tuple[float, ...]


class _NoOpAuditRecorder:
    def record_event(self, *, event_type: str, payload: dict[str, Any] | None = None) -> None:
        del event_type, payload


class _DeterministicQueryEmbeddingProvider:
    def __init__(self, queries: Sequence[BenchmarkQuery]) -> None:
        self._vectors = {query.text: query.vector for query in queries}

    def embed_query(
        self,
        *,
        text: str,
        model: str,
        dimensions: int,
        timeout_ms: int,
    ) -> tuple[float, ...]:
        del model, timeout_ms
        vector = self._vectors[text]
        return validate_embedding_vector(vector, dimensions=dimensions)


def percentile(values: Sequence[float], percentile_value: float) -> float:
    """Return nearest-rank percentile for already observed measurements."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = math.ceil((percentile_value / 100.0) * len(ordered))
    return ordered[max(0, min(rank - 1, len(ordered) - 1))]


def recall_at_k(*, expected: Sequence[str], actual: Sequence[str], limit: int) -> float:
    """Return recall against an expected top-k set."""
    expected_top = tuple(expected[:limit])
    if not expected_top:
        return 1.0
    return len(set(expected_top).intersection(actual[:limit])) / len(expected_top)


def ranking_quality_at_k(
    *,
    relevant: Sequence[str],
    actual: Sequence[str],
    limit: int,
) -> dict[str, float]:
    """Return binary relevance quality metrics for a ranked top-k result."""
    relevant_set = set(relevant)
    actual_top = tuple(actual[:limit])
    if not relevant_set:
        return {
            "hit_rate_at_k": 1.0,
            "mrr_at_k": 1.0,
            "ndcg_at_k": 1.0,
            "relevant_recall_at_k": 1.0,
        }

    relevant_hits = [rank for rank, slug in enumerate(actual_top, start=1) if slug in relevant_set]
    hit_rate = 1.0 if relevant_hits else 0.0
    mrr = 1.0 / relevant_hits[0] if relevant_hits else 0.0
    recall = len(relevant_hits) / min(len(relevant_set), limit)
    dcg = sum(1.0 / math.log2(rank + 1) for rank in relevant_hits)
    ideal_hit_count = min(len(relevant_set), limit)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hit_count + 1))
    ndcg = dcg / idcg if idcg else 0.0

    return {
        "hit_rate_at_k": round(hit_rate, 4),
        "mrr_at_k": round(mrr, 4),
        "ndcg_at_k": round(ndcg, 4),
        "relevant_recall_at_k": round(recall, 4),
    }


def average_quality(quality_values: Sequence[dict[str, float]]) -> dict[str, float]:
    if not quality_values:
        return {
            "hit_rate_at_k": 0.0,
            "mrr_at_k": 0.0,
            "ndcg_at_k": 0.0,
            "relevant_recall_at_k": 0.0,
        }
    keys = tuple(quality_values[0])
    return {
        key: round(sum(value[key] for value in quality_values) / len(quality_values), 4)
        for key in keys
    }


def latency_summary(duration_ms: Sequence[float]) -> dict[str, float]:
    return {
        "p50_ms": round(percentile(duration_ms, 50), 3),
        "p95_ms": round(percentile(duration_ms, 95), 3),
        "p99_ms": round(percentile(duration_ms, 99), 3),
    }


def build_benchmark_dataset(
    *,
    skill_count: int,
    query_count: int,
    dimensions: int,
    seed: int,
    slug_prefix: str,
) -> tuple[tuple[BenchmarkSkill, ...], tuple[BenchmarkQuery, ...]]:
    """Build deterministic clustered skill/query vectors."""
    if skill_count < 1:
        raise ValueError("--skills must be at least 1.")
    if query_count < 1:
        raise ValueError("--queries must be at least 1.")
    if dimensions != DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS:
        raise ValueError(
            "The current skill_search_embeddings schema supports only "
            f"{DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS} dimensions."
        )
    if query_count >= dimensions:
        raise ValueError("--queries must be lower than --dimensions.")
    _validate_benchmark_prefix(slug_prefix)

    skills: list[BenchmarkSkill] = []
    for index in range(skill_count):
        cluster = index % query_count
        skills.append(
            BenchmarkSkill(
                slug=f"{slug_prefix}skill-{index:06d}",
                name=f"Benchmark Semantic Skill {index:06d}",
                description=f"Synthetic capability family {cluster} for semantic recall testing.",
                tags=(BENCHMARK_TAG, "semantic", f"family-{cluster}"),
                cluster=cluster,
                vector=_skill_vector(
                    cluster=cluster,
                    index=index,
                    dimensions=dimensions,
                    query_count=query_count,
                    seed=seed,
                ),
            )
        )

    queries = tuple(
        BenchmarkQuery(
            text=f"meaning oriented request family {cluster}",
            cluster=cluster,
            vector=_query_vector(cluster=cluster, dimensions=dimensions),
        )
        for cluster in range(query_count)
    )
    return tuple(skills), queries


def run_benchmark(
    *,
    repository: SQLAlchemySkillCatalogRepository,
    connection: Connection,
    skills: Sequence[BenchmarkSkill],
    queries: Sequence[BenchmarkQuery],
    slug_prefix: str,
    embedding_model: str,
    embedding_dimensions: int,
    provider_model: str,
    limit: int,
    iterations: int,
    ef_search_values: Sequence[int],
) -> dict[str, Any]:
    exact_results = {
        query.text: _semantic_slugs(
            connection=connection,
            query=query,
            slug_prefix=slug_prefix,
            embedding_model=embedding_model,
            embedding_dimensions=embedding_dimensions,
            limit=limit,
            exact=True,
            hnsw_ef_search=None,
        )
        for query in queries
    }

    semantic_sections = []
    for ef_search in ef_search_values:
        durations: list[float] = []
        recalls: list[float] = []
        quality_values: list[dict[str, float]] = []
        failures = 0
        for _ in range(iterations):
            for query in queries:
                started = time.perf_counter_ns()
                try:
                    actual = _semantic_slugs(
                        connection=connection,
                        query=query,
                        slug_prefix=slug_prefix,
                        embedding_model=embedding_model,
                        embedding_dimensions=embedding_dimensions,
                        limit=limit,
                        exact=False,
                        hnsw_ef_search=ef_search,
                    )
                    recalls.append(
                        recall_at_k(expected=exact_results[query.text], actual=actual, limit=limit)
                    )
                    quality_values.append(
                        _cluster_quality(
                            expected_cluster=query.cluster,
                            actual=actual,
                            skills=skills,
                            limit=limit,
                        )
                    )
                except Exception:
                    failures += 1
                    raise
                finally:
                    durations.append(_elapsed_ms(started))
        semantic_sections.append(
            {
                "ef_search": ef_search,
                "recall_at_k": round(sum(recalls) / len(recalls), 4) if recalls else 0.0,
                "quality": average_quality(quality_values),
                "latency": latency_summary(durations),
                "failure_count": failures,
            }
        )

    discovery_sections = []
    for mode in ("off", "shadow", "hybrid"):
        ef_values = (DEFAULT_SEMANTIC_HNSW_EF_SEARCH,) if mode == "off" else ef_search_values
        for ef_search in ef_values:
            durations = []
            cluster_recalls = []
            quality_values = []
            failures = 0
            service = _build_search_service(
                repository=repository,
                queries=queries,
                mode=mode,
                provider_model=provider_model,
                embedding_model=embedding_model,
                embedding_dimensions=embedding_dimensions,
                limit=limit,
                ef_search=ef_search,
            )
            for _ in range(iterations):
                for query in queries:
                    started = time.perf_counter_ns()
                    try:
                        actual = tuple(
                            item.slug
                            for item in service.search(
                                caller=CallerIdentity(
                                    token_id="benchmark-reader",
                                    scopes=frozenset({"read"}),
                                ),
                                query=SkillSearchQuery(
                                    q=query.text,
                                    tags=(BENCHMARK_TAG,),
                                    language=None,
                                    fresh_within_days=None,
                                    max_footprint_bytes=None,
                                    limit=limit,
                                ),
                            )
                        )
                        cluster_recalls.append(
                            _cluster_recall(
                                expected_cluster=query.cluster,
                                actual=actual,
                                skills=skills,
                                limit=limit,
                            )
                        )
                        quality_values.append(
                            _cluster_quality(
                                expected_cluster=query.cluster,
                                actual=actual,
                                skills=skills,
                                limit=limit,
                            )
                        )
                    except Exception:
                        failures += 1
                        raise
                    finally:
                        durations.append(_elapsed_ms(started))
            discovery_sections.append(
                {
                    "mode": mode,
                    "ef_search": None if mode == "off" else ef_search,
                    "cluster_recall_at_k": round(sum(cluster_recalls) / len(cluster_recalls), 4)
                    if cluster_recalls
                    else 0.0,
                    "quality": average_quality(quality_values),
                    "latency": latency_summary(durations),
                    "failure_count": failures,
                }
            )

    return {
        "semantic_hnsw": semantic_sections,
        "discovery": discovery_sections,
    }


def prepare_benchmark_rows(
    *,
    connection: Connection,
    skills: Sequence[BenchmarkSkill],
    slug_prefix: str,
    embedding_model: str,
    embedding_dimensions: int,
) -> None:
    """Insert synthetic benchmark rows under the reserved slug prefix."""
    _validate_benchmark_prefix(slug_prefix)
    cleanup_benchmark_rows(connection=connection, slug_prefix=slug_prefix)
    namespace_id = connection.execute(
        text("SELECT id FROM namespaces WHERE slug = 'public'")
    ).scalar_one_or_none()
    if namespace_id is None:
        raise RuntimeError("Public namespace is missing. Run Alembic migrations first.")

    for skill in skills:
        content_id = connection.execute(
            text(
                """
                INSERT INTO skill_contents (
                    payload,
                    media_type,
                    storage_size_bytes,
                    checksum_digest
                )
                VALUES (
                    :payload,
                    'application/zstd',
                    :storage_size_bytes,
                    :checksum_digest
                )
                RETURNING id
                """
            ),
            {
                "payload": f"# {skill.name}\n".encode(),
                "storage_size_bytes": len(f"# {skill.name}\n".encode()),
                "checksum_digest": _digest(f"content:{skill.slug}"),
            },
        ).scalar_one()
        skill_id = connection.execute(
            text(
                """
                INSERT INTO skills (slug, namespace_fk)
                VALUES (:slug, :namespace_fk)
                RETURNING id
                """
            ),
            {"slug": skill.slug, "namespace_fk": namespace_id},
        ).scalar_one()
        version_id = connection.execute(
            text(
                """
                INSERT INTO skill_versions (
                    skill_fk,
                    version,
                    content_fk,
                    name, description, tags, token_estimate, maturity_score, security_score,
                    checksum_digest,
                    lifecycle_status,
                    trust_tier,
                    artifact_origin,
                    review_state,
                    promotion_channel,
                    provenance_publisher_identity,
                    policy_profile_at_publish
                )
                VALUES (
                    :skill_fk,
                    '1.0.0',
                    :content_fk,
                    :name, :description, :tags, 128, 0.9, 0.95,
                    :checksum_digest,
                    'published',
                    'internal',
                    'internal',
                    'approved',
                    'prod',
                    'benchmark/discovery-search',
                    'default'
                )
                RETURNING id
                """
            ),
            {
                "skill_fk": skill_id,
                "content_fk": content_id,
                "name": skill.name,
                "description": skill.description,
                "tags": list(skill.tags),
                "checksum_digest": _digest(f"version:{skill.slug}"),
            },
        ).scalar_one()
        connection.execute(
            text(
                """
                INSERT INTO skill_search_documents (
                    skill_version_fk,
                    slug,
                    normalized_slug,
                    version,
                    name,
                    normalized_name,
                    description,
                    tags,
                    normalized_tags,
                    lifecycle_status,
                    trust_tier,
                    namespace,
                    artifact_origin,
                    review_state,
                    promotion_channel,
                    search_vector,
                    published_at,
                    content_size_bytes
                )
                VALUES (
                    :skill_version_fk,
                    :slug,
                    :normalized_slug,
                    '1.0.0',
                    :name,
                    :normalized_name,
                    :description,
                    :tags,
                    :normalized_tags,
                    'published',
                    'internal',
                    'public',
                    'internal',
                    'approved',
                    'prod',
                    to_tsvector('simple'::regconfig, :search_source),
                    CURRENT_TIMESTAMP,
                    :content_size_bytes
                )
                """
            ),
            {
                "skill_version_fk": version_id,
                "slug": skill.slug,
                "normalized_slug": skill.slug,
                "name": skill.name,
                "normalized_name": skill.name.lower(),
                "description": skill.description,
                "tags": list(skill.tags),
                "normalized_tags": list(skill.tags),
                "search_source": " ".join((skill.slug, skill.name, skill.description, *skill.tags)),
                "content_size_bytes": len(f"# {skill.name}\n".encode()),
            },
        )
        source_text = f"{skill.description} {' '.join(skill.tags)}"
        connection.execute(
            text(
                f"""
                INSERT INTO skill_search_embeddings (
                    skill_version_fk,
                    embedding_model,
                    source_checksum_digest,
                    embedding_vector,
                    index_status,
                    indexed_at
                )
                VALUES (
                    :skill_version_fk,
                    :embedding_model,
                    :source_checksum_digest,
                    CAST(:embedding_vector AS halfvec({embedding_dimensions})),
                    'indexed',
                    CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "skill_version_fk": version_id,
                "embedding_model": embedding_model,
                "source_checksum_digest": build_source_checksum_digest(source_text),
                "embedding_vector": serialize_embedding_vector(skill.vector),
            },
        )
    connection.execute(text("ANALYZE skill_search_documents"))
    connection.execute(text("ANALYZE skill_search_embeddings"))


def cleanup_benchmark_rows(*, connection: Connection, slug_prefix: str) -> int:
    """Delete benchmark-prefixed rows and only benchmark-prefixed rows."""
    _validate_benchmark_prefix(slug_prefix)
    pattern = f"{slug_prefix}%"
    rows = (
        connection.execute(
            text(
                """
                SELECT skill_versions.content_fk
                FROM skill_versions
                JOIN skills ON skills.id = skill_versions.skill_fk
                WHERE skills.slug LIKE :pattern
                """
            ),
            {"pattern": pattern},
        )
        .mappings()
        .all()
    )
    content_ids = [int(row["content_fk"]) for row in rows]
    deleted = int(
        connection.execute(
            text("DELETE FROM skills WHERE slug LIKE :pattern"),
            {"pattern": pattern},
        ).rowcount
        or 0
    )
    if content_ids:
        connection.execute(
            text(
                "DELETE FROM skill_contents WHERE id = ANY(:content_ids) "
                "AND NOT EXISTS (SELECT 1 FROM skill_versions WHERE content_fk = skill_contents.id)"
            ),
            {"content_ids": content_ids},
        )
    return deleted


def format_summary(result: dict[str, Any]) -> str:
    lines = [
        "Discovery benchmark summary",
        "",
        "Semantic HNSW exact-baseline comparison:",
        "ef_search  recall@k  rel_rec@k  hit@k   mrr@k   ndcg@k  p50_ms  p95_ms  p99_ms  fail",
    ]
    for row in result["semantic_hnsw"]:
        latency = row["latency"]
        quality = row["quality"]
        lines.append(
            f"{row['ef_search']:>9}  {row['recall_at_k']:<8.4f}  "
            f"{quality['relevant_recall_at_k']:<12.4f}  "
            f"{quality['hit_rate_at_k']:<6.4f}  "
            f"{quality['mrr_at_k']:<6.4f}  "
            f"{quality['ndcg_at_k']:<6.4f}  "
            f"{latency['p50_ms']:<6.3f}  {latency['p95_ms']:<6.3f}  "
            f"{latency['p99_ms']:<6.3f}  {row['failure_count']}"
        )
    lines.extend(
        [
            "",
            "End-to-end discovery comparison:",
            "mode    ef_search  clus_rec@k  hit@k   mrr@k   ndcg@k  p50_ms  p95_ms  p99_ms  fail",
        ]
    )
    for row in result["discovery"]:
        latency = row["latency"]
        quality = row["quality"]
        ef_search = "-" if row["ef_search"] is None else str(row["ef_search"])
        lines.append(
            f"{row['mode']:<7} {ef_search:>8}  {row['cluster_recall_at_k']:<16.4f}  "
            f"{quality['hit_rate_at_k']:<6.4f}  "
            f"{quality['mrr_at_k']:<6.4f}  "
            f"{quality['ndcg_at_k']:<6.4f}  "
            f"{latency['p50_ms']:<6.3f}  {latency['p95_ms']:<6.3f}  "
            f"{latency['p99_ms']:<6.3f}  {row['failure_count']}"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    slug_prefix = args.prefix or f"{BENCHMARK_PREFIX_BASE}-{args.seed}-"
    _validate_benchmark_prefix(slug_prefix)
    ef_search_values = tuple(dict.fromkeys(args.ef_search))
    if any(value < args.limit for value in ef_search_values):
        raise SystemExit("--ef-search values must be greater than or equal to --limit.")

    os.environ.setdefault("SEMANTIC_DISCOVERY_MODE", "off")
    from app.core.settings import get_settings, reset_settings_cache

    reset_settings_cache()
    settings = get_settings()
    init_engine(
        settings.database_url,
        application_name=f"{settings.app_name}-{settings.app_env}-discovery-benchmark",
    )
    engine = get_engine()
    if engine is None:
        raise RuntimeError("Database engine was not initialized.")

    skills, queries = build_benchmark_dataset(
        skill_count=args.skills,
        query_count=args.queries,
        dimensions=args.dimensions,
        seed=args.seed,
        slug_prefix=slug_prefix,
    )
    repository = SQLAlchemySkillCatalogRepository(
        get_session_factory(),
        semantic_embedding_index_key=settings.semantic_embedding_index_key,
        semantic_embedding_dimensions=args.dimensions,
    )

    cleanup_count = 0
    with engine.begin() as connection:
        prepare_benchmark_rows(
            connection=connection,
            skills=skills,
            slug_prefix=slug_prefix,
            embedding_model=settings.semantic_embedding_index_key,
            embedding_dimensions=args.dimensions,
        )

    try:
        with engine.connect() as connection:
            benchmark = run_benchmark(
                repository=repository,
                connection=connection,
                skills=skills,
                queries=queries,
                slug_prefix=slug_prefix,
                embedding_model=settings.semantic_embedding_index_key,
                embedding_dimensions=args.dimensions,
                provider_model=settings.semantic_embedding_model,
                limit=args.limit,
                iterations=args.iterations,
                ef_search_values=ef_search_values,
            )
    finally:
        if not args.keep_data:
            with engine.begin() as connection:
                cleanup_count = cleanup_benchmark_rows(
                    connection=connection,
                    slug_prefix=slug_prefix,
                )
        dispose_engine()

    result = {
        "config": {
            "skills": args.skills,
            "queries": args.queries,
            "dimensions": args.dimensions,
            "limit": args.limit,
            "iterations": args.iterations,
            "seed": args.seed,
            "slug_prefix": slug_prefix,
            "ef_search_values": list(ef_search_values),
            "embedding_model": settings.semantic_embedding_index_key,
            "provider_model": settings.semantic_embedding_model,
        },
        "dataset": {
            "skill_count": len(skills),
            "query_count": len(queries),
            "benchmark_tag": BENCHMARK_TAG,
        },
        **benchmark,
        "cleanup": {
            "enabled": not args.keep_data,
            "deleted_skill_count": cleanup_count,
        },
    }
    print(format_summary(result))
    print(json.dumps(result, sort_keys=True))
    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills", type=int, default=DEFAULT_SKILL_COUNT)
    parser.add_argument("--queries", type=int, default=DEFAULT_QUERY_COUNT)
    parser.add_argument("--dimensions", type=int, default=DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--prefix", default=None)
    parser.add_argument("--keep-data", action="store_true")
    parser.add_argument(
        "--ef-search",
        type=int,
        nargs="+",
        default=list(DEFAULT_EF_SEARCH_VALUES),
    )
    return parser.parse_args(argv)


def _build_search_service(
    *,
    repository: SQLAlchemySkillCatalogRepository,
    queries: Sequence[BenchmarkQuery],
    mode: str,
    provider_model: str,
    embedding_model: str,
    embedding_dimensions: int,
    limit: int,
    ef_search: int,
) -> SkillSearchService:
    return SkillSearchService(
        repository=repository,
        audit_recorder=_NoOpAuditRecorder(),
        governance_policy=GovernancePolicy(profile=build_default_policy_profile()),
        semantic_discovery_mode=mode,  # type: ignore[arg-type]
        embedding_provider=None if mode == "off" else _DeterministicQueryEmbeddingProvider(queries),
        semantic_embedding_model=provider_model,
        semantic_embedding_index_key=embedding_model,
        semantic_embedding_dimensions=embedding_dimensions,
        semantic_candidate_limit=min(DEFAULT_SEMANTIC_CANDIDATE_LIMIT, limit),
        semantic_query_timeout_ms=DEFAULT_SEMANTIC_QUERY_TIMEOUT_MS,
        semantic_hnsw_ef_search=ef_search,
    )


def _semantic_slugs(
    *,
    connection: Connection,
    query: BenchmarkQuery,
    slug_prefix: str,
    embedding_model: str,
    embedding_dimensions: int,
    limit: int,
    exact: bool,
    hnsw_ef_search: int | None,
) -> tuple[str, ...]:
    _validate_benchmark_prefix(slug_prefix)
    vector_type = f"halfvec({embedding_dimensions})"
    query_embedding = serialize_embedding_vector(query.vector)
    with connection.begin():
        if exact:
            connection.execute(text("SET LOCAL enable_indexscan = off"))
        else:
            if hnsw_ef_search is None:
                raise ValueError("hnsw_ef_search is required for approximate semantic search.")
            connection.execute(text(f"SET LOCAL hnsw.ef_search = {hnsw_ef_search}"))
        rows = connection.execute(
            text(
                f"""
                SELECT doc.slug
                FROM skill_search_embeddings AS emb
                JOIN skill_search_documents AS doc
                    ON doc.skill_version_fk = emb.skill_version_fk
                WHERE emb.embedding_model = :embedding_model
                  AND emb.index_status = 'indexed'
                  AND emb.embedding_vector IS NOT NULL
                  AND doc.slug LIKE :slug_pattern
                  AND doc.normalized_tags @> :required_tags
                  AND doc.lifecycle_status = 'published'
                  AND doc.trust_tier = ANY(:trust_tiers)
                  AND doc.namespace = 'public'
                  AND doc.promotion_channel = 'prod'
                  AND doc.review_state = 'approved'
                ORDER BY
                    emb.embedding_vector <=> CAST(:query_embedding AS {vector_type}),
                    doc.slug ASC,
                    doc.skill_version_fk DESC
                LIMIT :limit
                """
            ),
            {
                "embedding_model": embedding_model,
                "slug_pattern": f"{slug_prefix}%",
                "required_tags": [BENCHMARK_TAG],
                "trust_tiers": list(ALL_TRUST_TIERS),
                "query_embedding": query_embedding,
                "limit": limit,
            },
        ).scalars()
        return tuple(str(row) for row in rows)


def _cluster_recall(
    *,
    expected_cluster: int,
    actual: Sequence[str],
    skills: Sequence[BenchmarkSkill],
    limit: int,
) -> float:
    expected = tuple(skill.slug for skill in skills if skill.cluster == expected_cluster)
    return recall_at_k(expected=expected, actual=actual, limit=limit)


def _cluster_quality(
    *,
    expected_cluster: int,
    actual: Sequence[str],
    skills: Sequence[BenchmarkSkill],
    limit: int,
) -> dict[str, float]:
    relevant = tuple(skill.slug for skill in skills if skill.cluster == expected_cluster)
    return ranking_quality_at_k(relevant=relevant, actual=actual, limit=limit)


def _skill_vector(
    *,
    cluster: int,
    index: int,
    dimensions: int,
    query_count: int,
    seed: int,
) -> tuple[float, ...]:
    values = [0.0] * dimensions
    values[cluster] = 1.0
    noise_slot_count = dimensions - query_count
    noise_slot = query_count + ((index * 31 + seed) % noise_slot_count)
    values[noise_slot] = 0.001
    return _normalize(values)


def _query_vector(*, cluster: int, dimensions: int) -> tuple[float, ...]:
    values = [0.0] * dimensions
    values[cluster] = 1.0
    return tuple(values)


def _normalize(values: Iterable[float]) -> tuple[float, ...]:
    raw = tuple(values)
    norm = math.sqrt(sum(value * value for value in raw))
    if norm == 0:
        raise ValueError("Cannot normalize a zero vector.")
    return tuple(value / norm for value in raw)


def _elapsed_ms(started_ns: int) -> float:
    return (time.perf_counter_ns() - started_ns) / 1_000_000


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_benchmark_prefix(slug_prefix: str) -> None:
    if not slug_prefix.startswith(f"{BENCHMARK_PREFIX_BASE}-"):
        raise ValueError(f"Benchmark prefix must start with {BENCHMARK_PREFIX_BASE!r}-.")
    if not slug_prefix.endswith("-"):
        raise ValueError("Benchmark prefix must end with '-'.")


if __name__ == "__main__":
    raise SystemExit(main())
