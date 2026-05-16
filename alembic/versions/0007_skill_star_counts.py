"""Add aggregate star counts for skill identities.

Revision ID: 0007_skill_star_counts
Revises: 0006_embedding_processing_status
Create Date: 2026-05-16
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007_skill_star_counts"
down_revision = "0006_embedding_processing_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "skills",
        sa.Column(
            "star_count",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("skills", "star_count")
