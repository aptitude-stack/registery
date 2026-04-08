"""Read-side SQLAlchemy mixin for exact version and relationship reads."""

from __future__ import annotations

from typing import cast

from sqlalchemy import select, tuple_, update
from sqlalchemy.orm import joinedload, selectinload

from app.core.governance import LifecycleStatus, TrustTier
from app.core.ports import (
    ExactSkillCoordinate,
    StoredSkillRelationshipSource,
    StoredSkillVersion,
    StoredSkillVersionContent,
    StoredSkillVersionSummary,
)
from app.persistence.models.skill import Skill
from app.persistence.models.skill_search_document import SkillSearchDocument
from app.persistence.models.skill_version import SkillVersion
from app.persistence.skill_registry_repository_base import SkillRegistryRepositoryBase
from app.persistence.skill_registry_repository_support import (
    sort_relationship_selectors,
    to_stored_selector,
    to_stored_skill_version,
)


class SkillRegistryReadMixin(SkillRegistryRepositoryBase):
    """Read-side methods for exact version and relationship retrieval."""

    def record_install(self, *, slug: str, version: str) -> None:
        with self._session_factory() as session:
            skill_row = session.execute(
                update(Skill)
                .where(
                    Skill.id
                    == select(SkillVersion.skill_fk)
                    .join(Skill, Skill.id == SkillVersion.skill_fk)
                    .where(Skill.slug == slug, SkillVersion.version == version)
                    .scalar_subquery()
                )
                .values(install_count=Skill.install_count + 1)
                .returning(Skill.id, Skill.install_count)
            ).one_or_none()
            if skill_row is None:
                session.rollback()
                return

            skill_id, install_count = skill_row
            session.execute(
                update(SkillSearchDocument)
                .where(
                    SkillSearchDocument.skill_version_fk.in_(
                        select(SkillVersion.id).where(SkillVersion.skill_fk == skill_id)
                    )
                )
                .values(usage_count=install_count)
            )
            session.commit()

    def get_version(self, *, slug: str, version: str) -> StoredSkillVersion | None:
        with self._session_factory() as session:
            entity = self._get_version_entity(session=session, slug=slug, version=version)
            if entity is None:
                return None
            return to_stored_skill_version(entity)

    def get_version_content(
        self,
        *,
        slug: str,
        version: str,
    ) -> StoredSkillVersionContent | None:
        with self._session_factory() as session:
            statement = (
                select(SkillVersion)
                .join(Skill, Skill.id == SkillVersion.skill_fk)
                .options(
                    joinedload(SkillVersion.skill),
                    joinedload(SkillVersion.content),
                )
                .where(Skill.slug == slug, SkillVersion.version == version)
            )
            item = session.execute(statement).scalar_one_or_none()
            if item is None:
                return None
            return StoredSkillVersionContent(
                slug=item.skill.slug,
                version=item.version,
                raw_markdown=item.content.raw_markdown,
                checksum_digest=item.content.checksum_digest,
                size_bytes=item.content.storage_size_bytes,
                lifecycle_status=cast(LifecycleStatus, item.lifecycle_status),
                trust_tier=cast(TrustTier, item.trust_tier),
            )

    def list_versions(self, *, slug: str) -> tuple[StoredSkillVersionSummary, ...]:
        with self._session_factory() as session:
            statement = (
                select(SkillVersion)
                .join(Skill, Skill.id == SkillVersion.skill_fk)
                .options(joinedload(SkillVersion.skill))
                .where(Skill.slug == slug)
            )
            rows = session.execute(statement).scalars().all()
            return tuple(
                StoredSkillVersionSummary(
                    slug=item.skill.slug,
                    version=item.version,
                    lifecycle_status=cast(LifecycleStatus, item.lifecycle_status),
                    trust_tier=cast(TrustTier, item.trust_tier),
                    published_at=item.published_at,
                )
                for item in rows
            )

    def get_relationship_sources_batch(
        self,
        *,
        coordinates: tuple[ExactSkillCoordinate, ...],
    ) -> tuple[StoredSkillRelationshipSource, ...]:
        if not coordinates:
            return ()

        coordinate_pairs = [(item.slug, item.version) for item in coordinates]
        with self._session_factory() as session:
            statement = (
                select(SkillVersion)
                .join(Skill, Skill.id == SkillVersion.skill_fk)
                .options(
                    joinedload(SkillVersion.skill),
                    selectinload(SkillVersion.relationship_selectors),
                )
                .where(tuple_(Skill.slug, SkillVersion.version).in_(coordinate_pairs))
            )
            rows = session.execute(statement).scalars().all()
            return tuple(
                StoredSkillRelationshipSource(
                    slug=item.skill.slug,
                    version=item.version,
                    lifecycle_status=cast(LifecycleStatus, item.lifecycle_status),
                    trust_tier=cast(TrustTier, item.trust_tier),
                    relationships=tuple(
                        to_stored_selector(selector)
                        for selector in sort_relationship_selectors(item.relationship_selectors)
                    ),
                )
                for item in rows
            )
