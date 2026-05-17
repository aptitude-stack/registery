"""Persisted per-user starred skill relation."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.models.base import Base


class SkillUserStar(Base):
    """One user's saved/starred state for one skill identity."""

    __tablename__ = "skill_user_stars"
    __table_args__ = (
        UniqueConstraint("user_subject", "skill_fk", name="uq_skill_user_stars_user_skill"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_subject: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    skill_fk: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
