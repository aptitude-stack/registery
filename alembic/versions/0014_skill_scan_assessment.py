"""Store sanitized publisher assessment summaries on immutable versions."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0014_skill_scan_assessment"
down_revision = "0013_db_structure_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "skill_versions",
        sa.Column(
            "assessment",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("skill_versions", "assessment")
