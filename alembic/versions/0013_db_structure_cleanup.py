"""Consolidate version metadata and remove redundant derived columns."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0013_db_structure_cleanup"
down_revision = "0012_remove_metadata_schemas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    _set_timeouts(connection)
    _assert_upgrade_preconditions(connection)

    op.add_column("skill_versions", sa.Column("name", sa.Text(), nullable=True))
    op.add_column("skill_versions", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "skill_versions",
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'::text[]"),
        ),
    )
    op.add_column("skill_versions", sa.Column("token_estimate", sa.Integer(), nullable=True))
    op.add_column("skill_versions", sa.Column("maturity_score", sa.Float(), nullable=True))
    op.add_column("skill_versions", sa.Column("security_score", sa.Float(), nullable=True))
    op.add_column("skill_versions", sa.Column("overall_score", sa.Float(), nullable=True))

    connection.execute(
        sa.text(
            """
            UPDATE skill_versions AS version_row
            SET
                name = metadata.name,
                description = metadata.description,
                tags = metadata.tags,
                token_estimate = metadata.token_estimate,
                maturity_score = metadata.maturity_score,
                security_score = metadata.security_score,
                overall_score = metadata.overall_score
            FROM skill_metadata AS metadata
            WHERE metadata.id = version_row.metadata_fk
            """
        )
    )
    _assert_empty(
        connection,
        "metadata_copy_mismatch",
        """
        SELECT version_row.id
        FROM skill_versions AS version_row
        JOIN skill_metadata AS metadata ON metadata.id = version_row.metadata_fk
        WHERE version_row.name IS DISTINCT FROM metadata.name
           OR version_row.description IS DISTINCT FROM metadata.description
           OR version_row.tags IS DISTINCT FROM metadata.tags
           OR version_row.token_estimate IS DISTINCT FROM metadata.token_estimate
           OR version_row.maturity_score IS DISTINCT FROM metadata.maturity_score
           OR version_row.security_score IS DISTINCT FROM metadata.security_score
           OR version_row.overall_score IS DISTINCT FROM metadata.overall_score
        LIMIT 1
        """,
    )

    op.alter_column("skill_versions", "name", nullable=False)
    op.alter_column("skill_versions", "tags", nullable=False)
    op.create_check_constraint(
        "ck_skill_versions_token_estimate",
        "skill_versions",
        "token_estimate >= 0",
    )
    op.create_check_constraint(
        "ck_skill_versions_maturity_score",
        "skill_versions",
        "maturity_score >= 0 AND maturity_score <= 1",
    )
    op.create_check_constraint(
        "ck_skill_versions_security_score",
        "skill_versions",
        "security_score >= 0 AND security_score <= 1",
    )
    op.create_check_constraint(
        "ck_skill_versions_overall_score",
        "skill_versions",
        "overall_score >= 0 AND overall_score <= 1",
    )

    op.create_check_constraint(
        "ck_skill_contents_storage_size",
        "skill_contents",
        "storage_size_bytes = octet_length(payload)",
    )
    op.create_check_constraint("ck_skills_install_count", "skills", "install_count >= 0")
    op.create_check_constraint(
        "ck_skill_search_documents_content_size",
        "skill_search_documents",
        "content_size_bytes >= 0",
    )

    op.create_unique_constraint("uq_skills_id_slug", "skills", ["id", "slug"])
    op.create_unique_constraint(
        "uq_skill_versions_id_skill_fk", "skill_versions", ["id", "skill_fk"]
    )
    op.create_unique_constraint(
        "uq_skill_relationship_selectors_position",
        "skill_relationship_selectors",
        ["source_skill_version_fk", "edge_type", "ordinal"],
    )
    op.drop_index(
        "ix_skill_relationship_selectors_source_edge_type_ordinal",
        table_name="skill_relationship_selectors",
    )
    op.create_check_constraint(
        "ck_skill_relationship_selectors_ordinal",
        "skill_relationship_selectors",
        "ordinal >= 0",
    )
    op.create_check_constraint(
        "ck_skill_relationship_selectors_shape",
        "skill_relationship_selectors",
        _selector_shape_sql(),
    )

    op.drop_constraint(
        "ck_skill_graph_edges_provenance_shape",
        "skill_graph_edges",
        type_="check",
    )
    op.create_check_constraint(
        "ck_skill_graph_edges_provenance_shape",
        "skill_graph_edges",
        _graph_shape_sql(),
    )
    _replace_graph_foreign_keys(connection)

    connection.execute(
        sa.text(
            """
            UPDATE skill_graph_edges
            SET evidence = evidence - ARRAY['observation_count', 'pmi_score']::text[]
            WHERE provenance = 'co_usage'
              AND evidence ?| ARRAY['observation_count', 'pmi_score']::text[]
            """
        )
    )

    op.drop_constraint(
        "ck_skill_search_embeddings_dimensions",
        "skill_search_embeddings",
        type_="check",
    )
    op.drop_column("skill_search_embeddings", "embedding_dimensions")
    op.create_check_constraint(
        "ck_skill_search_embeddings_indexed_shape",
        "skill_search_embeddings",
        "index_status <> 'indexed' OR (embedding_vector IS NOT NULL AND indexed_at IS NOT NULL)",
    )

    op.drop_constraint(
        "ck_skill_co_usage_pairs_counts_non_negative",
        "skill_co_usage_pairs",
        type_="check",
    )
    op.drop_column("skill_co_usage_pairs", "observation_count")
    op.drop_column("skill_co_usage_pairs", "pmi_score")
    op.create_check_constraint(
        "ck_skill_co_usage_pairs_counts_non_negative",
        "skill_co_usage_pairs",
        "distinct_run_count >= 0",
    )
    op.create_check_constraint(
        "ck_skill_co_usage_pairs_co_usage_rate",
        "skill_co_usage_pairs",
        "co_usage_rate >= 0 AND co_usage_rate <= 1",
    )
    op.create_check_constraint(
        "ck_skill_co_usage_pairs_lift_score",
        "skill_co_usage_pairs",
        "lift_score >= 0 AND lift_score <> 'NaN'::numeric",
    )

    op.drop_column("skill_usage_observations", "skill_slug")
    op.drop_column("skill_search_documents", "usage_count")
    op.drop_column("skills", "star_count")
    _drop_foreign_key(connection, "skill_versions", ("metadata_fk",), "skill_metadata")
    op.drop_index("ix_skill_versions_metadata_fk", table_name="skill_versions")
    op.drop_column("skill_versions", "metadata_fk")
    op.drop_table("skill_metadata")
    op.drop_index("ix_skill_versions_skill_fk_version", table_name="skill_versions")


def downgrade() -> None:
    connection = op.get_bind()
    _set_timeouts(connection)

    op.drop_constraint(
        "ck_skill_search_embeddings_indexed_shape",
        "skill_search_embeddings",
        type_="check",
    )
    op.add_column(
        "skill_search_embeddings",
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
    )
    connection.execute(sa.text("UPDATE skill_search_embeddings SET embedding_dimensions = 1536"))
    op.alter_column("skill_search_embeddings", "embedding_dimensions", nullable=False)
    op.create_check_constraint(
        "ck_skill_search_embeddings_dimensions",
        "skill_search_embeddings",
        "embedding_dimensions = 1536",
    )

    op.drop_constraint(
        "ck_skill_co_usage_pairs_co_usage_rate",
        "skill_co_usage_pairs",
        type_="check",
    )
    op.drop_constraint(
        "ck_skill_co_usage_pairs_lift_score",
        "skill_co_usage_pairs",
        type_="check",
    )
    op.drop_constraint(
        "ck_skill_co_usage_pairs_counts_non_negative",
        "skill_co_usage_pairs",
        type_="check",
    )
    op.add_column(
        "skill_co_usage_pairs",
        sa.Column(
            "observation_count",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "skill_co_usage_pairs",
        sa.Column(
            "pmi_score",
            sa.Numeric(10, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    connection.execute(
        sa.text(
            """
            UPDATE skill_co_usage_pairs
            SET
                observation_count = distinct_run_count,
                pmi_score = CASE
                    WHEN lift_score > 0 THEN ROUND(LN(lift_score), 6)
                    ELSE 0
                END
            """
        )
    )
    connection.execute(
        sa.text(
            """
            WITH directional_pairs AS (
                SELECT
                    LEAST(anchor_skill_fk, related_skill_fk) AS source_skill_fk,
                    GREATEST(anchor_skill_fk, related_skill_fk) AS target_skill_fk,
                    MAX(observation_count) AS observation_count,
                    MAX(pmi_score) AS pmi_score
                FROM skill_co_usage_pairs
                GROUP BY
                    LEAST(anchor_skill_fk, related_skill_fk),
                    GREATEST(anchor_skill_fk, related_skill_fk)
            ),
            edge_metrics AS (
                SELECT
                    edge.id,
                    COALESCE(
                        pair.observation_count,
                        NULLIF(edge.evidence ->> 'distinct_run_count', '')::bigint,
                        0
                    ) AS observation_count,
                    COALESCE(
                        pair.pmi_score,
                        CASE
                            WHEN NULLIF(edge.evidence ->> 'lift_score', '')::numeric > 0
                            THEN ROUND(
                                LN(NULLIF(edge.evidence ->> 'lift_score', '')::numeric),
                                6
                            )
                            ELSE 0
                        END
                    ) AS pmi_score
                FROM skill_graph_edges AS edge
                LEFT JOIN directional_pairs AS pair
                    ON pair.source_skill_fk = edge.source_skill_fk
                   AND pair.target_skill_fk = edge.target_skill_fk
                WHERE edge.provenance = 'co_usage'
            )
            UPDATE skill_graph_edges AS edge
            SET evidence = jsonb_set(
                jsonb_set(
                    edge.evidence,
                    '{observation_count}',
                    to_jsonb(metrics.observation_count),
                    TRUE
                ),
                '{pmi_score}',
                to_jsonb(metrics.pmi_score),
                TRUE
            )
            FROM edge_metrics AS metrics
            WHERE edge.id = metrics.id
            """
        )
    )
    op.create_check_constraint(
        "ck_skill_co_usage_pairs_counts_non_negative",
        "skill_co_usage_pairs",
        "observation_count >= 0 AND distinct_run_count >= 0",
    )

    op.add_column(
        "skill_usage_observations",
        sa.Column("skill_slug", sa.Text(), nullable=True),
    )
    connection.execute(
        sa.text(
            """
            UPDATE skill_usage_observations AS observation
            SET skill_slug = skill.slug
            FROM skills AS skill
            WHERE skill.id = observation.skill_fk
            """
        )
    )
    op.alter_column("skill_usage_observations", "skill_slug", nullable=False)

    op.add_column(
        "skill_search_documents",
        sa.Column(
            "usage_count",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    connection.execute(
        sa.text(
            """
            UPDATE skill_search_documents AS document
            SET usage_count = skill.install_count
            FROM skill_versions AS version_row
            JOIN skills AS skill ON skill.id = version_row.skill_fk
            WHERE document.skill_version_fk = version_row.id
            """
        )
    )

    op.add_column(
        "skills",
        sa.Column(
            "star_count",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    connection.execute(
        sa.text(
            """
            UPDATE skills AS skill
            SET star_count = (
                SELECT COUNT(*)
                FROM skill_user_stars AS user_star
                WHERE user_star.skill_fk = skill.id
            )
            """
        )
    )

    op.create_table(
        "skill_metadata",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("token_estimate", sa.Integer(), nullable=True),
        sa.Column("maturity_score", sa.Float(), nullable=True),
        sa.Column("security_score", sa.Float(), nullable=True),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.CheckConstraint(
            "overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 1)",
            name="ck_skill_metadata_overall_score_range",
        ),
    )
    op.add_column("skill_versions", sa.Column("metadata_fk", sa.BigInteger(), nullable=True))
    connection.execute(
        sa.text(
            """
            INSERT INTO skill_metadata (
                id, name, description, tags, token_estimate,
                maturity_score, security_score, overall_score
            )
            SELECT
                ROW_NUMBER() OVER (ORDER BY id),
                name,
                description,
                tags,
                token_estimate,
                maturity_score,
                security_score,
                overall_score
            FROM skill_versions
            """
        )
    )
    connection.execute(
        sa.text(
            """
            WITH ordered_versions AS (
                SELECT id, ROW_NUMBER() OVER (ORDER BY id) AS metadata_id
                FROM skill_versions
            )
            UPDATE skill_versions AS version_row
            SET metadata_fk = ordered_versions.metadata_id
            FROM ordered_versions
            WHERE version_row.id = ordered_versions.id
            """
        )
    )
    op.alter_column("skill_versions", "metadata_fk", nullable=False)
    op.create_foreign_key(
        None,
        "skill_versions",
        "skill_metadata",
        ["metadata_fk"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_skill_versions_metadata_fk", "skill_versions", ["metadata_fk"])
    connection.execute(
        sa.text(
            """
            SELECT setval(
                pg_get_serial_sequence('skill_metadata', 'id'),
                COALESCE(MAX(id), 1),
                MAX(id) IS NOT NULL
            )
            FROM skill_metadata
            """
        )
    )

    _drop_final_constraints_for_downgrade()
    op.create_index(
        "ix_skill_versions_skill_fk_version",
        "skill_versions",
        ["skill_fk", "version"],
    )
    _restore_graph_foreign_keys(connection)

    op.drop_constraint("uq_skill_versions_id_skill_fk", "skill_versions", type_="unique")
    op.drop_constraint("uq_skills_id_slug", "skills", type_="unique")
    op.drop_constraint("ck_skill_contents_storage_size", "skill_contents", type_="check")
    op.drop_constraint("ck_skills_install_count", "skills", type_="check")
    op.drop_constraint(
        "ck_skill_search_documents_content_size",
        "skill_search_documents",
        type_="check",
    )

    op.drop_column("skill_versions", "overall_score")
    op.drop_column("skill_versions", "security_score")
    op.drop_column("skill_versions", "maturity_score")
    op.drop_column("skill_versions", "token_estimate")
    op.drop_column("skill_versions", "tags")
    op.drop_column("skill_versions", "description")
    op.drop_column("skill_versions", "name")


def _set_timeouts(connection: sa.Connection) -> None:
    connection.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
    connection.execute(sa.text("SET LOCAL statement_timeout = '120s'"))


def _assert_upgrade_preconditions(connection: sa.Connection) -> None:
    _assert_empty(
        connection,
        "orphan_metadata",
        """
        SELECT metadata.id
        FROM skill_metadata AS metadata
        WHERE NOT EXISTS (
            SELECT 1 FROM skill_versions AS version_row
            WHERE version_row.metadata_fk = metadata.id
        )
        LIMIT 1
        """,
    )
    _assert_empty(
        connection,
        "version_without_metadata",
        """
        SELECT version_row.id
        FROM skill_versions AS version_row
        LEFT JOIN skill_metadata AS metadata ON metadata.id = version_row.metadata_fk
        WHERE metadata.id IS NULL
        LIMIT 1
        """,
    )
    _assert_empty(
        connection,
        "invalid_metadata_values",
        """
        SELECT version_row.id
        FROM skill_versions AS version_row
        JOIN skill_metadata AS metadata ON metadata.id = version_row.metadata_fk
        WHERE metadata.name IS NULL
           OR metadata.tags IS NULL
           OR metadata.token_estimate < 0
           OR metadata.maturity_score < 0 OR metadata.maturity_score > 1
           OR metadata.security_score < 0 OR metadata.security_score > 1
           OR metadata.overall_score < 0 OR metadata.overall_score > 1
        LIMIT 1
        """,
    )
    _assert_empty(
        connection,
        "invalid_content_size",
        """
        SELECT id
        FROM skill_contents
        WHERE storage_size_bytes <> octet_length(payload)
        LIMIT 1
        """,
    )
    _assert_empty(
        connection,
        "invalid_install_count",
        "SELECT id FROM skills WHERE install_count < 0 LIMIT 1",
    )
    _assert_empty(
        connection,
        "invalid_search_content_size",
        "SELECT skill_version_fk FROM skill_search_documents WHERE content_size_bytes < 0 LIMIT 1",
    )
    _assert_empty(
        connection,
        "stale_search_document",
        """
        SELECT document.skill_version_fk
        FROM skill_search_documents AS document
        JOIN skill_versions AS version_row
            ON version_row.id = document.skill_version_fk
        JOIN skill_metadata AS metadata
            ON metadata.id = version_row.metadata_fk
        JOIN skills AS skill
            ON skill.id = version_row.skill_fk
        JOIN namespaces AS namespace_row
            ON namespace_row.id = skill.namespace_fk
        LEFT JOIN policy_packs AS policy_pack
            ON policy_pack.id = version_row.policy_pack_fk
        JOIN skill_contents AS content
            ON content.id = version_row.content_fk
        WHERE document.slug IS DISTINCT FROM skill.slug
           OR document.version IS DISTINCT FROM version_row.version
           OR document.name IS DISTINCT FROM metadata.name
           OR document.description IS DISTINCT FROM metadata.description
           OR document.tags IS DISTINCT FROM metadata.tags
           OR document.lifecycle_status IS DISTINCT FROM version_row.lifecycle_status
           OR document.trust_tier IS DISTINCT FROM version_row.trust_tier
           OR document.namespace IS DISTINCT FROM namespace_row.slug
           OR document.artifact_origin IS DISTINCT FROM version_row.artifact_origin
           OR document.review_state IS DISTINCT FROM version_row.review_state
           OR document.promotion_channel IS DISTINCT FROM version_row.promotion_channel
           OR document.policy_pack_slug IS DISTINCT FROM policy_pack.slug
           OR document.published_at IS DISTINCT FROM version_row.published_at
           OR document.content_size_bytes IS DISTINCT FROM content.storage_size_bytes
        LIMIT 1
        """,
    )
    _assert_empty(
        connection,
        "duplicate_selector_positions",
        """
        SELECT source_skill_version_fk, edge_type, ordinal
        FROM skill_relationship_selectors
        GROUP BY source_skill_version_fk, edge_type, ordinal
        HAVING COUNT(*) > 1
        LIMIT 1
        """,
    )
    _assert_empty(
        connection,
        "invalid_selector_rows",
        f"""
        SELECT id
        FROM skill_relationship_selectors
        WHERE ordinal < 0
           OR target_slug IS NULL OR btrim(target_slug) = ''
           OR markers IS NULL
           OR (edge_type = 'depends_on' AND (
                   (target_version IS NOT NULL AND btrim(target_version) = '')
                OR (version_constraint IS NOT NULL AND btrim(version_constraint) = '')
               ))
           OR (edge_type <> 'depends_on' AND (
                   target_version IS NULL OR btrim(target_version) = ''
               ))
           OR NOT ({_selector_shape_sql()})
        LIMIT 1
        """,
    )
    _assert_empty(
        connection,
        "invalid_observation_slug",
        """
        SELECT observation.id
        FROM skill_usage_observations AS observation
        JOIN skills AS skill ON skill.id = observation.skill_fk
        WHERE observation.skill_slug IS DISTINCT FROM skill.slug
        LIMIT 1
        """,
    )
    _assert_empty(
        connection,
        "invalid_graph_identifiers",
        """
        SELECT edge.id
        FROM skill_graph_edges AS edge
        WHERE edge.provenance NOT IN ('authored', 'co_usage')
           OR edge.edge_type NOT IN ('depends_on', 'extends', 'overlaps_with', 'relates_to')
           OR (edge.source_skill_version_fk IS NOT NULL AND NOT EXISTS (
                   SELECT 1 FROM skill_versions AS version_row
                   WHERE version_row.id = edge.source_skill_version_fk
                     AND version_row.skill_fk = edge.source_skill_fk
               ))
           OR (edge.target_skill_fk IS NOT NULL AND NOT EXISTS (
                   SELECT 1 FROM skills AS target
                   WHERE target.id = edge.target_skill_fk
                     AND target.slug = edge.target_slug
               ))
           OR (edge.provenance = 'authored' AND (
                   edge.source_skill_version_fk IS NULL
                   OR edge.edge_type NOT IN ('depends_on', 'extends', 'overlaps_with')
               ))
           OR (edge.provenance = 'co_usage' AND (
                   edge.source_skill_version_fk IS NOT NULL
                   OR edge.edge_type <> 'relates_to'
                   OR edge.target_skill_fk IS NULL
                   OR edge.source_skill_fk >= edge.target_skill_fk
               ))
        LIMIT 1
        """,
    )
    _assert_empty(
        connection,
        "invalid_embedding_rows",
        """
        SELECT skill_version_fk, embedding_model
        FROM skill_search_embeddings
        WHERE embedding_dimensions <> 1536
           OR (index_status = 'indexed' AND (embedding_vector IS NULL OR indexed_at IS NULL))
        LIMIT 1
        """,
    )
    _assert_empty(
        connection,
        "invalid_co_usage_rows",
        """
        SELECT anchor_skill_fk, related_skill_fk
        FROM skill_co_usage_pairs
        WHERE anchor_skill_fk = related_skill_fk
           OR observation_count < 0
           OR distinct_run_count < 0
           OR co_usage_rate < 0 OR co_usage_rate > 1
           OR lift_score < 0 OR lift_score = 'NaN'::numeric
           OR window_days <= 0
        LIMIT 1
        """,
    )


def _assert_empty(
    connection: sa.Connection,
    code: str,
    statement: str,
) -> None:
    row = connection.execute(sa.text(statement)).first()
    if row is not None:
        raise RuntimeError(f"0013 preflight blocked: {code}: {tuple(row)}")


def _selector_shape_sql() -> str:
    return """(edge_type = 'depends_on'
                AND ((target_version IS NOT NULL) <> (version_constraint IS NOT NULL)))
            OR (edge_type <> 'depends_on' AND target_version IS NOT NULL
                AND version_constraint IS NULL AND optional IS NULL AND cardinality(markers) = 0)"""


def _graph_shape_sql() -> str:
    return """
            (provenance = 'authored' AND source_skill_version_fk IS NOT NULL
                AND edge_type IN ('depends_on', 'extends', 'overlaps_with'))
            OR (
                provenance = 'co_usage'
                AND source_skill_version_fk IS NULL
                AND edge_type = 'relates_to'
                AND target_skill_fk IS NOT NULL
                AND source_skill_fk < target_skill_fk
            )
            """


def _foreign_key_name(
    connection: sa.Connection,
    table: str,
    columns: tuple[str, ...],
    referred_table: str,
) -> str:
    for foreign_key in inspect(connection).get_foreign_keys(table):
        if (
            foreign_key.get("referred_table") == referred_table
            and tuple(foreign_key.get("constrained_columns") or ()) == columns
        ):
            name = foreign_key.get("name")
            if name:
                return str(name)
    raise RuntimeError(f"0013 preflight blocked: missing foreign key {table}({', '.join(columns)})")


def _drop_foreign_key(
    connection: sa.Connection,
    table: str,
    columns: tuple[str, ...],
    referred_table: str,
) -> None:
    name = _foreign_key_name(connection, table, columns, referred_table)
    op.drop_constraint(name, table, type_="foreignkey")


def _replace_graph_foreign_keys(connection: sa.Connection) -> None:
    _drop_foreign_key(
        connection,
        "skill_graph_edges",
        ("source_skill_version_fk",),
        "skill_versions",
    )
    _drop_foreign_key(
        connection,
        "skill_graph_edges",
        ("target_skill_fk",),
        "skills",
    )
    op.create_foreign_key(
        "fk_skill_graph_edges_source_version",
        "skill_graph_edges",
        "skill_versions",
        ["source_skill_version_fk", "source_skill_fk"],
        ["id", "skill_fk"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_skill_graph_edges_target",
        "skill_graph_edges",
        "skills",
        ["target_skill_fk", "target_slug"],
        ["id", "slug"],
        ondelete="CASCADE",
    )


def _restore_graph_foreign_keys(connection: sa.Connection) -> None:
    op.drop_constraint(
        "fk_skill_graph_edges_source_version",
        "skill_graph_edges",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_skill_graph_edges_target",
        "skill_graph_edges",
        type_="foreignkey",
    )
    op.create_foreign_key(
        None,
        "skill_graph_edges",
        "skill_versions",
        ["source_skill_version_fk"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        None,
        "skill_graph_edges",
        "skills",
        ["target_skill_fk"],
        ["id"],
        ondelete="CASCADE",
    )


def _drop_final_constraints_for_downgrade() -> None:
    for constraint_name in (
        "ck_skill_versions_overall_score",
        "ck_skill_versions_security_score",
        "ck_skill_versions_maturity_score",
        "ck_skill_versions_token_estimate",
    ):
        op.drop_constraint(constraint_name, "skill_versions", type_="check")
    op.drop_constraint(
        "ck_skill_graph_edges_provenance_shape",
        "skill_graph_edges",
        type_="check",
    )
    op.create_check_constraint(
        "ck_skill_graph_edges_provenance_shape",
        "skill_graph_edges",
        """
            (provenance = 'authored' AND source_skill_version_fk IS NOT NULL)
            OR (
                provenance = 'co_usage'
                AND edge_type = 'relates_to'
                AND target_skill_fk IS NOT NULL
                AND source_skill_fk < target_skill_fk
            )
            """,
    )
    op.drop_constraint(
        "ck_skill_relationship_selectors_shape",
        "skill_relationship_selectors",
        type_="check",
    )
    op.drop_constraint(
        "ck_skill_relationship_selectors_ordinal",
        "skill_relationship_selectors",
        type_="check",
    )
    op.drop_constraint(
        "uq_skill_relationship_selectors_position",
        "skill_relationship_selectors",
        type_="unique",
    )
    op.create_index(
        "ix_skill_relationship_selectors_source_edge_type_ordinal",
        "skill_relationship_selectors",
        ["source_skill_version_fk", "edge_type", "ordinal"],
    )
