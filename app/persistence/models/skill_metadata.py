"""Structured metadata storage model."""

from __future__ import annotations

from sqlalchemy import BigInteger, CheckConstraint, Float, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.models.base import Base


class SkillMetadata(Base):
    """Stores queryable metadata separately from bundle content."""

    __tablename__ = "skill_metadata"
    __table_args__ = (
        CheckConstraint(
            "overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 1)",
            name="ck_skill_metadata_overall_score_range",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
        default=list,
    )
    token_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    maturity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    security_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
