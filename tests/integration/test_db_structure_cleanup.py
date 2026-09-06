"""Populated preflight and cleanup migration coverage."""

from __future__ import annotations

import hashlib
from collections.abc import Generator

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from alembic import command
from scripts.check_db_structure import compare_reports, inspect_structure

pytestmark = pytest.mark.integration

_FINAL_INVALID_WRITES = (
    (
        "maturity score",
        "UPDATE skill_versions SET maturity_score = 2 WHERE version = '1.0.0'",
    ),
    (
        "security score",
        "UPDATE skill_versions SET security_score = -1 WHERE version = '1.0.0'",
    ),
    (
        "overall score",
        "UPDATE skill_versions SET overall_score = 2 WHERE version = '1.0.0'",
    ),
    (
        "token estimate",
        "UPDATE skill_versions SET token_estimate = -1 WHERE version = '1.0.0'",
    ),
    ("install count", "UPDATE skills SET install_count = -1"),
    (
        "content size",
        "UPDATE skill_contents SET storage_size_bytes = storage_size_bytes + 1",
    ),
    (
        "search content size",
        "UPDATE skill_search_documents SET content_size_bytes = -1",
    ),
    (
        "duplicate selector ordinal",
        """
        INSERT INTO skill_relationship_selectors (
            source_skill_version_fk, edge_type, ordinal, target_slug,
            target_version, version_constraint, optional, markers
        )
        SELECT source_skill_version_fk, edge_type, ordinal, target_slug,
               target_version, version_constraint, optional, markers
        FROM skill_relationship_selectors WHERE edge_type = 'depends_on' LIMIT 1
        """,
    ),
    (
        "malformed selector",
        "UPDATE skill_relationship_selectors SET target_version = NULL WHERE edge_type = 'extends'",
    ),
    (
        "negative selector ordinal",
        "UPDATE skill_relationship_selectors SET ordinal = -1 WHERE edge_type = 'extends'",
    ),
    (
        "graph source ownership",
        """
        UPDATE skill_graph_edges
        SET source_skill_fk = (SELECT id FROM skills WHERE slug = 'cleanup-target')
        WHERE provenance = 'authored'
        """,
    ),
    (
        "graph target slug",
        """
        UPDATE skill_graph_edges
        SET target_skill_fk = (SELECT id FROM skills WHERE slug = 'cleanup-source')
        WHERE provenance = 'authored'
        """,
    ),
    (
        "co-usage ordering",
        """
        UPDATE skill_graph_edges
        SET source_skill_fk = (SELECT id FROM skills WHERE slug = 'cleanup-target')
        WHERE provenance = 'co_usage'
        """,
    ),
    (
        "indexed vector",
        "UPDATE skill_search_embeddings SET embedding_vector = NULL WHERE index_status = 'indexed'",
    ),
    (
        "indexed timestamp",
        "UPDATE skill_search_embeddings SET indexed_at = NULL WHERE index_status = 'indexed'",
    ),
    (
        "negative co-usage count",
        "UPDATE skill_co_usage_pairs SET distinct_run_count = -1",
    ),
    (
        "co-usage rate",
        "UPDATE skill_co_usage_pairs SET co_usage_rate = 2",
    ),
    (
        "negative lift",
        "UPDATE skill_co_usage_pairs SET lift_score = -1",
    ),
    (
        "NaN lift",
        "UPDATE skill_co_usage_pairs SET lift_score = 'NaN'::numeric",
    ),
    (
        "co-usage window",
        "UPDATE skill_co_usage_pairs SET window_days = 0",
    ),
    (
        "co-usage distinct skills",
        "UPDATE skill_co_usage_pairs SET related_skill_fk = anchor_skill_fk",
    ),
)


def _config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _report(database_url: str, phase: str) -> dict[str, object]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                )
                return inspect_structure(connection, phase)  # type: ignore[arg-type]
    finally:
        engine.dispose()


@pytest.fixture
def populated_0012_database(
    clean_integration_database: str,
) -> Generator[str, None, None]:
    """Seed revision 0012 with shared canonical rows and derived signals."""
    database_url = clean_integration_database
    config = _config(database_url)
    command.upgrade(config, "0012_remove_metadata_schemas")

    payload_a = b"shared canonical artifact"
    payload_b = b"nullable metadata artifact"
    vector = "[" + ",".join("0.1" for _ in range(1536)) + "]"
    checksum_a = hashlib.sha256(payload_a).hexdigest()
    checksum_b = hashlib.sha256(payload_b).hexdigest()
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            namespace_id = connection.execute(
                text("SELECT id FROM namespaces WHERE slug = 'public'")
            ).scalar_one()
            policy_id = connection.execute(
                text(
                    """
                    INSERT INTO policy_packs (slug, description, rules)
                    VALUES ('cleanup-policy', 'fixture policy', '{"allow": true}'::jsonb)
                    RETURNING id
                    """
                )
            ).scalar_one()
            skill_ids: dict[str, int] = {}
            for slug, install_count, star_count in (
                ("cleanup-source", 17, 5),
                ("cleanup-target", 3, 1),
            ):
                skill_ids[slug] = int(
                    connection.execute(
                        text(
                            """
                            INSERT INTO skills (slug, namespace_fk, install_count, star_count)
                            VALUES (:slug, :namespace_id, :install_count, :star_count)
                            RETURNING id
                            """
                        ),
                        {
                            "slug": slug,
                            "namespace_id": namespace_id,
                            "install_count": install_count,
                            "star_count": star_count,
                        },
                    ).scalar_one()
                )

            content_ids: dict[str, int] = {}
            for name, payload, checksum in (
                ("shared", payload_a, checksum_a),
                ("nullable", payload_b, checksum_b),
            ):
                content_ids[name] = int(
                    connection.execute(
                        text(
                            """
                            INSERT INTO skill_contents (
                                payload, media_type, storage_size_bytes, checksum_digest
                            )
                            VALUES (:payload, 'application/zstd', :size_bytes, :checksum)
                            RETURNING id
                            """
                        ),
                        {
                            "payload": payload,
                            "size_bytes": len(payload),
                            "checksum": checksum,
                        },
                    ).scalar_one()
                )

            metadata_ids: dict[str, int] = {}
            metadata_values = {
                "shared": {
                    "name": "Shared metadata",
                    "description": "Used by two versions",
                    "tags": ["cleanup", "shared"],
                    "token_estimate": 90,
                    "maturity_score": 0.8,
                    "security_score": 0.9,
                    "overall_score": 0.85,
                },
                "nullable": {
                    "name": "Nullable metadata",
                    "description": None,
                    "tags": [],
                    "token_estimate": None,
                    "maturity_score": None,
                    "security_score": None,
                    "overall_score": None,
                },
            }
            for key, values in metadata_values.items():
                metadata_ids[key] = int(
                    connection.execute(
                        text(
                            """
                            INSERT INTO skill_metadata (
                                name, description, tags, token_estimate,
                                maturity_score, security_score, overall_score
                            )
                            VALUES (
                                :name, :description, :tags, :token_estimate,
                                :maturity_score, :security_score, :overall_score
                            )
                            RETURNING id
                            """
                        ),
                        values,
                    ).scalar_one()
                )

            version_ids: dict[tuple[str, str], int] = {}
            version_values = (
                (
                    "cleanup-source",
                    "1.0.0",
                    "shared",
                    "shared",
                    "internal",
                    "approved",
                    "prod",
                    None,
                ),
                (
                    "cleanup-source",
                    "2.0.0",
                    "shared",
                    "shared",
                    "imported",
                    "pending_review",
                    "staging",
                    policy_id,
                ),
                (
                    "cleanup-target",
                    "1.0.0",
                    "nullable",
                    "nullable",
                    "verified",
                    "approved",
                    "prod",
                    policy_id,
                ),
            )
            for (
                slug,
                version,
                content_key,
                metadata_key,
                artifact_origin,
                review_state,
                promotion_channel,
                version_policy_id,
            ) in version_values:
                version_ids[(slug, version)] = int(
                    connection.execute(
                        text(
                            """
                            INSERT INTO skill_versions (
                                skill_fk, version, content_fk, metadata_fk,
                                checksum_digest, artifact_origin, review_state,
                                promotion_channel, policy_pack_fk,
                                provenance_repo_url, provenance_commit_sha,
                                provenance_tree_path, provenance_publisher_identity,
                                policy_profile_at_publish
                            )
                            VALUES (
                                :skill_id, :version, :content_id, :metadata_id,
                                :checksum, :artifact_origin, :review_state,
                                :promotion_channel, :policy_id,
                                'https://example.invalid/cleanup', 'abc123',
                                'skills/cleanup', 'fixture-publisher', 'strict'
                            )
                            RETURNING id
                            """
                        ),
                        {
                            "skill_id": skill_ids[slug],
                            "version": version,
                            "content_id": content_ids[content_key],
                            "metadata_id": metadata_ids[metadata_key],
                            "checksum": hashlib.sha256(f"{slug}:{version}".encode()).hexdigest(),
                            "artifact_origin": artifact_origin,
                            "review_state": review_state,
                            "promotion_channel": promotion_channel,
                            "policy_id": version_policy_id,
                        },
                    ).scalar_one()
                )

            selectors = (
                (
                    ("cleanup-source", "1.0.0"),
                    "depends_on",
                    0,
                    "cleanup-target",
                    "1.0.0",
                    None,
                    True,
                    ["python_version >= '3.12'"],
                ),
                (
                    ("cleanup-source", "2.0.0"),
                    "extends",
                    0,
                    "cleanup-target",
                    "1.0.0",
                    None,
                    None,
                    [],
                ),
                (
                    ("cleanup-target", "1.0.0"),
                    "overlaps_with",
                    0,
                    "cleanup-source",
                    "1.0.0",
                    None,
                    None,
                    [],
                ),
            )
            for (
                source_coordinate,
                edge_type,
                ordinal,
                target_slug,
                target_version,
                version_constraint,
                optional,
                markers,
            ) in selectors:
                connection.execute(
                    text(
                        """
                        INSERT INTO skill_relationship_selectors (
                            source_skill_version_fk, edge_type, ordinal,
                            target_slug, target_version, version_constraint,
                            optional, markers
                        )
                        VALUES (
                            :source_version_id, :edge_type, :ordinal,
                            :target_slug, :target_version, :version_constraint,
                            :optional, :markers
                        )
                        """
                    ),
                    {
                        "source_version_id": version_ids[source_coordinate],
                        "edge_type": edge_type,
                        "ordinal": ordinal,
                        "target_slug": target_slug,
                        "target_version": target_version,
                        "version_constraint": version_constraint,
                        "optional": optional,
                        "markers": markers,
                    },
                )

            connection.execute(
                text(
                    """
                    INSERT INTO skill_search_documents (
                        skill_version_fk, slug, normalized_slug, version, name,
                        normalized_name, description, tags, normalized_tags,
                        lifecycle_status, trust_tier, namespace, artifact_origin,
                        review_state, promotion_channel, policy_pack_slug,
                        search_vector, published_at, content_size_bytes, usage_count
                    )
                    SELECT
                        version_row.id, skill.slug, lower(skill.slug), version_row.version,
                        metadata.name, lower(metadata.name), metadata.description,
                        metadata.tags, metadata.tags, version_row.lifecycle_status,
                        version_row.trust_tier, 'public', version_row.artifact_origin,
                        version_row.review_state, version_row.promotion_channel,
                        CASE
                            WHEN version_row.policy_pack_fk IS NULL THEN NULL
                            ELSE 'cleanup-policy'
                        END,
                        to_tsvector('simple', metadata.name), version_row.published_at,
                        content.storage_size_bytes, 33
                    FROM skill_versions AS version_row
                    JOIN skills AS skill ON skill.id = version_row.skill_fk
                    JOIN skill_metadata AS metadata ON metadata.id = version_row.metadata_fk
                    JOIN skill_contents AS content ON content.id = version_row.content_fk
                    """
                )
            )

            connection.execute(
                text(
                    """
                    INSERT INTO skill_search_embeddings (
                        skill_version_fk, embedding_model, embedding_dimensions,
                        source_checksum_digest, embedding_vector, index_status, indexed_at
                    )
                    VALUES (
                        :version_id, 'fixture-model', 1536, :source_checksum,
                        CAST(:vector AS halfvec(1536)), 'indexed', CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "version_id": version_ids[("cleanup-source", "1.0.0")],
                    "source_checksum": "a" * 64,
                    "vector": vector,
                },
            )

            run_id = connection.execute(
                text(
                    """
                    INSERT INTO skill_usage_observation_runs (source, source_digest, observed_at)
                    VALUES ('fixture', :digest, CURRENT_TIMESTAMP)
                    RETURNING id
                    """
                ),
                {"digest": "b" * 64},
            ).scalar_one()
            for slug in ("cleanup-source", "cleanup-target"):
                connection.execute(
                    text(
                        """
                        INSERT INTO skill_usage_observations (run_fk, skill_fk, skill_slug)
                        VALUES (:run_id, :skill_id, :slug)
                        """
                    ),
                    {"run_id": run_id, "skill_id": skill_ids[slug], "slug": slug},
                )
            connection.execute(
                text(
                    """
                    INSERT INTO skill_co_usage_pairs (
                        anchor_skill_fk, related_skill_fk, observation_count,
                        distinct_run_count, co_usage_rate, lift_score, pmi_score, window_days
                    )
                    VALUES (:anchor, :related, 4, 2, 0.5, 1.2, 0.3, 90)
                    """
                ),
                {
                    "anchor": skill_ids["cleanup-source"],
                    "related": skill_ids["cleanup-target"],
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO skill_graph_edges (
                        source_skill_fk, source_skill_version_fk, target_skill_fk,
                        target_slug, edge_type, provenance, active, confidence, evidence
                    )
                    VALUES
                        (:source, :source_version, :target, 'cleanup-target',
                         'overlaps_with', 'authored', TRUE, 0.9, '{"ordinal": 0}'::jsonb),
                        (:source, NULL, :target, 'cleanup-target',
                         'relates_to', 'co_usage', TRUE, 0.7,
                         '{"observation_count": 4, "pmi_score": 0.3,
                           "window_days": 90, "retained": "fixture"}'::jsonb)
                    """
                ),
                {
                    "source": skill_ids["cleanup-source"],
                    "source_version": version_ids[("cleanup-source", "1.0.0")],
                    "target": skill_ids["cleanup-target"],
                },
            )
            for skill_slug, user_subject in (
                ("cleanup-source", "user-a"),
                ("cleanup-source", "user-b"),
                ("cleanup-target", "user-a"),
            ):
                connection.execute(
                    text(
                        """
                        INSERT INTO skill_user_stars (user_subject, skill_fk)
                        VALUES (:subject, :skill_id)
                        """
                    ),
                    {"subject": user_subject, "skill_id": skill_ids[skill_slug]},
                )
            connection.execute(
                text(
                    """
                    INSERT INTO trust_evidence (
                        skill_version_fk, evidence_type, subject, digest, uri, payload
                    )
                    VALUES (
                        :version_id, 'signature', 'fixture-publisher', :digest,
                        'https://example.invalid/evidence', '{"verified": true}'::jsonb
                    )
                    """
                ),
                {
                    "version_id": version_ids[("cleanup-source", "1.0.0")],
                    "digest": "c" * 64,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO audit_events (event_type, payload)
                    VALUES ('fixture.publish', '{"fixture": true}'::jsonb)
                    """
                )
            )
    finally:
        engine.dispose()

    yield database_url


def test_populated_upgrade_and_downgrade_preserve_canonical_fingerprint(
    populated_0012_database: str,
) -> None:
    database_url = populated_0012_database
    config = _config(database_url)
    before = _report(database_url, "before")
    assert before["ok"] is True
    assert before["metadata_coverage"]["shared_metadata_rows"] == 1
    assert before["advisories"]
    assert before["redundant_value_differences"] == {
        "search_usage_count_vs_install_count": 3,
        "co_observation_count_vs_distinct_run_count": 1,
    }
    assert before["historical_star_counts"] == {
        "historical_total": 6,
        "user_total": 3,
        "discrepancy_rows": 1,
        "total_absolute_difference": 3,
    }

    command.upgrade(config, "0013_db_structure_cleanup")
    after = _report(database_url, "after")
    assert after["ok"] is True
    assert all(after["required_constraints"].values())
    assert compare_reports(before, after)["ok"] is True

    command.downgrade(config, "0012_remove_metadata_schemas")
    restored = _report(database_url, "before")
    assert restored["ok"] is True
    assert restored["canonical_fingerprint"] == before["canonical_fingerprint"]

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            evidence = connection.execute(
                text("SELECT evidence FROM skill_graph_edges WHERE provenance = 'co_usage'")
            ).scalar_one()
    finally:
        engine.dispose()
    assert evidence["observation_count"] == 2
    assert evidence["pmi_score"] == pytest.approx(0.182322)
    assert evidence["window_days"] == 90
    assert evidence["retained"] == "fixture"

    command.upgrade(config, "0013_db_structure_cleanup")
    upgraded_again = _report(database_url, "after")
    assert upgraded_again["ok"] is True
    assert upgraded_again["canonical_fingerprint"] == after["canonical_fingerprint"]


def test_canonical_fingerprint_covers_all_versions_and_metadata_values(
    populated_0012_database: str,
) -> None:
    database_url = populated_0012_database
    before = _report(database_url, "before")
    assert before["canonical_fingerprint"]["tables"]["skill_versions"]["rows"] == 3

    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE skill_metadata SET description = 'fingerprint mutation' "
                    "WHERE name = 'Shared metadata'"
                )
            )
    finally:
        engine.dispose()

    mutated = _report(database_url, "before")
    assert mutated["canonical_fingerprint"] != before["canonical_fingerprint"]


@pytest.mark.parametrize("case,statement", _FINAL_INVALID_WRITES)
def test_final_constraints_reject_invalid_direct_sql_write(
    populated_0012_database: str,
    case: str,
    statement: str,
) -> None:
    database_url = populated_0012_database
    config = _config(database_url)
    command.upgrade(config, "0013_db_structure_cleanup")

    engine = create_engine(database_url)
    try:
        with pytest.raises(SQLAlchemyError):
            with engine.begin() as connection:
                connection.execute(text(statement))
        with engine.connect() as connection:
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == "0013_db_structure_cleanup"
            ), case
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("case", "violation_code"),
    [
        ("score", "invalid_metadata_scores"),
        ("duplicate_selector", "duplicate_selector_ordinals"),
        ("malformed_selector", "invalid_selector_shape"),
        ("stale_search_document", "stale_search_document"),
        ("graph_mismatch", "graph_target_slug"),
        ("orphan_metadata", "orphan_metadata"),
    ],
)
def test_invalid_canonical_data_aborts_upgrade_atomically(
    populated_0012_database: str,
    case: str,
    violation_code: str,
) -> None:
    database_url = populated_0012_database
    config = _config(database_url)
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            if case == "score":
                connection.execute(
                    text(
                        "ALTER TABLE skill_metadata "
                        "DROP CONSTRAINT ck_skill_metadata_overall_score_range"
                    )
                )
                connection.execute(text("UPDATE skill_metadata SET overall_score = 2.0"))
            elif case == "duplicate_selector":
                connection.execute(
                    text(
                        """
                        INSERT INTO skill_relationship_selectors (
                            source_skill_version_fk, edge_type, ordinal, target_slug,
                            target_version, version_constraint, optional, markers
                        )
                        SELECT source_skill_version_fk, edge_type, ordinal, target_slug,
                               target_version, version_constraint, optional, markers
                        FROM skill_relationship_selectors WHERE edge_type = 'depends_on'
                        LIMIT 1
                        """
                    )
                )
            elif case == "malformed_selector":
                connection.execute(
                    text(
                        "UPDATE skill_relationship_selectors SET target_version = NULL "
                        "WHERE edge_type = 'extends'"
                    )
                )
            elif case == "stale_search_document":
                connection.execute(
                    text(
                        "UPDATE skill_search_documents SET name = 'stale projection' "
                        "WHERE slug = 'cleanup-source' AND version = '1.0.0'"
                    )
                )
            elif case == "graph_mismatch":
                connection.execute(
                    text(
                        """
                        UPDATE skill_graph_edges
                        SET target_skill_fk = (SELECT id FROM skills WHERE slug = 'cleanup-source')
                        WHERE provenance = 'authored'
                        """
                    )
                )
            elif case == "orphan_metadata":
                connection.execute(
                    text(
                        """
                        INSERT INTO skill_metadata (name, description, tags)
                        VALUES ('orphan metadata', NULL, ARRAY[]::text[])
                        """
                    )
                )
    finally:
        engine.dispose()

    before = _report(database_url, "before")
    assert before["ok"] is False
    assert any(issue["code"] == violation_code for issue in before["blocking_violations"])

    with pytest.raises((RuntimeError, SQLAlchemyError, ValueError)):
        command.upgrade(config, "0013_db_structure_cleanup")

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == ("0012_remove_metadata_schemas")
            assert "metadata_fk" in {
                column["name"] for column in inspect(connection).get_columns("skill_versions")
            }
            assert "name" not in {
                column["name"] for column in inspect(connection).get_columns("skill_versions")
            }
    finally:
        engine.dispose()
