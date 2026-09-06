"""Authored relationship selectors preserved exactly as published."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.models.base import Base


class SkillRelationshipSelector(Base):
    """Stores one authored relationship selector in publish order."""

    __tablename__ = "skill_relationship_selectors"
    __table_args__ = (
        CheckConstraint(
            "edge_type IN ('depends_on', 'extends', 'conflicts_with', 'overlaps_with')",
            name="ck_skill_relationship_selectors_edge_type",
        ),
        UniqueConstraint(
            "source_skill_version_fk",
            "edge_type",
            "ordinal",
            name="uq_skill_relationship_selectors_position",
        ),
        CheckConstraint("ordinal >= 0", name="ck_skill_relationship_selectors_ordinal"),
        CheckConstraint(
            """(edge_type = 'depends_on'
                AND ((target_version IS NOT NULL) <> (version_constraint IS NOT NULL)))
            OR (edge_type <> 'depends_on' AND target_version IS NOT NULL
                AND version_constraint IS NULL AND optional IS NULL AND cardinality(markers) = 0)
            """,
            name="ck_skill_relationship_selectors_shape",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_skill_version_fk: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("skill_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    edge_type: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    target_slug: Mapped[str] = mapped_column(Text, nullable=False)
    target_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_constraint: Mapped[str | None] = mapped_column(Text, nullable=True)
    optional: Mapped[bool | None] = mapped_column(nullable=True)
    markers: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    skill_version = relationship("SkillVersion", back_populates="relationship_selectors")
