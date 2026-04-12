"""Shared session and helper logic for SQLAlchemy skill repository adapters."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload, sessionmaker

from app.core.ports import AuditEventRecord, CreateSkillVersionRecord
from app.core.skills.version_ordering import select_current_default_version
from app.persistence.models.audit_event import AuditEvent
from app.persistence.models.skill import Skill
from app.persistence.models.skill_content import SkillContent
from app.persistence.models.skill_version import SkillVersion


class SkillRegistryRepositoryBase:
    """Shared SQLAlchemy session helpers for skill repository mixins."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _add_audit_events(
        *,
        session: Session,
        audit_events: tuple[AuditEventRecord, ...],
    ) -> None:
        if not audit_events:
            return
        session.add_all(
            AuditEvent(event_type=event.event_type, payload=event.payload) for event in audit_events
        )

    @staticmethod
    def _get_or_create_skill(*, session: Session, slug: str) -> Skill:
        existing = session.execute(select(Skill).where(Skill.slug == slug)).scalar_one_or_none()
        if existing is not None:
            return existing

        created = Skill(slug=slug)
        session.add(created)
        session.flush()
        return created

    @staticmethod
    def _get_or_create_content(
        *,
        session: Session,
        record: CreateSkillVersionRecord,
    ) -> SkillContent:
        existing = session.execute(
            select(SkillContent).where(
                SkillContent.checksum_digest == record.content.checksum_digest
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        created = SkillContent(
            payload=record.content.payload,
            media_type=record.content.media_type,
            storage_size_bytes=record.content.size_bytes,
            checksum_digest=record.content.checksum_digest,
        )
        session.add(created)
        session.flush()
        return created

    @staticmethod
    def _select_current_default_version_id(*, session: Session, skill_id: int) -> int | None:
        rows = session.execute(
            select(SkillVersion).where(SkillVersion.skill_fk == skill_id)
        ).scalars()
        current_default = select_current_default_version(rows)
        if current_default is None:
            return None
        return current_default.id

    @staticmethod
    def _get_version_entity(
        *,
        session: Session,
        slug: str,
        version: str,
    ) -> SkillVersion | None:
        statement = (
            select(SkillVersion)
            .join(Skill, Skill.id == SkillVersion.skill_fk)
            .options(
                joinedload(SkillVersion.skill),
                joinedload(SkillVersion.content),
                joinedload(SkillVersion.metadata_row),
                selectinload(SkillVersion.relationship_selectors),
            )
            .where(Skill.slug == slug, SkillVersion.version == version)
        )
        return session.execute(statement).scalar_one_or_none()
