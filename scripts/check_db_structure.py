"""Read-only preflight for the populated database-structure cleanup."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

Phase = Literal["before", "after"]
BEFORE_REVISION = "0012_remove_metadata_schemas"
AFTER_REVISION = "0013_db_structure_cleanup"
EXPECTED = {"before": BEFORE_REVISION, "after": AFTER_REVISION}
TABLES = (
    "organizations",
    "namespaces",
    "policy_packs",
    "skills",
    "skill_versions",
    "skill_contents",
    "skill_relationship_selectors",
    "skill_search_documents",
    "skill_search_embeddings",
    "skill_usage_observation_runs",
    "skill_usage_observations",
    "skill_co_usage_pairs",
    "skill_graph_edges",
    "trust_evidence",
    "skill_user_stars",
    "audit_events",
)
REMOVED = {
    "skills": {"star_count"},
    "skill_versions": {"metadata_fk"},
    "skill_search_documents": {"usage_count"},
    "skill_usage_observations": {"skill_slug"},
    "skill_co_usage_pairs": {"observation_count", "pmi_score"},
    "skill_search_embeddings": {"embedding_dimensions"},
}


def migration_database_url() -> str:
    """Read the explicit direct URL; application settings and dotenv are out of scope."""
    value = os.environ.get("MIGRATION_DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("MIGRATION_DATABASE_URL is required for database preflight.")
    try:
        url = make_url(value)
    except Exception as exc:  # pragma: no cover - SQLAlchemy owns URL parsing.
        raise ValueError("MIGRATION_DATABASE_URL is not a valid database URL.") from exc
    if "-pooler" in (url.host or ""):
        raise ValueError("Database preflight requires a direct host, not a Neon pooler host.")
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return url.render_as_string(hide_password=False)


def fingerprint_rows(rows_by_table: Mapping[str, Iterable[Mapping[str, Any]]]) -> dict[str, Any]:
    """Hash complete rows while returning only row counts and digests."""
    tables: dict[str, dict[str, int | str]] = {}
    for name in sorted(rows_by_table):
        rows = sorted(_json(dict(row)).encode() for row in rows_by_table[name])
        tables[name] = {
            "rows": len(rows),
            "digest": hashlib.sha256(b"\n".join(rows)).hexdigest(),
        }
    return {
        "algorithm": "sha256",
        "digest": hashlib.sha256(_json(tables).encode()).hexdigest(),
        "tables": tables,
    }


def compare_reports(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """Compare canonical data and blocking findings from two reports."""
    issues = [
        dict(item) for item in after.get("blocking_violations", []) if isinstance(item, Mapping)
    ]
    if before.get("blocking_violations"):
        issues.append({"code": "before_preflight_blocked"})
    if before.get("canonical_fingerprint") != after.get("canonical_fingerprint"):
        issues.append({"code": "canonical_fingerprint_changed"})
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for issue in issues:
        key = _json(issue)
        if key not in seen:
            seen.add(key)
            unique.append(issue)
    return {
        "ok": not unique,
        "blocking_violations": unique,
        "advisories": [
            dict(item) for item in after.get("advisories", []) if isinstance(item, Mapping)
        ],
    }


def inspect_structure(connection: Connection, phase: Phase) -> dict[str, Any]:
    """Inspect one phase through SELECTs only; the caller owns the read-only transaction."""
    if phase not in EXPECTED:
        raise ValueError(f"Unknown preflight phase: {phase!r}")
    report: dict[str, Any] = {
        "phase": phase,
        "expected_revision": EXPECTED[phase],
        "actual_revision": _revision(connection),
        "blocking_violations": [],
        "advisories": [],
        "metadata_coverage": {},
        "domain_validity": {},
        "redundant_value_differences": {},
        "required_constraints": {},
    }
    if report["actual_revision"] != EXPECTED[phase]:
        _issue(report["blocking_violations"], "revision_mismatch")

    required = set(TABLES) | ({"skill_metadata"} if phase == "before" else set())
    for table in sorted(required):
        if not _exists(connection, table):
            _issue(report["blocking_violations"], "missing_table", table=table)

    if phase == "after":
        for table, columns in REMOVED.items():
            if _cols(connection, table) & columns:
                _issue(report["blocking_violations"], "retired_column_present", table=table)
        if _exists(connection, "skill_metadata"):
            _issue(report["blocking_violations"], "retired_table_present", table="skill_metadata")
        missing = {
            "name",
            "description",
            "tags",
            "token_estimate",
            "maturity_score",
            "security_score",
            "overall_score",
        } - _cols(connection, "skill_versions")
        if missing:
            _issue(
                report["blocking_violations"],
                "missing_version_metadata_column",
                table="skill_versions",
            )
        for column in ("name", "tags"):
            if not _not_null(connection, "skill_versions", column):
                _issue(
                    report["blocking_violations"],
                    "nullable_version_metadata_column",
                    table="skill_versions",
                )

    _metadata_coverage(connection, report, phase)
    _domain_validity(connection, report, phase)
    _historical_stars(connection, report, phase)
    _redundant_value_differences(connection, report, phase)
    if phase == "after":
        report["required_constraints"] = _required_constraints(connection)
        for name, present in report["required_constraints"].items():
            if not present:
                _issue(
                    report["blocking_violations"], "missing_required_constraint", constraint=name
                )
    report["canonical_fingerprint"] = _fingerprint(connection, phase)
    report["ok"] = not report["blocking_violations"]
    return report


def _metadata_coverage(connection: Connection, report: dict[str, Any], phase: Phase) -> None:
    if phase == "before":
        orphan = _count(
            connection,
            """
            SELECT COUNT(*) FROM skill_metadata AS m
            LEFT JOIN skill_versions AS v ON v.metadata_fk = m.id WHERE v.id IS NULL
        """,
        )
        shared = _count(
            connection,
            """
            SELECT COUNT(*) FROM (SELECT metadata_fk FROM skill_versions
            GROUP BY metadata_fk HAVING COUNT(*) > 1) AS shared
        """,
        )
        missing = _count(
            connection, "SELECT COUNT(*) FROM skill_versions WHERE metadata_fk IS NULL"
        )
        report["metadata_coverage"] = {
            "metadata_rows": _count(connection, "SELECT COUNT(*) FROM skill_metadata"),
            "referenced_metadata_rows": _count(
                connection, "SELECT COUNT(DISTINCT metadata_fk) FROM skill_versions"
            ),
            "orphan_metadata_rows": orphan,
            "shared_metadata_rows": shared,
            "versions_without_metadata": missing,
        }
        if orphan:
            _issue(report["blocking_violations"], "orphan_metadata", count=orphan)
        if missing:
            _issue(report["blocking_violations"], "version_without_metadata", count=missing)
    else:
        missing = _count(connection, "SELECT COUNT(*) FROM skill_versions WHERE name IS NULL")
        report["metadata_coverage"] = {
            "metadata_rows": 0,
            "referenced_metadata_rows": 0,
            "orphan_metadata_rows": 0,
            "shared_metadata_rows": 0,
            "versions_without_metadata": missing,
        }
        if missing:
            _issue(report["blocking_violations"], "version_without_metadata", count=missing)


def _domain_validity(connection: Connection, report: dict[str, Any], phase: Phase) -> None:
    table = "skill_metadata" if phase == "before" else "skill_versions"
    metadata_join = (
        "JOIN skill_metadata AS metadata ON metadata.id = version_row.metadata_fk"
        if phase == "before"
        else ""
    )
    metadata = "metadata" if phase == "before" else "version_row"
    checks = {
        "invalid_metadata_scores": f"""
            SELECT COUNT(*) FROM {table}
            WHERE (maturity_score IS NOT NULL AND (maturity_score < 0 OR maturity_score > 1))
               OR (security_score IS NOT NULL AND (security_score < 0 OR security_score > 1))
               OR (overall_score IS NOT NULL AND (overall_score < 0 OR overall_score > 1))
        """,
        "invalid_token_estimate": f"""
            SELECT COUNT(*) FROM {table}
            WHERE token_estimate IS NOT NULL AND token_estimate < 0
        """,
        "invalid_content_size": """
            SELECT COUNT(*) FROM skill_contents
            WHERE storage_size_bytes < 0 OR storage_size_bytes <> octet_length(payload)
        """,
        "negative_install_count": "SELECT COUNT(*) FROM skills WHERE install_count < 0",
        "negative_search_content_size": """
            SELECT COUNT(*) FROM skill_search_documents WHERE content_size_bytes < 0
        """,
        "stale_search_document": f"""
            SELECT COUNT(*)
            FROM skill_search_documents AS document
            JOIN skill_versions AS version_row ON version_row.id = document.skill_version_fk
            {metadata_join}
            JOIN skills AS skill ON skill.id = version_row.skill_fk
            JOIN namespaces AS namespace_row ON namespace_row.id = skill.namespace_fk
            LEFT JOIN policy_packs AS policy_pack ON policy_pack.id = version_row.policy_pack_fk
            JOIN skill_contents AS content ON content.id = version_row.content_fk
            WHERE document.slug IS DISTINCT FROM skill.slug
               OR document.version IS DISTINCT FROM version_row.version
               OR document.name IS DISTINCT FROM {metadata}.name
               OR document.description IS DISTINCT FROM {metadata}.description
               OR document.tags IS DISTINCT FROM {metadata}.tags
               OR document.lifecycle_status IS DISTINCT FROM version_row.lifecycle_status
               OR document.trust_tier IS DISTINCT FROM version_row.trust_tier
               OR document.namespace IS DISTINCT FROM namespace_row.slug
               OR document.artifact_origin IS DISTINCT FROM version_row.artifact_origin
               OR document.review_state IS DISTINCT FROM version_row.review_state
               OR document.promotion_channel IS DISTINCT FROM version_row.promotion_channel
               OR document.policy_pack_slug IS DISTINCT FROM policy_pack.slug
               OR document.published_at IS DISTINCT FROM version_row.published_at
               OR document.content_size_bytes IS DISTINCT FROM content.storage_size_bytes
        """,
        "negative_selector_ordinal": """
            SELECT COUNT(*) FROM skill_relationship_selectors WHERE ordinal < 0
        """,
        "duplicate_selector_ordinals": """
            SELECT COUNT(*) FROM (SELECT source_skill_version_fk, edge_type, ordinal
            FROM skill_relationship_selectors GROUP BY source_skill_version_fk, edge_type, ordinal
            HAVING COUNT(*) > 1) AS duplicate_positions
        """,
        "invalid_selector_shape": """
            SELECT COUNT(*) FROM skill_relationship_selectors
            WHERE markers IS NULL OR target_slug IS NULL OR btrim(target_slug) = ''
            OR (edge_type = 'depends_on'
                AND (((target_version IS NULL) = (version_constraint IS NULL))
                OR (target_version IS NOT NULL AND btrim(target_version) = '')
                OR (version_constraint IS NOT NULL AND btrim(version_constraint) = '')))
            OR (edge_type <> 'depends_on' AND (target_version IS NULL OR btrim(target_version) = ''
                OR version_constraint IS NOT NULL OR optional IS NOT NULL OR markers IS NULL
                OR cardinality(markers) <> 0))
        """,
        "indexed_embedding_missing_data": """
            SELECT COUNT(*) FROM skill_search_embeddings
            WHERE index_status = 'indexed' AND (embedding_vector IS NULL OR indexed_at IS NULL)
        """,
        "invalid_co_usage": f"""
            SELECT COUNT(*) FROM skill_co_usage_pairs
            WHERE anchor_skill_fk = related_skill_fk OR distinct_run_count < 0
            OR co_usage_rate < 0 OR co_usage_rate > 1 OR lift_score < 0 OR window_days <= 0
            OR lower(lift_score::text) = 'nan'
            {"OR observation_count < 0" if phase == "before" else ""}
        """,
        "graph_source_ownership": """
            SELECT COUNT(*) FROM skill_graph_edges AS e
            WHERE e.source_skill_version_fk IS NOT NULL AND NOT EXISTS
            (SELECT 1 FROM skill_versions AS v
             WHERE v.id = e.source_skill_version_fk AND v.skill_fk = e.source_skill_fk)
        """,
        "graph_target_slug": """
            SELECT COUNT(*) FROM skill_graph_edges AS e
            WHERE e.target_skill_fk IS NOT NULL AND NOT EXISTS
            (SELECT 1 FROM skills AS s WHERE s.id = e.target_skill_fk AND s.slug = e.target_slug)
        """,
        "invalid_authored_graph_shape": """
            SELECT COUNT(*) FROM skill_graph_edges
            WHERE provenance = 'authored' AND (source_skill_version_fk IS NULL
            OR edge_type NOT IN ('depends_on', 'extends', 'overlaps_with'))
        """,
        "invalid_co_usage_graph_shape": """
            SELECT COUNT(*) FROM skill_graph_edges
            WHERE provenance = 'co_usage' AND (source_skill_version_fk IS NOT NULL
            OR edge_type <> 'relates_to' OR target_skill_fk IS NULL
            OR source_skill_fk >= target_skill_fk)
        """,
    }
    if phase == "before":
        checks["invalid_embedding_dimensions"] = """
            SELECT COUNT(*) FROM skill_search_embeddings
            WHERE embedding_dimensions <> 1536
            """
    else:
        actual_type = _column_type(connection, "skill_search_embeddings", "embedding_vector")
        checks["invalid_embedding_vector_type"] = (
            "SELECT 0" if _norm_type(actual_type) == "halfvec(1536)" else "SELECT 1"
        )
    values = {name: _count(connection, statement) for name, statement in checks.items()}
    report["domain_validity"] = values
    for name, count in values.items():
        if count:
            _issue(report["blocking_violations"], name, count=count)


def _historical_stars(connection: Connection, report: dict[str, Any], phase: Phase) -> None:
    if phase != "before" or "star_count" not in _cols(connection, "skills"):
        return
    count, historical_total, user_total, difference = connection.execute(
        text("""
        WITH counts AS (
            SELECT skill_fk, COUNT(*) AS user_count
            FROM skill_user_stars GROUP BY skill_fk
        )
        SELECT
            COUNT(*) FILTER (WHERE s.star_count <> COALESCE(c.user_count, 0)),
            COALESCE(SUM(s.star_count), 0),
            COALESCE(SUM(COALESCE(c.user_count, 0)), 0),
            COALESCE(SUM(ABS(s.star_count - COALESCE(c.user_count, 0))), 0)
        FROM skills AS s LEFT JOIN counts AS c ON c.skill_fk = s.id
    """)
    ).one()
    if int(count):
        report["advisories"].append(
            {
                "code": "historical_star_count_discrepancy",
                "count": int(count),
                "total_absolute_difference": int(difference),
            }
        )
    report["historical_star_counts"] = {
        "historical_total": int(historical_total),
        "user_total": int(user_total),
        "discrepancy_rows": int(count),
        "total_absolute_difference": int(difference),
    }


def _redundant_value_differences(
    connection: Connection, report: dict[str, Any], phase: Phase
) -> None:
    if phase != "before":
        return
    search_usage = _count(
        connection,
        """
        SELECT COUNT(*)
        FROM skill_search_documents AS document
        JOIN skill_versions AS version_row ON version_row.id = document.skill_version_fk
        JOIN skills AS skill ON skill.id = version_row.skill_fk
        WHERE document.usage_count IS DISTINCT FROM skill.install_count
        """,
    )
    co_usage = _count(
        connection,
        """
        SELECT COUNT(*) FROM skill_co_usage_pairs
        WHERE observation_count IS DISTINCT FROM distinct_run_count
        """,
    )
    report["redundant_value_differences"] = {
        "search_usage_count_vs_install_count": search_usage,
        "co_observation_count_vs_distinct_run_count": co_usage,
    }
    if search_usage:
        _issue(
            report["advisories"],
            "search_usage_count_discrepancy",
            count=search_usage,
        )
    if co_usage:
        _issue(
            report["advisories"],
            "co_observation_count_discrepancy",
            count=co_usage,
        )


def _required_constraints(connection: Connection) -> dict[str, bool]:
    definitions = _constraint_definitions(connection) + _unique_indexes(connection)
    index_names = set(_unique_index_names(connection))

    def has(table: str, *parts: str) -> bool:
        return any(
            table in definition and all(part.lower() in definition.lower() for part in parts)
            for definition in definitions
        )

    return {
        "version_overall_score_range": has("skill_versions", "overall_score", ">=", "<=", "0", "1"),
        "version_maturity_score_range": has(
            "skill_versions", "maturity_score", ">=", "<=", "0", "1"
        ),
        "version_security_score_range": has(
            "skill_versions", "security_score", ">=", "<=", "0", "1"
        ),
        "version_token_estimate_non_negative": has("skill_versions", "token_estimate", ">=", "0"),
        "content_size_matches_payload": has(
            "skill_contents", "storage_size_bytes", "octet_length", "payload"
        ),
        "install_count_non_negative": has("skills", "install_count", ">=", "0"),
        "search_content_size_non_negative": has(
            "skill_search_documents", "content_size_bytes", ">=", "0"
        ),
        "selector_ordinal_non_negative": has("skill_relationship_selectors", "ordinal", ">=", "0"),
        "selector_ordinal_unique": has(
            "skill_relationship_selectors", "source_skill_version_fk", "edge_type", "ordinal"
        ),
        "version_coordinate_unique": has("skill_versions", "skill_fk", "version"),
        "skills_id_slug_unique": has("skills", "id", "slug"),
        "versions_id_skill_unique": has("skill_versions", "id", "skill_fk"),
        "selector_shape": has(
            "skill_relationship_selectors",
            "target_version",
            "version_constraint",
            "optional",
            "markers",
        ),
        "indexed_embedding_shape": has(
            "skill_search_embeddings", "indexed", "embedding_vector", "indexed_at"
        ),
        "co_usage_rate_range": has("skill_co_usage_pairs", "co_usage_rate", ">=", "<=", "0", "1"),
        "co_usage_lift_non_negative": has("skill_co_usage_pairs", "lift_score", ">=", "0"),
        "co_usage_count_non_negative": has("skill_co_usage_pairs", "distinct_run_count", ">=", "0"),
        "co_usage_window_positive": has("skill_co_usage_pairs", "window_days", ">", "0"),
        "co_usage_distinct_skills": has(
            "skill_co_usage_pairs", "anchor_skill_fk", "<>", "related_skill_fk"
        ),
        "graph_source_composite_fk": has(
            "skill_graph_edges",
            "source_skill_version_fk",
            "source_skill_fk",
            "skill_versions",
            "(id, skill_fk)",
        ),
        "graph_target_composite_fk": has(
            "skill_graph_edges", "target_skill_fk", "target_slug", "skills", "(id, slug)"
        ),
        "graph_shape": has("skill_graph_edges", "authored", "co_usage", "relates_to", "depends_on"),
        "graph_authored_unique": "uq_skill_graph_edges_authored" in index_names,
        "graph_co_usage_unique": "uq_skill_graph_edges_co_usage_pair" in index_names,
    }


def _fingerprint(connection: Connection, phase: Phase) -> dict[str, Any]:
    version_sql = (
        """SELECT v.id, v.skill_fk, v.version, v.content_fk, v.checksum_digest,
        v.lifecycle_status, v.lifecycle_changed_at, v.trust_tier, v.artifact_origin,
        v.review_state, v.promotion_channel, v.policy_pack_fk, v.provenance_repo_url,
        v.provenance_commit_sha, v.provenance_tree_path, v.provenance_publisher_identity,
        v.policy_profile_at_publish, v.created_at, v.published_at, m.name, m.description,
        m.tags, m.token_estimate, m.maturity_score, m.security_score, m.overall_score
        FROM skill_versions v JOIN skill_metadata m ON m.id = v.metadata_fk ORDER BY v.id"""
        if phase == "before"
        else """SELECT id, skill_fk, version, content_fk, checksum_digest, lifecycle_status,
        lifecycle_changed_at, trust_tier, artifact_origin, review_state, promotion_channel,
        policy_pack_fk, provenance_repo_url, provenance_commit_sha, provenance_tree_path,
        provenance_publisher_identity, policy_profile_at_publish, created_at, published_at,
        name, description, tags, token_estimate, maturity_score, security_score, overall_score
        FROM skill_versions ORDER BY id"""
    )
    selects = {
        "organizations": "id, slug, display_name, created_at, updated_at",
        "namespaces": "id, organization_fk, slug, visibility, created_at, updated_at",
        "policy_packs": "id, slug, description, rules, created_at, updated_at",
        "skills": "id, slug, namespace_fk, install_count, created_at, updated_at",
        "skill_contents": "id, payload, media_type, storage_size_bytes, checksum_digest",
        "skill_relationship_selectors": """
            id, source_skill_version_fk, edge_type, ordinal, target_slug,
            target_version, version_constraint, optional, markers, created_at
        """,
        "skill_search_documents": """
            skill_version_fk, slug, normalized_slug, version, name, normalized_name,
            description, tags, normalized_tags, lifecycle_status, trust_tier, namespace,
            artifact_origin, review_state, promotion_channel, policy_pack_slug,
            search_vector::text AS search_vector, published_at, content_size_bytes, created_at
        """,
        "skill_search_embeddings": """
            skill_version_fk, embedding_model, source_checksum_digest,
            embedding_vector::text AS vector_text, index_status, indexed_at,
            created_at, updated_at, last_error
        """,
        "skill_usage_observation_runs": "id, source, source_digest, observed_at, created_at",
        "skill_usage_observations": "id, run_fk, skill_fk, created_at",
        "skill_co_usage_pairs": """
            anchor_skill_fk, related_skill_fk, distinct_run_count, co_usage_rate,
            lift_score, last_observed_at, window_days, created_at, updated_at
        """,
        "skill_graph_edges": """
            id, source_skill_fk, source_skill_version_fk, target_skill_fk, target_slug,
            edge_type, provenance, active, confidence, evidence, created_at, updated_at
        """,
        "trust_evidence": """
            id, skill_version_fk, evidence_type, subject, digest, uri, payload, created_at
        """,
        "skill_user_stars": "id, user_subject, skill_fk, created_at",
        "audit_events": "id, event_type, payload, created_at",
    }
    rows = {"skill_versions": _fetch(connection, version_sql)}
    rows.update(
        {
            name: _fetch(connection, f"SELECT {columns} FROM {name} ORDER BY 1")
            for name, columns in selects.items()
        }
    )
    for row in rows["skill_search_embeddings"]:
        row["embedding_vector_sha256"] = _hash_text(row.pop("vector_text", None))
    for row in rows["skill_graph_edges"]:
        if row.get("provenance") == "co_usage" and isinstance(row.get("evidence"), Mapping):
            row["evidence"] = {
                k: v
                for k, v in row["evidence"].items()
                if k not in {"observation_count", "pmi_score"}
            }
    return fingerprint_rows(rows)


def _fetch(connection: Connection, statement: str) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(text(statement)).mappings().all()]


def _count(connection: Connection, statement: str) -> int:
    return int(connection.execute(text(statement)).scalar_one())


def _exists(connection: Connection, table: str) -> bool:
    return bool(
        connection.execute(
            text("SELECT to_regclass(:name)"), {"name": f"public.{table}"}
        ).scalar_one_or_none()
    )


def _cols(connection: Connection, table: str) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = :table
    """),
            {"table": table},
        ).all()
    }


def _not_null(connection: Connection, table: str, column: str) -> bool:
    return bool(
        connection.execute(
            text("""
                SELECT is_nullable = 'NO' FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = :table AND column_name = :column
            """),
            {"table": table, "column": column},
        ).scalar_one_or_none()
    )


def _column_type(connection: Connection, table: str, column: str) -> str:
    return str(
        connection.execute(
            text("""
        SELECT format_type(a.atttypid, a.atttypmod) FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relname = :table AND a.attname = :column
        AND a.attnum > 0 AND NOT a.attisdropped
    """),
            {"table": table, "column": column},
        ).scalar_one_or_none()
        or ""
    )


def _constraint_definitions(connection: Connection) -> list[str]:
    return [
        f"{row[0]}: {row[1]}"
        for row in connection.execute(
            text("""
        SELECT c.relname, pg_get_constraintdef(k.oid) FROM pg_constraint k
        JOIN pg_class c ON c.oid = k.conrelid JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
    """)
        ).all()
    ]


def _unique_indexes(connection: Connection) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            text("""
        SELECT indexdef FROM pg_indexes WHERE schemaname = 'public' AND indexdef ILIKE '%UNIQUE%'
    """)
        ).all()
    ]


def _unique_index_names(connection: Connection) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            text("""
        SELECT indexname FROM pg_indexes
        WHERE schemaname = 'public' AND indexdef ILIKE '%UNIQUE%'
    """)
        ).all()
    ]


def _revision(connection: Connection) -> str | None:
    return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()


def _norm_type(value: str) -> str:
    return "".join(value.lower().split())


def _hash_text(value: object) -> str | None:
    return hashlib.sha256(str(value).encode()).hexdigest() if value is not None else None


def _canonical(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"sha256": hashlib.sha256(value).hexdigest(), "length": len(value)}
    if isinstance(value, Mapping):
        return {
            str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _json(value: Any) -> str:
    return json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _issue(issues: list[dict[str, Any]], code: str, *, count: int = 1, **extra: Any) -> None:
    for issue in issues:
        if issue.get("code") == code and all(
            issue.get(key) == value for key, value in extra.items()
        ):
            issue["count"] = int(issue.get("count", 0)) + count
            return
    issue = {"code": code, **extra}
    if count != 1:
        issue["count"] = count
    issues.append(issue)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("before", "after"))
    parser.add_argument("--before-report", type=Path)
    args = parser.parse_args(argv)
    phase: Phase = args.phase or ("after" if args.before_report else "before")
    try:
        engine = create_engine(migration_database_url(), pool_pre_ping=True)
        try:
            with engine.connect() as connection:
                with connection.begin():
                    connection.execute(
                        text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                    )
                    report = inspect_structure(connection, phase)
        finally:
            engine.dispose()
        if args.before_report:
            comparison = compare_reports(json.loads(args.before_report.read_text()), report)
            report["comparison"] = comparison
            report["blocking_violations"] = comparison["blocking_violations"]
            report["advisories"] = comparison["advisories"]
            report["ok"] = comparison["ok"]
    except (OSError, SQLAlchemyError, RuntimeError, ValueError, json.JSONDecodeError):
        print(json.dumps({"ok": False, "error": "database preflight failed"}, sort_keys=True))
        return 1
    print(_json(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
