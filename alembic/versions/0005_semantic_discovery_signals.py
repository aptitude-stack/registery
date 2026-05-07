"""Add semantic discovery embeddings and co-usage signals.

Revision ID: 0005_semantic_discovery_signals
Revises: 0004_enterprise_governance
Create Date: 2026-05-07
"""

from __future__ import annotations

from alembic import op

revision = "0005_semantic_discovery_signals"
down_revision = "0004_enterprise_governance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE skill_search_embeddings (
            skill_version_fk BIGINT NOT NULL
                REFERENCES skill_versions(id) ON DELETE CASCADE,
            embedding_model TEXT NOT NULL,
            embedding_dimensions INTEGER NOT NULL,
            source_checksum_digest TEXT NOT NULL,
            embedding_vector halfvec(1536),
            index_status TEXT NOT NULL DEFAULT 'pending',
            indexed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_error TEXT,
            CONSTRAINT pk_skill_search_embeddings
                PRIMARY KEY (skill_version_fk, embedding_model),
            CONSTRAINT ck_skill_search_embeddings_dimensions
                CHECK (embedding_dimensions = 1536),
            CONSTRAINT ck_skill_search_embeddings_source_digest
                CHECK (source_checksum_digest ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_skill_search_embeddings_index_status
                CHECK (index_status IN ('pending', 'indexed', 'failed', 'stale'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_skill_search_embeddings_model_status
        ON skill_search_embeddings (embedding_model, index_status)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_skill_search_embeddings_source_checksum
        ON skill_search_embeddings (source_checksum_digest)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_skill_search_embeddings_vector_hnsw
        ON skill_search_embeddings
        USING hnsw (embedding_vector halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        WHERE embedding_vector IS NOT NULL AND index_status = 'indexed'
        """
    )
    op.execute(
        """
        CREATE TABLE skill_usage_observation_runs (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            source TEXT NOT NULL,
            source_digest TEXT NOT NULL,
            observed_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_skill_usage_observation_runs_source_digest
                UNIQUE (source, source_digest),
            CONSTRAINT ck_skill_usage_observation_runs_source_digest
                CHECK (source_digest ~ '^[0-9a-f]{64}$')
        )
        """
    )
    op.execute(
        """
        CREATE TABLE skill_usage_observations (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            run_fk BIGINT NOT NULL
                REFERENCES skill_usage_observation_runs(id) ON DELETE CASCADE,
            skill_fk BIGINT NOT NULL
                REFERENCES skills(id) ON DELETE CASCADE,
            skill_slug TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_skill_usage_observations_run_skill
                UNIQUE (run_fk, skill_fk)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_skill_usage_observations_skill_fk
        ON skill_usage_observations (skill_fk)
        """
    )
    op.execute(
        """
        CREATE TABLE skill_co_usage_pairs (
            anchor_skill_fk BIGINT NOT NULL
                REFERENCES skills(id) ON DELETE CASCADE,
            related_skill_fk BIGINT NOT NULL
                REFERENCES skills(id) ON DELETE CASCADE,
            observation_count BIGINT NOT NULL DEFAULT 0,
            distinct_run_count BIGINT NOT NULL DEFAULT 0,
            co_usage_rate NUMERIC(10, 6) NOT NULL DEFAULT 0,
            lift_score NUMERIC(10, 6) NOT NULL DEFAULT 0,
            pmi_score NUMERIC(10, 6) NOT NULL DEFAULT 0,
            last_observed_at TIMESTAMPTZ,
            window_days INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT pk_skill_co_usage_pairs
                PRIMARY KEY (anchor_skill_fk, related_skill_fk),
            CONSTRAINT ck_skill_co_usage_pairs_distinct_skills
                CHECK (anchor_skill_fk <> related_skill_fk),
            CONSTRAINT ck_skill_co_usage_pairs_counts_non_negative
                CHECK (observation_count >= 0 AND distinct_run_count >= 0),
            CONSTRAINT ck_skill_co_usage_pairs_window_positive
                CHECK (window_days > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_skill_co_usage_pairs_related_skill_fk
        ON skill_co_usage_pairs (related_skill_fk)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_skill_co_usage_pairs_related_skill_fk")
    op.execute("DROP TABLE IF EXISTS skill_co_usage_pairs")
    op.execute("DROP INDEX IF EXISTS ix_skill_usage_observations_skill_fk")
    op.execute("DROP TABLE IF EXISTS skill_usage_observations")
    op.execute("DROP TABLE IF EXISTS skill_usage_observation_runs")
    op.execute("DROP INDEX IF EXISTS ix_skill_search_embeddings_vector_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_skill_search_embeddings_source_checksum")
    op.execute("DROP INDEX IF EXISTS ix_skill_search_embeddings_model_status")
    op.execute("DROP TABLE IF EXISTS skill_search_embeddings")
