"""Derived read model backing advisory search retrieval."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.models.base import Base


class SkillSearchDocument(Base):
    """Denormalized search document keyed by immutable skill version."""

    __tablename__ = "skill_search_documents"
    __table_args__ = (
        CheckConstraint("content_size_bytes >= 0", name="ck_skill_search_documents_content_size"),
        CheckConstraint(
            "lifecycle_status IN ('published', 'deprecated', 'archived')",
            name="ck_skill_search_documents_lifecycle_status",
        ),
        CheckConstraint(
            "trust_tier IN ('untrusted', 'internal', 'verified')",
            name="ck_skill_search_documents_trust_tier",
        ),
        CheckConstraint(
            "artifact_origin IN ('internal', 'imported', 'verified', 'restricted')",
            name="ck_skill_search_documents_artifact_origin",
        ),
        CheckConstraint(
            "review_state IN ('pending_review', 'approved', 'rejected')",
            name="ck_skill_search_documents_review_state",
        ),
        CheckConstraint(
            "promotion_channel IN ('dev', 'staging', 'prod')",
            name="ck_skill_search_documents_promotion_channel",
        ),
        Index("ix_skill_search_documents_normalized_slug", "normalized_slug"),
        Index("ix_skill_search_documents_normalized_name", "normalized_name"),
        Index("ix_skill_search_documents_published_at", "published_at"),
        Index("ix_skill_search_documents_content_size_bytes", "content_size_bytes"),
        Index("ix_skill_search_documents_lifecycle_status", "lifecycle_status"),
        Index("ix_skill_search_documents_trust_tier", "trust_tier"),
        Index("ix_skill_search_documents_namespace", "namespace"),
        Index("ix_skill_search_documents_review_state", "review_state"),
        Index("ix_skill_search_documents_promotion_channel", "promotion_channel"),
        Index(
            "ix_skill_search_documents_normalized_tags_gin",
            "normalized_tags",
            postgresql_using="gin",
        ),
        Index(
            "ix_skill_search_documents_search_vector_gin",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    skill_version_fk: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("skill_versions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_slug: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    normalized_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    lifecycle_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'published'"),
    )
    trust_tier: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'untrusted'"),
    )
    namespace: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'public'"),
    )
    artifact_origin: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'internal'"),
    )
    review_state: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'approved'"),
    )
    promotion_channel: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'prod'"),
    )
    policy_pack_slug: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        nullable=False,
        server_default=text("''::tsvector"),
    )
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
