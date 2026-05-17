"""Add per-user starred skill relation.

Revision ID: 0008_skill_user_stars
Revises: 0007_skill_star_counts
Create Date: 2026-05-17
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008_skill_user_stars"
down_revision = "0007_skill_star_counts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skill_user_stars",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_subject", sa.Text(), nullable=False),
        sa.Column("skill_fk", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["skill_fk"], ["skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_subject",
            "skill_fk",
            name="uq_skill_user_stars_user_skill",
        ),
    )
    op.create_index(
        "ix_skill_user_stars_user_subject",
        "skill_user_stars",
        ["user_subject"],
        unique=False,
    )
    op.create_index(
        "ix_skill_user_stars_skill_fk",
        "skill_user_stars",
        ["skill_fk"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_skill_user_stars_skill_fk", table_name="skill_user_stars")
    op.drop_index("ix_skill_user_stars_user_subject", table_name="skill_user_stars")
    op.drop_table("skill_user_stars")
