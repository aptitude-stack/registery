"""Normalized immutable skill version model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.models.base import Base

if TYPE_CHECKING:
    from app.persistence.models.policy_pack import PolicyPack
    from app.persistence.models.skill import Skill
    from app.persistence.models.skill_content import SkillContent
    from app.persistence.models.skill_relationship_selector import SkillRelationshipSelector


class SkillVersion(Base):
    """Represents one immutable published version bound to normalized content and metadata."""

    __tablename__ = "skill_versions"
    __table_args__ = (
        CheckConstraint(
            "lifecycle_status IN ('published', 'deprecated', 'archived')",
            name="ck_skill_versions_lifecycle_status",
        ),
        CheckConstraint(
            "trust_tier IN ('untrusted', 'internal', 'verified')",
            name="ck_skill_versions_trust_tier",
        ),
        CheckConstraint(
            "artifact_origin IN ('internal', 'imported', 'verified', 'restricted')",
            name="ck_skill_versions_artifact_origin",
        ),
        CheckConstraint(
            "review_state IN ('pending_review', 'approved', 'rejected')",
            name="ck_skill_versions_review_state",
        ),
        CheckConstraint(
            "promotion_channel IN ('dev', 'staging', 'prod')",
            name="ck_skill_versions_promotion_channel",
        ),
        UniqueConstraint("skill_fk", "version", name="uq_skill_versions_skill_fk_version"),
        Index(
            "ix_skill_versions_skill_fk_published_at_id",
            "skill_fk",
            "published_at",
            "id",
        ),
        UniqueConstraint("id", "skill_fk", name="uq_skill_versions_id_skill_fk"),
        CheckConstraint("token_estimate >= 0", name="ck_skill_versions_token_estimate"),
        CheckConstraint(
            "maturity_score >= 0 AND maturity_score <= 1", name="ck_skill_versions_maturity_score"
        ),
        CheckConstraint(
            "security_score >= 0 AND security_score <= 1", name="ck_skill_versions_security_score"
        ),
        CheckConstraint(
            "overall_score >= 0 AND overall_score <= 1", name="ck_skill_versions_overall_score"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    skill_fk: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(Text, nullable=False)
    content_fk: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("skill_contents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]"), default=list
    )
    token_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    maturity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    security_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    assessment: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    checksum_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'published'"),
    )
    lifecycle_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    trust_tier: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'untrusted'"),
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
    policy_pack_fk: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("policy_packs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provenance_repo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance_commit_sha: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance_tree_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance_publisher_identity: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_profile_at_publish: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    skill: Mapped[Skill] = relationship(
        back_populates="versions",
        foreign_keys=[skill_fk],
    )
    content: Mapped[SkillContent] = relationship()
    policy_pack: Mapped[PolicyPack | None] = relationship(back_populates="versions")
    relationship_selectors: Mapped[list[SkillRelationshipSelector]] = relationship(
        cascade="all, delete-orphan",
        order_by="SkillRelationshipSelector.ordinal",
        back_populates="skill_version",
    )
