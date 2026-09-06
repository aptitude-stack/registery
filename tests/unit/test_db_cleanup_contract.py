"""Small executable contracts for the consolidated persistence model."""

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import aliased, configure_mappers

from app.core.settings import Settings
from app.interface.dto.skills_telemetry import StarEventBatchRequest
from app.persistence.models import Skill, SkillContent, SkillSearchDocument, SkillVersion


def test_versions_own_metadata_and_counters_have_one_source() -> None:
    configure_mappers()
    assert "metadata_fk" not in SkillVersion.__table__.c
    assert {
        "name",
        "description",
        "tags",
        "token_estimate",
        "maturity_score",
        "security_score",
        "overall_score",
    } <= set(SkillVersion.__table__.c.keys())
    assert "star_count" not in Skill.__table__.c
    assert "usage_count" not in SkillSearchDocument.__table__.c
    skill = aliased(Skill)
    sql = str(select(skill.slug, skill.star_count).compile(dialect=postgresql.dialect()))
    assert "count(" in sql
    assert "skill_user_stars" in sql


def test_content_payload_requires_explicit_loading() -> None:
    assert SkillContent.payload.property.deferred
    assert SkillContent.payload.property.raiseload


@pytest.mark.parametrize("subject", [None, "", "   "])
def test_star_events_require_a_user(subject: str | None) -> None:
    with pytest.raises(ValidationError):
        StarEventBatchRequest.model_validate(
            {
                "events": [{"slug": "test", "action": "star"}],
                "user_subject": subject,
            }
        )


def test_embedding_dimensions_match_physical_storage() -> None:
    with pytest.raises(ValidationError) as error:
        Settings(
            _env_file=None,
            DATABASE_URL="postgresql+psycopg://localhost/test",
            semantic_embedding_dimensions=768,
        )
    assert error.value.errors()[0]["loc"] == ("semantic_embedding_dimensions",)
