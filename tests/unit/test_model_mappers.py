"""Regression coverage for SQLAlchemy mapper configuration."""

from __future__ import annotations

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import configure_mappers


def test_persistence_models_configure_mappers() -> None:
    import app.persistence.models  # noqa: F401

    configure_mappers()


def test_skill_version_declares_overall_score_range_constraint() -> None:
    from app.persistence.models.skill_version import SkillVersion

    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in SkillVersion.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert constraints["ck_skill_versions_overall_score"] == (
        "overall_score >= 0 AND overall_score <= 1"
    )
