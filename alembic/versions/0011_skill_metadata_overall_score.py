"""Add nullable normalized overall scores to skill metadata."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0011_overall_score"
down_revision = "0010_clean_skill_graph"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "skill_metadata",
        sa.Column("overall_score", sa.Float(), nullable=True),
    )
    op.create_check_constraint(
        "ck_skill_metadata_overall_score_range",
        "skill_metadata",
        "overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 1)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_skill_metadata_overall_score_range",
        "skill_metadata",
        type_="check",
    )
    op.drop_column("skill_metadata", "overall_score")
