"""Immutable skill bundle storage model."""

from __future__ import annotations

from sqlalchemy import BigInteger, CheckConstraint, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.models.base import Base


class SkillContent(Base):
    """Stores canonical bundle blobs in PostgreSQL."""

    __tablename__ = "skill_contents"
    __table_args__ = (
        CheckConstraint(
            "storage_size_bytes = octet_length(payload)", name="ck_skill_contents_storage_size"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    payload: Mapped[bytes] = mapped_column(
        LargeBinary, nullable=False, deferred=True, deferred_raiseload=True
    )
    media_type: Mapped[str] = mapped_column(Text, nullable=False)
    storage_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
