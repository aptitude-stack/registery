"""Unified SQLAlchemy repository for the skill catalog."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload, sessionmaker

from app.core.governance import LifecycleStatus, TrustTier
from app.core.ports import (
    AuditEventRecord,
    CreateSkillVersionRecord,
    SearchCandidatesRequest,
    SkillCatalogRepository,
    SkillRegistryPersistenceError,
    StoredSkillSearchCandidate,
)
from app.core.skills.models import (
    SkillContentRecord,
    SkillRelationshipSource,
    SkillVersionDetail,
    SkillVersionListEntry,
    SkillVersionStatusUpdate,
)
from app.core.skills.version_ordering import select_current_default_version
from app.persistence.models.audit_event import AuditEvent
from app.persistence.models.skill import Skill
from app.persistence.models.skill_content import SkillContent
from app.persistence.models.skill_metadata import SkillMetadata
from app.persistence.models.skill_relationship_selector import SkillRelationshipSelector
from app.persistence.models.skill_search_document import SkillSearchDocument
from app.persistence.models.skill_version import SkillVersion
from app.persistence.skill_registry_repository_support import (
    SEARCH_CANDIDATES_SQL,
    build_contains_pattern,
    build_search_document,
    classify_integrity_error,
    ensure_datetime,
    ensure_string_list,
    to_skill_content_record,
    to_skill_relationship_source,
    to_skill_version_detail,
    to_skill_version_list_entry,
    to_skill_version_status_update,
)


class SQLAlchemySkillCatalogRepository(SkillCatalogRepository):
    """SQLAlchemy implementation for normalized immutable skill persistence."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def skill_exists(self, *, slug: str) -> bool:
        with self._session_factory() as session:
            statement = select(Skill.id).where(Skill.slug == slug).limit(1)
            return session.execute(statement).scalar_one_or_none() is not None

    def version_exists(self, *, slug: str, version: str) -> bool:
        with self._session_factory() as session:
            statement = (
                select(SkillVersion.id)
                .join(Skill, Skill.id == SkillVersion.skill_fk)
                .where(Skill.slug == slug, SkillVersion.version == version)
                .limit(1)
            )
            return session.execute(statement).scalar_one_or_none() is not None

    def create_version(
        self,
        *,
        record: CreateSkillVersionRecord,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> SkillVersionDetail:
        with self._session_factory() as session:
            try:
                skill = self._get_or_create_skill(session=session, slug=record.slug)
                content = self._get_or_create_content(session=session, record=record)
                metadata = SkillMetadata(
                    name=record.metadata.name,
                    description=record.metadata.description,
                    tags=list(record.metadata.tags),
                    inputs_schema=record.metadata.inputs_schema,
                    outputs_schema=record.metadata.outputs_schema,
                    token_estimate=record.metadata.token_estimate,
                    maturity_score=record.metadata.maturity_score,
                    security_score=record.metadata.security_score,
                )
                session.add(metadata)
                session.flush()

                skill_version = SkillVersion(
                    skill_fk=skill.id,
                    version=record.version,
                    content_fk=content.id,
                    metadata_fk=metadata.id,
                    checksum_digest=record.version_checksum_digest,
                    lifecycle_status="published",
                    lifecycle_changed_at=datetime.now(UTC),
                    trust_tier=record.governance.trust_tier,
                    provenance_repo_url=(
                        None
                        if record.governance.provenance is None
                        else record.governance.provenance.repo_url
                    ),
                    provenance_commit_sha=(
                        None
                        if record.governance.provenance is None
                        else record.governance.provenance.commit_sha
                    ),
                    provenance_tree_path=(
                        None
                        if record.governance.provenance is None
                        else record.governance.provenance.tree_path
                    ),
                    provenance_publisher_identity=(
                        None
                        if record.governance.provenance is None
                        else record.governance.provenance.publisher_identity
                    ),
                    policy_profile_at_publish=(
                        None
                        if record.governance.provenance is None
                        else record.governance.provenance.policy_profile
                    ),
                )
                session.add(skill_version)
                session.flush()
                session.refresh(
                    skill_version,
                    attribute_names=["published_at", "created_at", "lifecycle_changed_at"],
                )

                selector_rows = [
                    SkillRelationshipSelector(
                        source_skill_version_fk=skill_version.id,
                        edge_type=item.edge_type,
                        ordinal=item.ordinal,
                        target_slug=item.slug,
                        target_version=item.version,
                        version_constraint=item.version_constraint,
                        optional=item.optional,
                        markers=list(item.markers),
                    )
                    for item in record.relationships
                ]
                session.add_all(selector_rows)
                session.flush()
                session.add(
                    build_search_document(
                        skill_version_id=skill_version.id,
                        slug=record.slug,
                        version=record.version,
                        metadata=record.metadata,
                        governance=record.governance,
                        published_at=skill_version.published_at,
                        content_size_bytes=record.content.size_bytes,
                    )
                )
                self._add_audit_events(session=session, audit_events=audit_events)
                session.commit()

                reloaded = self._get_version_entity(
                    session=session,
                    slug=record.slug,
                    version=record.version,
                )
                if reloaded is None:
                    raise SkillRegistryPersistenceError(
                        "Created skill version could not be reloaded."
                    )
                return to_skill_version_detail(reloaded)
            except IntegrityError as exc:
                session.rollback()
                raise classify_integrity_error(exc) from exc
            except SQLAlchemyError as exc:
                session.rollback()
                raise SkillRegistryPersistenceError(
                    "Failed to persist immutable skill version."
                ) from exc

    def get_version_detail(self, *, slug: str, version: str) -> SkillVersionDetail | None:
        with self._session_factory() as session:
            entity = self._get_version_entity(session=session, slug=slug, version=version)
            if entity is None:
                return None
            return to_skill_version_detail(entity)

    def get_version_content(
        self,
        *,
        slug: str,
        version: str,
    ) -> SkillContentRecord | None:
        with self._session_factory() as session:
            entity = self._get_version_entity(session=session, slug=slug, version=version)
            if entity is None:
                return None
            return to_skill_content_record(entity)

    def list_versions(self, *, slug: str) -> tuple[SkillVersionListEntry, ...]:
        with self._session_factory() as session:
            statement = (
                select(SkillVersion)
                .join(Skill, Skill.id == SkillVersion.skill_fk)
                .options(joinedload(SkillVersion.skill))
                .where(Skill.slug == slug)
            )
            rows = session.execute(statement).scalars().all()
            return tuple(to_skill_version_list_entry(item) for item in rows)

    def get_relationship_source(
        self,
        *,
        slug: str,
        version: str,
    ) -> SkillRelationshipSource | None:
        with self._session_factory() as session:
            entity = self._get_version_entity(session=session, slug=slug, version=version)
            if entity is None:
                return None
            return to_skill_relationship_source(entity)

    def search_candidates(
        self,
        *,
        request: SearchCandidatesRequest,
    ) -> tuple[StoredSkillSearchCandidate, ...]:
        published_after = None
        if request.fresh_within_days is not None:
            published_after = datetime.now(UTC) - timedelta(days=request.fresh_within_days)

        with self._session_factory() as session:
            rows = session.execute(
                SEARCH_CANDIDATES_SQL,
                {
                    "query_text": request.query_text,
                    "query_contains_pattern": build_contains_pattern(request.query_text),
                    "required_tags": list(request.required_tags),
                    "required_tag_count": len(request.required_tags),
                    "published_after": published_after,
                    "max_content_size_bytes": request.max_content_size_bytes,
                    "lifecycle_statuses": list(request.lifecycle_statuses),
                    "trust_tiers": list(request.trust_tiers),
                    "limit": request.limit,
                },
            ).mappings()
            return tuple(
                StoredSkillSearchCandidate(
                    slug=str(row["slug"]),
                    version=str(row["version"]),
                    name=str(row["name"]),
                    description=str(row["description"]) if row["description"] is not None else None,
                    tags=tuple(ensure_string_list(row["tags"])),
                    lifecycle_status=cast(LifecycleStatus, str(row["lifecycle_status"])),
                    trust_tier=cast(TrustTier, str(row["trust_tier"])),
                    published_at=ensure_datetime(row["published_at"]),
                    content_size_bytes=int(row["content_size_bytes"]),
                    usage_count=int(row["usage_count"]),
                    exact_slug_match=bool(row["exact_slug_match"]),
                    exact_name_match=bool(row["exact_name_match"]),
                    lexical_score=float(row["lexical_score"]),
                    tag_overlap_count=int(row["tag_overlap_count"]),
                )
                for row in rows
            )

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

    def update_version_status(
        self,
        *,
        slug: str,
        version: str,
        lifecycle_status: LifecycleStatus,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> SkillVersionStatusUpdate | None:
        with self._session_factory() as session:
            try:
                entity = self._get_version_entity(session=session, slug=slug, version=version)
                if entity is None:
                    return None

                lifecycle_changed_at = datetime.now(UTC)
                entity.lifecycle_status = lifecycle_status
                entity.lifecycle_changed_at = lifecycle_changed_at
                session.add(entity)
                session.flush()

                search_document = session.get(SkillSearchDocument, entity.id)
                if search_document is not None:
                    search_document.lifecycle_status = lifecycle_status
                    session.add(search_document)

                current_default_version_id = self._select_current_default_version_id(
                    session=session,
                    skill_id=entity.skill_fk,
                )
                self._add_audit_events(session=session, audit_events=audit_events)
                session.flush()
                session.commit()

                return to_skill_version_status_update(
                    entity=entity,
                    lifecycle_changed_at=lifecycle_changed_at,
                    is_current_default=current_default_version_id == entity.id,
                )
            except SQLAlchemyError as exc:
                session.rollback()
                raise SkillRegistryPersistenceError(
                    "Failed to update immutable skill version status."
                ) from exc

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


SQLAlchemySkillRegistryRepository = SQLAlchemySkillCatalogRepository
