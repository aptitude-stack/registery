"""Unified graph edge projection for authored and derived skill relations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.models.base import Base


class SkillGraphEdge(Base):
    """Queryable graph edge projection with provenance."""

    __tablename__ = "skill_graph_edges"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_skill_version_fk", "source_skill_fk"],
            ["skill_versions.id", "skill_versions.skill_fk"],
            name="fk_skill_graph_edges_source_version",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_skill_fk", "target_slug"],
            ["skills.id", "skills.slug"],
            name="fk_skill_graph_edges_target",
            ondelete="CASCADE",
        ),
        Index(
            "uq_skill_graph_edges_authored",
            "source_skill_version_fk",
            "target_slug",
            "edge_type",
            "provenance",
            unique=True,
            postgresql_where=text("provenance = 'authored'"),
        ),
        Index(
            "uq_skill_graph_edges_co_usage_pair",
            "source_skill_fk",
            "target_skill_fk",
            "edge_type",
            "provenance",
            unique=True,
            postgresql_where=text("provenance = 'co_usage'"),
        ),
        CheckConstraint(
            "edge_type IN ('depends_on', 'extends', 'overlaps_with', 'relates_to')",
            name="ck_skill_graph_edges_edge_type",
        ),
        CheckConstraint(
            "provenance IN ('authored', 'co_usage')",
            name="ck_skill_graph_edges_provenance",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_skill_graph_edges_confidence_range",
        ),
        CheckConstraint(
            """
            (provenance = 'authored' AND source_skill_version_fk IS NOT NULL
                AND edge_type IN ('depends_on', 'extends', 'overlaps_with'))
            OR (
                provenance = 'co_usage'
                AND source_skill_version_fk IS NULL
                AND edge_type = 'relates_to'
                AND target_skill_fk IS NOT NULL
                AND source_skill_fk < target_skill_fk
            )
            """,
            name="ck_skill_graph_edges_provenance_shape",
        ),
        Index(
            "ix_skill_graph_edges_active_source_edge",
            "active",
            "source_skill_fk",
            "edge_type",
        ),
        Index("ix_skill_graph_edges_target_skill_fk", "target_skill_fk"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_skill_fk: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_skill_version_fk: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    target_skill_fk: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    target_slug: Mapped[str] = mapped_column(Text, nullable=False)
    edge_type: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("TRUE"),
    )
    confidence: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
