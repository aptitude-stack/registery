"""Add enterprise governance namespaces and promotion workflow state.

Revision ID: 0004_enterprise_governance
Revises: 0003_skill_bundle_storage
Create Date: 2026-04-25
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004_enterprise_governance"
down_revision = "0003_skill_bundle_storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_table(
        "namespaces",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("organization_fk", sa.BigInteger(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("visibility", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("visibility IN ('public', 'private')", name="ck_namespaces_visibility"),
        sa.ForeignKeyConstraint(["organization_fk"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("slug", name="uq_namespaces_slug"),
    )
    op.create_index("ix_namespaces_organization_fk", "namespaces", ["organization_fk"])

    op.create_table(
        "policy_packs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("slug", name="uq_policy_packs_slug"),
    )

    op.execute(
        """
        INSERT INTO organizations (slug, display_name)
        VALUES ('public', 'Public Catalog')
        ON CONFLICT (slug) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO namespaces (organization_fk, slug, visibility)
        SELECT id, 'public', 'public'
        FROM organizations
        WHERE slug = 'public'
        ON CONFLICT (slug) DO NOTHING
        """
    )

    op.add_column("skills", sa.Column("namespace_fk", sa.BigInteger(), nullable=True))
    op.execute(
        """
        UPDATE skills
        SET namespace_fk = (SELECT id FROM namespaces WHERE slug = 'public')
        WHERE namespace_fk IS NULL
        """
    )
    op.alter_column("skills", "namespace_fk", nullable=False)
    op.create_index("ix_skills_namespace_fk", "skills", ["namespace_fk"])
    op.create_foreign_key(
        "fk_skills_namespace_fk_namespaces",
        "skills",
        "namespaces",
        ["namespace_fk"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.add_column(
        "skill_versions",
        sa.Column(
            "artifact_origin",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'internal'"),
        ),
    )
    op.add_column(
        "skill_versions",
        sa.Column(
            "review_state",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'approved'"),
        ),
    )
    op.add_column(
        "skill_versions",
        sa.Column(
            "promotion_channel",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'prod'"),
        ),
    )
    op.add_column("skill_versions", sa.Column("policy_pack_fk", sa.BigInteger(), nullable=True))
    op.create_check_constraint(
        "ck_skill_versions_artifact_origin",
        "skill_versions",
        "artifact_origin IN ('internal', 'imported', 'verified', 'restricted')",
    )
    op.create_check_constraint(
        "ck_skill_versions_review_state",
        "skill_versions",
        "review_state IN ('pending_review', 'approved', 'rejected')",
    )
    op.create_check_constraint(
        "ck_skill_versions_promotion_channel",
        "skill_versions",
        "promotion_channel IN ('dev', 'staging', 'prod')",
    )
    op.create_index("ix_skill_versions_policy_pack_fk", "skill_versions", ["policy_pack_fk"])
    op.create_foreign_key(
        "fk_skill_versions_policy_pack_fk_policy_packs",
        "skill_versions",
        "policy_packs",
        ["policy_pack_fk"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "skill_search_documents",
        sa.Column("namespace", sa.Text(), nullable=False, server_default=sa.text("'public'")),
    )
    op.add_column(
        "skill_search_documents",
        sa.Column(
            "artifact_origin",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'internal'"),
        ),
    )
    op.add_column(
        "skill_search_documents",
        sa.Column(
            "review_state",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'approved'"),
        ),
    )
    op.add_column(
        "skill_search_documents",
        sa.Column(
            "promotion_channel",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'prod'"),
        ),
    )
    op.add_column("skill_search_documents", sa.Column("policy_pack_slug", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_skill_search_documents_artifact_origin",
        "skill_search_documents",
        "artifact_origin IN ('internal', 'imported', 'verified', 'restricted')",
    )
    op.create_check_constraint(
        "ck_skill_search_documents_review_state",
        "skill_search_documents",
        "review_state IN ('pending_review', 'approved', 'rejected')",
    )
    op.create_check_constraint(
        "ck_skill_search_documents_promotion_channel",
        "skill_search_documents",
        "promotion_channel IN ('dev', 'staging', 'prod')",
    )
    op.create_index("ix_skill_search_documents_namespace", "skill_search_documents", ["namespace"])
    op.create_index(
        "ix_skill_search_documents_review_state",
        "skill_search_documents",
        ["review_state"],
    )
    op.create_index(
        "ix_skill_search_documents_promotion_channel",
        "skill_search_documents",
        ["promotion_channel"],
    )

    op.create_table(
        "trust_evidence",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("skill_version_fk", sa.BigInteger(), nullable=False),
        sa.Column("evidence_type", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("digest", sa.Text(), nullable=True),
        sa.Column("uri", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["skill_version_fk"],
            ["skill_versions.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_trust_evidence_skill_version_fk", "trust_evidence", ["skill_version_fk"])


def downgrade() -> None:
    op.drop_index("ix_trust_evidence_skill_version_fk", table_name="trust_evidence")
    op.drop_table("trust_evidence")

    op.drop_index(
        "ix_skill_search_documents_promotion_channel", table_name="skill_search_documents"
    )
    op.drop_index("ix_skill_search_documents_review_state", table_name="skill_search_documents")
    op.drop_index("ix_skill_search_documents_namespace", table_name="skill_search_documents")
    op.drop_constraint(
        "ck_skill_search_documents_promotion_channel",
        "skill_search_documents",
        type_="check",
    )
    op.drop_constraint(
        "ck_skill_search_documents_review_state", "skill_search_documents", type_="check"
    )
    op.drop_constraint(
        "ck_skill_search_documents_artifact_origin",
        "skill_search_documents",
        type_="check",
    )
    op.drop_column("skill_search_documents", "policy_pack_slug")
    op.drop_column("skill_search_documents", "promotion_channel")
    op.drop_column("skill_search_documents", "review_state")
    op.drop_column("skill_search_documents", "artifact_origin")
    op.drop_column("skill_search_documents", "namespace")

    op.drop_constraint(
        "fk_skill_versions_policy_pack_fk_policy_packs",
        "skill_versions",
        type_="foreignkey",
    )
    op.drop_index("ix_skill_versions_policy_pack_fk", table_name="skill_versions")
    op.drop_constraint("ck_skill_versions_promotion_channel", "skill_versions", type_="check")
    op.drop_constraint("ck_skill_versions_review_state", "skill_versions", type_="check")
    op.drop_constraint("ck_skill_versions_artifact_origin", "skill_versions", type_="check")
    op.drop_column("skill_versions", "policy_pack_fk")
    op.drop_column("skill_versions", "promotion_channel")
    op.drop_column("skill_versions", "review_state")
    op.drop_column("skill_versions", "artifact_origin")

    op.drop_constraint("fk_skills_namespace_fk_namespaces", "skills", type_="foreignkey")
    op.drop_index("ix_skills_namespace_fk", table_name="skills")
    op.drop_column("skills", "namespace_fk")

    op.drop_table("policy_packs")
    op.drop_index("ix_namespaces_organization_fk", table_name="namespaces")
    op.drop_table("namespaces")
    op.drop_table("organizations")
