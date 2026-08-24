"""Regression coverage for SQLAlchemy mapper configuration."""

from __future__ import annotations

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import configure_mappers


def test_persistence_models_configure_mappers() -> None:
    import app.persistence.models  # noqa: F401

    configure_mappers()


def test_skill_metadata_declares_overall_score_range_constraint() -> None:
    from app.persistence.models.skill_metadata import SkillMetadata

    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in SkillMetadata.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert constraints["ck_skill_metadata_overall_score_range"] == (
        "overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 1)"
    )
