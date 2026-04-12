"""Add mutable aggregate install counts for skill identities.

Revision ID: 0002_skill_install_counts
Revises: 0001_initial_schema
Create Date: 2026-03-26
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_skill_install_counts"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "skills",
        sa.Column(
            "install_count",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.drop_column("skill_metadata", "headers")


def downgrade() -> None:
    op.add_column(
        "skill_metadata",
        sa.Column("headers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.drop_column("skills", "install_count")
