"""Add unified skill graph edge projection.

Revision ID: 0009_skill_graph_edges
Revises: 0008_skill_user_stars
Create Date: 2026-06-03
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0009_skill_graph_edges"
down_revision = "0008_skill_user_stars"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skill_graph_edges",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_skill_fk", sa.BigInteger(), nullable=False),
        sa.Column("source_skill_version_fk", sa.BigInteger(), nullable=True),
        sa.Column("target_skill_fk", sa.BigInteger(), nullable=True),
        sa.Column("target_slug", sa.Text(), nullable=False),
        sa.Column("edge_type", sa.Text(), nullable=False),
        sa.Column("provenance", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
        sa.Column("confidence", sa.Numeric(10, 6), nullable=True),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "edge_type IN ('depends_on', 'extends', 'overlaps_with', 'relates_to')",
            name="ck_skill_graph_edges_edge_type",
        ),
        sa.CheckConstraint(
            "provenance IN ('authored', 'co_usage')",
            name="ck_skill_graph_edges_provenance",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_skill_graph_edges_confidence_range",
        ),
        sa.CheckConstraint(
            """
            (provenance = 'authored' AND source_skill_version_fk IS NOT NULL)
            OR (
                provenance = 'co_usage'
                AND edge_type = 'relates_to'
                AND target_skill_fk IS NOT NULL
                AND source_skill_fk < target_skill_fk
            )
            """,
            name="ck_skill_graph_edges_provenance_shape",
        ),
        sa.ForeignKeyConstraint(["source_skill_fk"], ["skills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_skill_version_fk"],
            ["skill_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["target_skill_fk"], ["skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_skill_graph_edges_active_source_edge",
        "skill_graph_edges",
        ["active", "source_skill_fk", "edge_type"],
        unique=False,
    )
    op.create_index(
        "ix_skill_graph_edges_target_skill_fk",
        "skill_graph_edges",
        ["target_skill_fk"],
        unique=False,
    )
    op.create_index(
        "uq_skill_graph_edges_authored",
        "skill_graph_edges",
        ["source_skill_version_fk", "target_slug", "edge_type", "provenance"],
        unique=True,
        postgresql_where=sa.text("provenance = 'authored'"),
    )
    op.create_index(
        "uq_skill_graph_edges_co_usage_pair",
        "skill_graph_edges",
        ["source_skill_fk", "target_skill_fk", "edge_type", "provenance"],
        unique=True,
        postgresql_where=sa.text("provenance = 'co_usage'"),
    )
    op.execute(
        """
        INSERT INTO skill_graph_edges (
            source_skill_fk,
            source_skill_version_fk,
            target_skill_fk,
            target_slug,
            edge_type,
            provenance,
            active,
            evidence
        )
        SELECT
            version.skill_fk,
            selector.source_skill_version_fk,
            target.id,
            selector.target_slug,
            selector.edge_type,
            'authored',
            TRUE,
            jsonb_build_object('ordinal', selector.ordinal)
        FROM skill_relationship_selectors AS selector
        JOIN skill_versions AS version
            ON version.id = selector.source_skill_version_fk
        LEFT JOIN skills AS target
            ON target.slug = selector.target_slug
        WHERE selector.edge_type IN ('depends_on', 'extends', 'overlaps_with')
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("uq_skill_graph_edges_co_usage_pair", table_name="skill_graph_edges")
    op.drop_index("uq_skill_graph_edges_authored", table_name="skill_graph_edges")
    op.drop_index("ix_skill_graph_edges_target_skill_fk", table_name="skill_graph_edges")
    op.drop_index("ix_skill_graph_edges_active_source_edge", table_name="skill_graph_edges")
    op.drop_table("skill_graph_edges")
