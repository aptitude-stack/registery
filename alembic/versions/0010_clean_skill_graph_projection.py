"""Clean stale skill graph projection rows.

Revision ID: 0010_clean_skill_graph
Revises: 0009_skill_graph_edges
Create Date: 2026-06-04
"""

from __future__ import annotations

from alembic import op

revision = "0010_clean_skill_graph"
down_revision = "0009_skill_graph_edges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE skill_graph_edges AS edge
        SET target_skill_fk = target.id,
            updated_at = CURRENT_TIMESTAMP
        FROM skills AS target
        WHERE edge.target_slug = target.slug
          AND edge.target_skill_fk IS NULL
        """
    )
    op.execute(
        """
        WITH ranked_versions AS (
            SELECT
                version.id,
                version.skill_fk,
                ROW_NUMBER() OVER (
                    PARTITION BY version.skill_fk
                    ORDER BY
                        CASE version.lifecycle_status
                            WHEN 'published' THEN 0
                            WHEN 'deprecated' THEN 1
                            ELSE 2
                        END,
                        version.published_at DESC,
                        version.version ASC
                ) AS skill_rank
            FROM skill_versions AS version
            WHERE version.lifecycle_status IN ('published', 'deprecated')
        ),
        current_defaults AS (
            SELECT id, skill_fk
            FROM ranked_versions
            WHERE skill_rank = 1
        )
        UPDATE skill_graph_edges AS edge
        SET active = FALSE,
            updated_at = CURRENT_TIMESTAMP
        WHERE edge.provenance = 'authored'
          AND edge.active IS TRUE
          AND NOT EXISTS (
              SELECT 1
              FROM current_defaults AS current_default
              WHERE current_default.skill_fk = edge.source_skill_fk
                AND current_default.id = edge.source_skill_version_fk
          )
        """
    )
    op.execute(
        """
        UPDATE skill_graph_edges AS edge
        SET active = FALSE,
            updated_at = CURRENT_TIMESTAMP
        WHERE edge.provenance = 'authored'
          AND edge.active IS TRUE
          AND NOT EXISTS (
              SELECT 1
              FROM skills AS target
              WHERE target.slug = edge.target_slug
          )
        """
    )


def downgrade() -> None:
    pass
