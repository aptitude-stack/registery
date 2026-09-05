"""Remove retired input and output schema columns from metadata rows."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0012_remove_metadata_schemas"
down_revision = "0011_overall_score"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("skill_metadata", "inputs_schema")
    op.drop_column("skill_metadata", "outputs_schema")


def downgrade() -> None:
    op.add_column(
        "skill_metadata",
        sa.Column("inputs_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "skill_metadata",
        sa.Column("outputs_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
