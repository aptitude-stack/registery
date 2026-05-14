"""Allow semantic embedding processing claims.

Revision ID: 0006_embedding_processing_status
Revises: 0005_semantic_discovery_signals
Create Date: 2026-05-09
"""

from __future__ import annotations

from alembic import op

revision = "0006_embedding_processing_status"
down_revision = "0005_semantic_discovery_signals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE skill_search_embeddings
        DROP CONSTRAINT ck_skill_search_embeddings_index_status
        """
    )
    op.execute(
        """
        ALTER TABLE skill_search_embeddings
        ADD CONSTRAINT ck_skill_search_embeddings_index_status
        CHECK (index_status IN ('pending', 'processing', 'indexed', 'failed', 'stale'))
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE skill_search_embeddings
        SET index_status = 'stale',
            updated_at = CURRENT_TIMESTAMP
        WHERE index_status = 'processing'
        """
    )
    op.execute(
        """
        ALTER TABLE skill_search_embeddings
        DROP CONSTRAINT ck_skill_search_embeddings_index_status
        """
    )
    op.execute(
        """
        ALTER TABLE skill_search_embeddings
        ADD CONSTRAINT ck_skill_search_embeddings_index_status
        CHECK (index_status IN ('pending', 'indexed', 'failed', 'stale'))
        """
    )
