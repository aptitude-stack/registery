"""Unified SQLAlchemy repository for the skill catalog."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    Text,
    bindparam,
    delete,
    func,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload, sessionmaker

from app.core.governance import (
    ArtifactOrigin,
    LifecycleStatus,
    PromotionChannel,
    ReviewState,
    TrustTier,
)
from app.core.governance import (
    PolicyPack as DomainPolicyPack,
)
from app.core.ports import (
    AuditEventRecord,
    CoUsageBoostRequest,
    CoUsageObservationImportRecord,
    CreateSkillVersionRecord,
    MetadataRecordInput,
    SearchCandidatesRequest,
    SearchSemanticCandidatesRequest,
    SkillCatalogRepository,
    SkillEmbeddingIndexRecord,
    SkillEmbeddingWorkItem,
    SkillRegistryPersistenceError,
    StoredSkillSearchCandidate,
)
from app.core.semantic_defaults import (
    DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS,
    DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
)
from app.core.skills.models import (
    CoUsageObservationImportResult,
    CoUsageRelatesToPolicy,
    NamespaceRecord,
    OrganizationRecord,
    PolicyPackRecord,
    SkillContentRecord,
    SkillGraphEdge,
    SkillGraphEdgeProvenance,
    SkillGraphEdgeType,
    SkillOwnershipUpdate,
    SkillRelationshipSource,
    SkillStarCount,
    SkillVersionDetail,
    SkillVersionGovernanceUpdate,
    SkillVersionListEntry,
    SkillVersionStatusUpdate,
    StarEvent,
    TrustEvidenceRecord,
    UnknownCoUsageSkillError,
    UnknownStarEventSkillsError,
)
from app.core.skills.version_ordering import select_current_default_version
from app.intelligence.discovery_signals import (
    build_embedding_source,
    build_source_checksum_digest,
    serialize_embedding_vector,
    validate_embedding_vector,
)
from app.persistence.models.audit_event import AuditEvent
from app.persistence.models.namespace import Namespace
from app.persistence.models.organization import Organization
from app.persistence.models.policy_pack import PolicyPack
from app.persistence.models.skill import Skill
from app.persistence.models.skill_content import SkillContent
from app.persistence.models.skill_graph_edge import SkillGraphEdge as SkillGraphEdgeModel
from app.persistence.models.skill_metadata import SkillMetadata
from app.persistence.models.skill_relationship_selector import SkillRelationshipSelector
from app.persistence.models.skill_search_document import SkillSearchDocument
from app.persistence.models.skill_user_star import SkillUserStar
from app.persistence.models.skill_version import SkillVersion
from app.persistence.models.trust_evidence import TrustEvidence
from app.persistence.skill_registry_repository_support import (
    GRAPH_EDGE_ORDER,
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

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        semantic_embedding_index_key: str = DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
        semantic_embedding_dimensions: int = DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS,
    ) -> None:
        self._session_factory = session_factory
        self._semantic_embedding_index_key = semantic_embedding_index_key
        self._semantic_embedding_dimensions = semantic_embedding_dimensions

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
                skill = self._get_or_create_skill(
                    session=session,
                    slug=record.slug,
                    namespace_slug=record.governance.namespace,
                )
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
                    artifact_origin=record.governance.artifact_origin,
                    review_state=record.governance.review_state,
                    promotion_channel=record.governance.promotion_channel,
                    policy_pack_fk=self._policy_pack_id(
                        session=session,
                        slug=record.governance.policy_pack_slug,
                    ),
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
                self._add_authored_graph_edges(
                    session=session,
                    skill=skill,
                    skill_version=skill_version,
                    selector_rows=selector_rows,
                )
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
                self._add_pending_search_embedding(
                    session=session,
                    skill_version_id=skill_version.id,
                    slug=record.slug,
                    metadata=record.metadata,
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

    def list_top_installed_versions(self, *, limit: int) -> tuple[SkillVersionDetail, ...]:
        return self._list_installed_versions(limit=limit)

    def list_catalog_skill_versions(self) -> tuple[SkillVersionDetail, ...]:
        return self._list_installed_versions(limit=None)

    def _list_installed_versions(self, *, limit: int | None) -> tuple[SkillVersionDetail, ...]:
        with self._session_factory() as session:
            statement = (
                select(SkillVersion)
                .join(Skill, Skill.id == SkillVersion.skill_fk)
                .options(
                    joinedload(SkillVersion.skill),
                    joinedload(SkillVersion.skill).joinedload(Skill.namespace),
                    joinedload(SkillVersion.content),
                    joinedload(SkillVersion.metadata_row),
                    joinedload(SkillVersion.policy_pack),
                )
                .where(SkillVersion.lifecycle_status.in_(("published", "deprecated")))
                .order_by(
                    Skill.install_count.desc(),
                    SkillVersion.published_at.desc(),
                    Skill.slug.asc(),
                )
            )
            rows = session.execute(statement).scalars().all()

        by_slug: dict[str, list[SkillVersion]] = {}
        for row in rows:
            by_slug.setdefault(row.skill.slug, []).append(row)

        current_defaults = [
            current
            for versions in by_slug.values()
            if (current := select_current_default_version(versions)) is not None
        ]
        ordered = sorted(
            current_defaults,
            key=lambda item: (
                -item.skill.install_count,
                -item.published_at.timestamp(),
                item.skill.slug,
            ),
        )
        if limit is not None:
            ordered = ordered[:limit]
        return tuple(to_skill_version_detail(item) for item in ordered)

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

    def list_skill_graph_edges(
        self,
        *,
        sources: tuple[tuple[str, str], ...],
        edge_types: tuple[SkillGraphEdgeType, ...],
    ) -> tuple[SkillGraphEdge, ...]:
        if not sources:
            return ()

        source_versions = dict(sources)
        source_slugs = tuple(source_versions)
        edge_type_set = set(edge_types)
        with self._session_factory() as session:
            rows = session.execute(
                select(
                    Skill.slug.label("source_slug"),
                    SkillGraphEdgeModel.target_slug,
                    SkillGraphEdgeModel.edge_type,
                    SkillGraphEdgeModel.provenance,
                    SkillGraphEdgeModel.confidence,
                    SkillGraphEdgeModel.evidence,
                )
                .join(Skill, Skill.id == SkillGraphEdgeModel.source_skill_fk)
                .where(
                    SkillGraphEdgeModel.active.is_(True),
                    Skill.slug.in_(source_slugs),
                    SkillGraphEdgeModel.edge_type.in_(tuple(edge_type_set)),
                )
            ).mappings()
            edges = [
                SkillGraphEdge(
                    source_slug=str(row["source_slug"]),
                    source_version=source_versions[str(row["source_slug"])],
                    target_slug=str(row["target_slug"]),
                    edge_type=cast(SkillGraphEdgeType, row["edge_type"]),
                    provenance=cast(SkillGraphEdgeProvenance, row["provenance"]),
                    confidence=(
                        None
                        if row["confidence"] is None
                        else float(row["confidence"])
                    ),
                )
                for row in rows
            ]
        return tuple(
            sorted(
                edges,
                key=lambda edge: (
                    source_slugs.index(edge.source_slug),
                    GRAPH_EDGE_ORDER[edge.edge_type],
                    999
                    if edge.provenance != "authored"
                    else int((edge.confidence is not None) or 0),
                    edge.target_slug,
                ),
            )
        )

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
                    "identity_query_text": request.identity_query_text,
                    "full_text_query_text": request.full_text_query_text,
                    "query_contains_pattern": build_contains_pattern(request.identity_query_text),
                    "required_tags": list(request.required_tags),
                    "required_tag_count": len(request.required_tags),
                    "published_after": published_after,
                    "max_content_size_bytes": request.max_content_size_bytes,
                    "lifecycle_statuses": list(request.lifecycle_statuses),
                    "trust_tiers": list(request.trust_tiers),
                    "namespaces": list(request.namespaces or ()),
                    "namespaces_unrestricted": request.namespaces is None,
                    "promotion_channels": list(request.promotion_channels or ()),
                    "promotion_channels_unrestricted": request.promotion_channels is None,
                    "review_states": list(request.review_states),
                    "limit": request.limit,
                },
            ).mappings()
            return tuple(self._to_search_candidate(row) for row in rows)

    def search_semantic_candidates(
        self,
        *,
        request: SearchSemanticCandidatesRequest,
    ) -> tuple[StoredSkillSearchCandidate, ...]:
        published_after = None
        if request.fresh_within_days is not None:
            published_after = datetime.now(UTC) - timedelta(days=request.fresh_within_days)

        query_embedding = serialize_embedding_vector(request.query_embedding)
        vector_type = f"halfvec({request.embedding_dimensions})"
        with self._session_factory() as session:
            session.execute(text(f"SET LOCAL hnsw.ef_search = {request.hnsw_ef_search}"))
            semantic_statement = text(
                f"""
                    SELECT
                        doc.skill_version_fk,
                        doc.slug,
                        doc.version,
                        doc.name,
                        doc.description,
                        doc.tags,
                        doc.lifecycle_status,
                        doc.trust_tier,
                        doc.namespace,
                        doc.artifact_origin,
                        doc.review_state,
                        doc.promotion_channel,
                        doc.policy_pack_slug,
                        pack.rules AS policy_pack_rules,
                        doc.published_at,
                        doc.content_size_bytes,
                        doc.usage_count,
                        FALSE AS exact_slug_match,
                        FALSE AS exact_name_match,
                        0.0 AS lexical_score,
                        CASE
                            WHEN :required_tag_count > 0 THEN (
                                SELECT COUNT(*)
                                FROM unnest(doc.normalized_tags) AS tag
                                WHERE tag = ANY(:required_tags)
                            )
                            ELSE 0
                        END AS tag_overlap_count,
                        emb.embedding_vector <=> CAST(:query_embedding AS {vector_type})
                            AS semantic_distance
                    FROM skill_search_embeddings AS emb
                    JOIN skill_search_documents AS doc
                        ON doc.skill_version_fk = emb.skill_version_fk
                    LEFT JOIN policy_packs AS pack
                        ON pack.slug = doc.policy_pack_slug
                    WHERE emb.embedding_model = :embedding_model
                      AND emb.embedding_dimensions = :embedding_dimensions
                      AND emb.index_status = 'indexed'
                      AND emb.embedding_vector IS NOT NULL
                      AND (
                        :required_tag_count = 0
                        OR doc.normalized_tags @> :required_tags
                      )
                      AND (
                        :published_after IS NULL
                        OR doc.published_at >= :published_after
                      )
                      AND (
                        :max_content_size_bytes IS NULL
                        OR doc.content_size_bytes <= :max_content_size_bytes
                      )
                      AND doc.lifecycle_status = ANY(:lifecycle_statuses)
                      AND doc.trust_tier = ANY(:trust_tiers)
                      AND (
                        :namespaces_unrestricted
                        OR doc.namespace = ANY(:namespaces)
                      )
                      AND (
                        :promotion_channels_unrestricted
                        OR doc.promotion_channel = ANY(:promotion_channels)
                      )
                      AND doc.review_state = ANY(:review_states)
                    ORDER BY semantic_distance ASC, doc.slug ASC, doc.skill_version_fk DESC
                    LIMIT :limit
                    """
            ).bindparams(
                bindparam("query_embedding", type_=Text()),
                bindparam("embedding_model", type_=Text()),
                bindparam("embedding_dimensions", type_=Integer()),
                bindparam("required_tags", type_=ARRAY(Text())),
                bindparam("required_tag_count", type_=Integer()),
                bindparam("published_after", type_=DateTime(timezone=True)),
                bindparam("max_content_size_bytes", type_=BigInteger()),
                bindparam("lifecycle_statuses", type_=ARRAY(Text())),
                bindparam("trust_tiers", type_=ARRAY(Text())),
                bindparam("namespaces", type_=ARRAY(Text())),
                bindparam("namespaces_unrestricted", type_=Boolean()),
                bindparam("promotion_channels", type_=ARRAY(Text())),
                bindparam("promotion_channels_unrestricted", type_=Boolean()),
                bindparam("review_states", type_=ARRAY(Text())),
                bindparam("limit", type_=Integer()),
            )
            rows = session.execute(
                semantic_statement,
                {
                    "query_embedding": query_embedding,
                    "embedding_model": request.embedding_model,
                    "embedding_dimensions": request.embedding_dimensions,
                    "required_tags": list(request.required_tags),
                    "required_tag_count": len(request.required_tags),
                    "published_after": published_after,
                    "max_content_size_bytes": request.max_content_size_bytes,
                    "lifecycle_statuses": list(request.lifecycle_statuses),
                    "trust_tiers": list(request.trust_tiers),
                    "namespaces": list(request.namespaces or ()),
                    "namespaces_unrestricted": request.namespaces is None,
                    "promotion_channels": list(request.promotion_channels or ()),
                    "promotion_channels_unrestricted": request.promotion_channels is None,
                    "review_states": list(request.review_states),
                    "limit": request.limit,
                },
            ).mappings()
            return tuple(self._to_search_candidate(row) for row in rows)

    def backfill_pending_skill_embeddings(
        self,
        *,
        embedding_model: str,
        embedding_dimensions: int,
    ) -> int:
        """Create missing Plan 18 pending embedding rows from search documents."""
        inserted_count = 0
        with self._session_factory() as session:
            rows = (
                session.execute(
                    text(
                        """
                        SELECT skill_version_fk, slug, name, description, tags
                        FROM skill_search_documents
                        ORDER BY skill_version_fk
                        """
                    )
                )
                .mappings()
                .all()
            )
            for row in rows:
                source_text = build_embedding_source(
                    slug=str(row["slug"]),
                    name=str(row["name"]),
                    description=(
                        str(row["description"]) if row["description"] is not None else None
                    ),
                    tags=tuple(ensure_string_list(row["tags"])),
                )
                source_checksum = build_source_checksum_digest(source_text)
                existing = (
                    session.execute(
                        text(
                            """
                            SELECT source_checksum_digest, index_status
                            FROM skill_search_embeddings
                            WHERE skill_version_fk = :skill_version_fk
                              AND embedding_model = :embedding_model
                            """
                        ),
                        {
                            "skill_version_fk": int(row["skill_version_fk"]),
                            "embedding_model": embedding_model,
                        },
                    )
                    .mappings()
                    .one_or_none()
                )
                if existing is None:
                    session.execute(
                        text(
                            """
                            INSERT INTO skill_search_embeddings (
                                skill_version_fk,
                                embedding_model,
                                embedding_dimensions,
                                source_checksum_digest,
                                index_status
                            )
                            VALUES (
                                :skill_version_fk,
                                :embedding_model,
                                :embedding_dimensions,
                                :source_checksum_digest,
                                'pending'
                            )
                            """
                        ),
                        {
                            "skill_version_fk": int(row["skill_version_fk"]),
                            "embedding_model": embedding_model,
                            "embedding_dimensions": embedding_dimensions,
                            "source_checksum_digest": source_checksum,
                        },
                    )
                    inserted_count += 1
                    continue
                if str(existing["source_checksum_digest"]) != source_checksum:
                    session.execute(
                        text(
                            """
                            UPDATE skill_search_embeddings
                            SET embedding_dimensions = :embedding_dimensions,
                                source_checksum_digest = :source_checksum_digest,
                                embedding_vector = NULL,
                                index_status = 'stale',
                                indexed_at = NULL,
                                last_error = NULL,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE skill_version_fk = :skill_version_fk
                              AND embedding_model = :embedding_model
                            """
                        ),
                        {
                            "skill_version_fk": int(row["skill_version_fk"]),
                            "embedding_model": embedding_model,
                            "embedding_dimensions": embedding_dimensions,
                            "source_checksum_digest": source_checksum,
                        },
                    )
            session.commit()
        return inserted_count

    def claim_skill_embedding_work(
        self,
        *,
        embedding_model: str,
        limit: int,
        reclaim_after_seconds: int,
    ) -> tuple[SkillEmbeddingWorkItem, ...]:
        """Claim pending, stale, or abandoned embedding rows without provider locks."""
        with self._session_factory() as session:
            rows = (
                session.execute(
                    text(
                        """
                        WITH candidate_rows AS (
                            SELECT
                                emb.skill_version_fk,
                                emb.embedding_model,
                                emb.embedding_dimensions,
                                emb.source_checksum_digest,
                                doc.slug,
                                doc.name,
                                doc.description,
                                doc.tags
                            FROM skill_search_embeddings AS emb
                            JOIN skill_search_documents AS doc
                                ON doc.skill_version_fk = emb.skill_version_fk
                            WHERE emb.embedding_model = :embedding_model
                              AND (
                                emb.index_status IN ('pending', 'stale')
                                OR (
                                    emb.index_status = 'processing'
                                    AND emb.updated_at <= (
                                        CURRENT_TIMESTAMP
                                        - (:reclaim_after_seconds * INTERVAL '1 second')
                                    )
                                )
                              )
                            ORDER BY emb.updated_at ASC, emb.skill_version_fk ASC
                            FOR UPDATE OF emb SKIP LOCKED
                            LIMIT :limit
                        ),
                        updated AS (
                            UPDATE skill_search_embeddings AS emb
                            SET index_status = 'processing',
                                last_error = NULL,
                                updated_at = CURRENT_TIMESTAMP
                            FROM candidate_rows AS candidate
                            WHERE emb.skill_version_fk = candidate.skill_version_fk
                              AND emb.embedding_model = candidate.embedding_model
                            RETURNING
                                emb.skill_version_fk,
                                emb.embedding_model,
                                emb.embedding_dimensions,
                                emb.source_checksum_digest,
                                candidate.slug,
                                candidate.name,
                                candidate.description,
                                candidate.tags
                        )
                        SELECT *
                        FROM updated
                        ORDER BY skill_version_fk
                        """
                    ),
                    {
                        "embedding_model": embedding_model,
                        "limit": limit,
                        "reclaim_after_seconds": reclaim_after_seconds,
                    },
                )
                .mappings()
                .all()
            )
            session.commit()

        work_items: list[SkillEmbeddingWorkItem] = []
        for row in rows:
            source_text = build_embedding_source(
                slug=str(row["slug"]),
                name=str(row["name"]),
                description=str(row["description"]) if row["description"] is not None else None,
                tags=tuple(ensure_string_list(row["tags"])),
            )
            source_checksum = build_source_checksum_digest(source_text)
            if source_checksum != str(row["source_checksum_digest"]):
                self._mark_skill_embedding_stale(
                    skill_version_fk=int(row["skill_version_fk"]),
                    embedding_model=str(row["embedding_model"]),
                    embedding_dimensions=int(row["embedding_dimensions"]),
                    source_checksum_digest=source_checksum,
                )
                continue
            work_items.append(
                SkillEmbeddingWorkItem(
                    skill_version_fk=int(row["skill_version_fk"]),
                    embedding_model=str(row["embedding_model"]),
                    embedding_dimensions=int(row["embedding_dimensions"]),
                    source_checksum_digest=source_checksum,
                    source_text=source_text,
                )
            )
        return tuple(work_items)

    def index_skill_embedding(self, *, record: SkillEmbeddingIndexRecord) -> None:
        """Persist one validated vector and mark the derived row indexed."""
        embedding_vector = serialize_embedding_vector(
            validate_embedding_vector(
                record.embedding_vector,
                dimensions=record.embedding_dimensions,
            )
        )
        vector_type = f"halfvec({record.embedding_dimensions})"
        with self._session_factory() as session:
            session.execute(
                text(
                    f"""
                    UPDATE skill_search_embeddings
                    SET embedding_dimensions = :embedding_dimensions,
                        source_checksum_digest = :source_checksum_digest,
                        embedding_vector = CAST(:embedding_vector AS {vector_type}),
                        index_status = 'indexed',
                        indexed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP,
                        last_error = NULL
                    WHERE skill_version_fk = :skill_version_fk
                      AND embedding_model = :embedding_model
                    """
                ),
                {
                    "skill_version_fk": record.skill_version_fk,
                    "embedding_model": record.embedding_model,
                    "embedding_dimensions": record.embedding_dimensions,
                    "source_checksum_digest": record.source_checksum_digest,
                    "embedding_vector": embedding_vector,
                },
            )
            session.commit()

    def mark_skill_embedding_failed(
        self,
        *,
        skill_version_fk: int,
        embedding_model: str,
        error: str,
    ) -> None:
        """Record an indexing failure without touching authoritative catalog state."""
        with self._session_factory() as session:
            session.execute(
                text(
                    """
                    UPDATE skill_search_embeddings
                    SET embedding_vector = NULL,
                        index_status = 'failed',
                        indexed_at = NULL,
                        updated_at = CURRENT_TIMESTAMP,
                        last_error = :last_error
                    WHERE skill_version_fk = :skill_version_fk
                      AND embedding_model = :embedding_model
                    """
                ),
                {
                    "skill_version_fk": skill_version_fk,
                    "embedding_model": embedding_model,
                    "last_error": error[:500],
                },
            )
            session.commit()

    def get_co_usage_boosts(self, *, request: CoUsageBoostRequest) -> dict[str, float]:
        if not request.context_skill_slugs or not request.candidate_slugs:
            return {}
        with self._session_factory() as session:
            rows = session.execute(
                text(
                    """
                    SELECT
                        related.slug,
                        LEAST(
                            :boost_cap,
                            GREATEST(0.0, MAX(pair.co_usage_rate)::float * :boost_cap)
                        ) AS boost
                    FROM skill_co_usage_pairs AS pair
                    JOIN skills AS anchor
                        ON anchor.id = pair.anchor_skill_fk
                    JOIN skills AS related
                        ON related.id = pair.related_skill_fk
                    WHERE anchor.slug = ANY(:context_skill_slugs)
                      AND related.slug = ANY(:candidate_slugs)
                    GROUP BY related.slug
                    """
                ),
                {
                    "context_skill_slugs": list(request.context_skill_slugs),
                    "candidate_slugs": list(request.candidate_slugs),
                    "boost_cap": request.boost_cap,
                },
            ).mappings()
            return {str(row["slug"]): float(row["boost"]) for row in rows}

    def import_observation_run(
        self,
        *,
        record: CoUsageObservationImportRecord,
        policy: CoUsageRelatesToPolicy,
    ) -> CoUsageObservationImportResult:
        with self._session_factory() as session:
            existing_run = session.execute(
                text(
                    """
                    SELECT id
                    FROM skill_usage_observation_runs
                    WHERE source = :source
                      AND source_digest = :source_digest
                    LIMIT 1
                    """
                ),
                {"source": record.source, "source_digest": record.source_digest},
            ).scalar_one_or_none()
            if existing_run is not None:
                return CoUsageObservationImportResult(
                    imported=False,
                    observations_accepted=0,
                    pairs_rebuilt=0,
                    edges_activated=0,
                    edges_deactivated=0,
                    duplicate=True,
                )

            skill_rows = session.execute(
                select(Skill.slug, Skill.id).where(Skill.slug.in_(record.skill_slugs))
            ).all()
            skill_ids = {str(slug): int(skill_id) for slug, skill_id in skill_rows}
            missing_slugs = tuple(slug for slug in record.skill_slugs if slug not in skill_ids)
            if missing_slugs:
                raise UnknownCoUsageSkillError(slugs=missing_slugs)

            run_id = session.execute(
                text(
                    """
                    INSERT INTO skill_usage_observation_runs (
                        source,
                        source_digest,
                        observed_at
                    )
                    VALUES (:source, :source_digest, :observed_at)
                    RETURNING id
                    """
                ),
                {
                    "source": record.source,
                    "source_digest": record.source_digest,
                    "observed_at": record.observed_at,
                },
            ).scalar_one()
            session.execute(
                text(
                    """
                    INSERT INTO skill_usage_observations (run_fk, skill_fk, skill_slug)
                    VALUES (:run_fk, :skill_fk, :skill_slug)
                    """
                ),
                [
                    {
                        "run_fk": run_id,
                        "skill_fk": skill_ids[slug],
                        "skill_slug": slug,
                    }
                    for slug in record.skill_slugs
                ],
            )
            pairs_rebuilt = self._rebuild_co_usage_pairs(session=session, policy=policy)
            edges_activated, edges_deactivated = self._sync_co_usage_graph_edges(
                session=session,
                policy=policy,
            )
            session.commit()
            return CoUsageObservationImportResult(
                imported=True,
                observations_accepted=len(record.skill_slugs),
                pairs_rebuilt=pairs_rebuilt,
                edges_activated=edges_activated,
                edges_deactivated=edges_deactivated,
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

    def apply_star_count_deltas(
        self,
        *,
        deltas: tuple[tuple[str, int], ...],
    ) -> tuple[SkillStarCount, ...]:
        if not deltas:
            return ()

        slugs = tuple(slug for slug, _ in deltas)
        with self._session_factory() as session:
            existing = (
                session.execute(select(Skill.slug).where(Skill.slug.in_(slugs))).scalars().all()
            )
            existing_set = set(existing)
            missing = tuple(slug for slug in slugs if slug not in existing_set)
            if missing:
                # Deduplicate while preserving order so the error stays stable.
                seen: set[str] = set()
                unique_missing: list[str] = []
                for slug in missing:
                    if slug in seen:
                        continue
                    seen.add(slug)
                    unique_missing.append(slug)
                raise UnknownStarEventSkillsError(slugs=tuple(unique_missing))

            updated: dict[str, int] = {}
            for slug, delta in deltas:
                row = session.execute(
                    update(Skill)
                    .where(Skill.slug == slug)
                    .values(star_count=func.greatest(0, Skill.star_count + delta))
                    .returning(Skill.star_count)
                ).one_or_none()
                if row is None:
                    raise UnknownStarEventSkillsError(slugs=(slug,))
                updated[slug] = int(row[0])
            session.commit()

        return tuple(SkillStarCount(slug=slug, star_count=updated[slug]) for slug in slugs)

    def list_user_starred_skill_slugs(self, *, user_subject: str) -> tuple[str, ...]:
        with self._session_factory() as session:
            rows = session.execute(
                select(Skill.slug)
                .join(SkillUserStar, SkillUserStar.skill_fk == Skill.id)
                .where(SkillUserStar.user_subject == user_subject)
                .order_by(Skill.slug.asc())
            ).scalars()
            return tuple(rows)

    def apply_user_star_events(
        self,
        *,
        user_subject: str,
        events: tuple[StarEvent, ...],
    ) -> tuple[SkillStarCount, ...]:
        if not events:
            return ()

        slugs = tuple(event.slug for event in events)
        with self._session_factory() as session:
            skills = (
                session.execute(select(Skill).where(Skill.slug.in_(slugs)).with_for_update())
                .scalars()
                .all()
            )
            skill_by_slug = {skill.slug: skill for skill in skills}
            missing = tuple(slug for slug in slugs if slug not in skill_by_slug)
            if missing:
                seen: set[str] = set()
                unique_missing: list[str] = []
                for slug in missing:
                    if slug in seen:
                        continue
                    seen.add(slug)
                    unique_missing.append(slug)
                raise UnknownStarEventSkillsError(slugs=tuple(unique_missing))

            results: list[SkillStarCount] = []
            for event in events:
                skill = skill_by_slug[event.slug]
                existing_star_id = session.execute(
                    select(SkillUserStar.id).where(
                        SkillUserStar.user_subject == user_subject,
                        SkillUserStar.skill_fk == skill.id,
                    )
                ).scalar_one_or_none()
                if event.action == "star" and existing_star_id is None:
                    session.add(
                        SkillUserStar(
                            user_subject=user_subject,
                            skill_fk=skill.id,
                        )
                    )
                    skill.star_count += 1
                elif event.action == "unstar" and existing_star_id is not None:
                    session.execute(
                        delete(SkillUserStar).where(SkillUserStar.id == existing_star_id)
                    )
                    skill.star_count = max(0, skill.star_count - 1)

                session.add(skill)
                session.flush()
                results.append(SkillStarCount(slug=event.slug, star_count=int(skill.star_count)))
            session.commit()

        return tuple(results)

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

    def create_organization(
        self,
        *,
        slug: str,
        display_name: str,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> OrganizationRecord:
        with self._session_factory() as session:
            try:
                organization = Organization(slug=slug, display_name=display_name)
                session.add(organization)
                self._add_audit_events(session=session, audit_events=audit_events)
                session.commit()
                session.refresh(organization)
                return OrganizationRecord(
                    slug=organization.slug,
                    display_name=organization.display_name,
                    created_at=organization.created_at,
                )
            except SQLAlchemyError as exc:
                session.rollback()
                raise SkillRegistryPersistenceError("Failed to create organization.") from exc

    def create_namespace(
        self,
        *,
        slug: str,
        organization_slug: str,
        visibility: str,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> NamespaceRecord:
        with self._session_factory() as session:
            try:
                organization = self._get_organization(session=session, slug=organization_slug)
                namespace = Namespace(
                    slug=slug,
                    organization_fk=organization.id,
                    visibility=visibility,
                )
                session.add(namespace)
                self._add_audit_events(session=session, audit_events=audit_events)
                session.commit()
                session.refresh(namespace)
                return NamespaceRecord(
                    slug=namespace.slug,
                    organization_slug=organization.slug,
                    visibility=namespace.visibility,
                    created_at=namespace.created_at,
                )
            except SQLAlchemyError as exc:
                session.rollback()
                raise SkillRegistryPersistenceError("Failed to create namespace.") from exc

    def upsert_policy_pack(
        self,
        *,
        slug: str,
        description: str | None,
        rules: dict[str, object],
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> PolicyPackRecord:
        with self._session_factory() as session:
            try:
                policy_pack = session.execute(
                    select(PolicyPack).where(PolicyPack.slug == slug)
                ).scalar_one_or_none()
                if policy_pack is None:
                    policy_pack = PolicyPack(slug=slug, description=description, rules=rules)
                    session.add(policy_pack)
                else:
                    policy_pack.description = description
                    policy_pack.rules = rules
                self._add_audit_events(session=session, audit_events=audit_events)
                session.commit()
                return PolicyPackRecord(
                    slug=policy_pack.slug,
                    description=policy_pack.description,
                    rules=dict(policy_pack.rules),
                )
            except SQLAlchemyError as exc:
                session.rollback()
                raise SkillRegistryPersistenceError("Failed to upsert policy pack.") from exc

    def update_skill_ownership(
        self,
        *,
        slug: str,
        namespace: str,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> SkillOwnershipUpdate | None:
        with self._session_factory() as session:
            try:
                skill = self._get_skill(session=session, slug=slug)
                if skill is None:
                    return None
                namespace_row = self._get_namespace(session=session, slug=namespace)
                skill.namespace_fk = namespace_row.id
                session.add(skill)
                session.execute(
                    update(SkillSearchDocument)
                    .where(
                        SkillSearchDocument.skill_version_fk.in_(
                            select(SkillVersion.id).where(SkillVersion.skill_fk == skill.id)
                        )
                    )
                    .values(namespace=namespace_row.slug)
                )
                self._add_audit_events(session=session, audit_events=audit_events)
                session.commit()
                return SkillOwnershipUpdate(slug=slug, namespace=namespace_row.slug)
            except SQLAlchemyError as exc:
                session.rollback()
                raise SkillRegistryPersistenceError("Failed to update skill ownership.") from exc

    def update_version_governance(
        self,
        *,
        slug: str,
        version: str,
        review_state: ReviewState | None = None,
        promotion_channel: PromotionChannel | None = None,
        trust_tier: TrustTier | None = None,
        policy_pack_slug: str | None = None,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> SkillVersionGovernanceUpdate | None:
        with self._session_factory() as session:
            try:
                entity = self._get_version_entity(session=session, slug=slug, version=version)
                if entity is None:
                    return None
                if review_state is not None:
                    entity.review_state = review_state
                if promotion_channel is not None:
                    entity.promotion_channel = promotion_channel
                if trust_tier is not None:
                    entity.trust_tier = trust_tier
                if policy_pack_slug is not None:
                    entity.policy_pack_fk = self._policy_pack_id(
                        session=session,
                        slug=policy_pack_slug,
                    )
                session.add(entity)
                session.flush()
                if policy_pack_slug is not None:
                    synced_policy_pack_slug = policy_pack_slug
                elif entity.policy_pack is not None:
                    synced_policy_pack_slug = entity.policy_pack.slug
                else:
                    synced_policy_pack_slug = None
                self._sync_search_governance(
                    session=session,
                    entity=entity,
                    policy_pack_slug=synced_policy_pack_slug,
                )
                self._add_audit_events(session=session, audit_events=audit_events)
                session.commit()
                reloaded = self._get_version_entity(session=session, slug=slug, version=version)
                if reloaded is None:
                    return None
                return SkillVersionGovernanceUpdate(
                    slug=slug,
                    version=version,
                    lifecycle_status=cast(LifecycleStatus, reloaded.lifecycle_status),
                    trust_tier=cast(TrustTier, reloaded.trust_tier),
                    namespace=reloaded.skill.namespace.slug,
                    artifact_origin=cast(ArtifactOrigin, reloaded.artifact_origin),
                    review_state=cast(ReviewState, reloaded.review_state),
                    promotion_channel=cast(PromotionChannel, reloaded.promotion_channel),
                    policy_pack_slug=(
                        None if reloaded.policy_pack is None else reloaded.policy_pack.slug
                    ),
                )
            except SQLAlchemyError as exc:
                session.rollback()
                raise SkillRegistryPersistenceError("Failed to update version governance.") from exc

    def add_trust_evidence(
        self,
        *,
        slug: str,
        version: str,
        evidence_type: str,
        subject: str,
        digest: str | None,
        uri: str | None,
        payload: dict[str, object] | None,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> TrustEvidenceRecord | None:
        with self._session_factory() as session:
            try:
                entity = self._get_version_entity(session=session, slug=slug, version=version)
                if entity is None:
                    return None
                evidence = TrustEvidence(
                    skill_version_fk=entity.id,
                    evidence_type=evidence_type,
                    subject=subject,
                    digest=digest,
                    uri=uri,
                    payload=payload,
                )
                session.add(evidence)
                self._add_audit_events(session=session, audit_events=audit_events)
                session.commit()
                session.refresh(evidence)
                return TrustEvidenceRecord(
                    slug=slug,
                    version=version,
                    evidence_type=evidence.evidence_type,
                    subject=evidence.subject,
                    digest=evidence.digest,
                    uri=evidence.uri,
                    created_at=evidence.created_at,
                )
            except SQLAlchemyError as exc:
                session.rollback()
                raise SkillRegistryPersistenceError("Failed to append trust evidence.") from exc

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
    def _get_or_create_skill(*, session: Session, slug: str, namespace_slug: str) -> Skill:
        existing = session.execute(
            select(Skill).options(joinedload(Skill.namespace)).where(Skill.slug == slug)
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        namespace = SQLAlchemySkillCatalogRepository._get_namespace(
            session=session,
            slug=namespace_slug,
        )
        created = Skill(slug=slug, namespace_fk=namespace.id)
        session.add(created)
        session.flush()
        session.refresh(created, attribute_names=["namespace"])
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
                joinedload(SkillVersion.skill).joinedload(Skill.namespace),
                joinedload(SkillVersion.content),
                joinedload(SkillVersion.metadata_row),
                joinedload(SkillVersion.policy_pack),
                selectinload(SkillVersion.relationship_selectors),
            )
            .where(Skill.slug == slug, SkillVersion.version == version)
        )
        return session.execute(statement).scalar_one_or_none()

    @staticmethod
    def _get_skill(*, session: Session, slug: str) -> Skill | None:
        return session.execute(select(Skill).where(Skill.slug == slug)).scalar_one_or_none()

    @staticmethod
    def _get_organization(*, session: Session, slug: str) -> Organization:
        organization = session.execute(
            select(Organization).where(Organization.slug == slug)
        ).scalar_one_or_none()
        if organization is None:
            raise SkillRegistryPersistenceError(f"Organization not found: {slug}")
        return organization

    @staticmethod
    def _get_namespace(*, session: Session, slug: str) -> Namespace:
        namespace = session.execute(
            select(Namespace).where(Namespace.slug == slug)
        ).scalar_one_or_none()
        if namespace is None:
            raise SkillRegistryPersistenceError(f"Namespace not found: {slug}")
        return namespace

    @staticmethod
    def _policy_pack_id(*, session: Session, slug: str | None) -> int | None:
        if slug is None:
            return None
        policy_pack = session.execute(
            select(PolicyPack).where(PolicyPack.slug == slug)
        ).scalar_one_or_none()
        if policy_pack is None:
            raise SkillRegistryPersistenceError(f"Policy pack not found: {slug}")
        return policy_pack.id

    @staticmethod
    def _add_authored_graph_edges(
        *,
        session: Session,
        skill: Skill,
        skill_version: SkillVersion,
        selector_rows: list[SkillRelationshipSelector],
    ) -> None:
        graph_selectors = [
            selector
            for selector in selector_rows
            if selector.edge_type in {"depends_on", "extends", "overlaps_with"}
        ]
        if not graph_selectors:
            return
        target_slugs = tuple(dict.fromkeys(selector.target_slug for selector in graph_selectors))
        target_rows = session.execute(
            select(Skill.slug, Skill.id).where(Skill.slug.in_(target_slugs))
        ).all()
        target_ids = {str(slug): int(skill_id) for slug, skill_id in target_rows}
        deduped_selectors: dict[tuple[str, str], SkillRelationshipSelector] = {}
        for selector in graph_selectors:
            deduped_selectors.setdefault((selector.target_slug, selector.edge_type), selector)
        session.add_all(
            SkillGraphEdgeModel(
                source_skill_fk=skill.id,
                source_skill_version_fk=skill_version.id,
                target_skill_fk=target_ids.get(selector.target_slug),
                target_slug=selector.target_slug,
                edge_type=selector.edge_type,
                provenance="authored",
                active=True,
                confidence=None,
                evidence={"ordinal": selector.ordinal},
            )
            for selector in deduped_selectors.values()
        )

    @staticmethod
    def _rebuild_co_usage_pairs(
        *,
        session: Session,
        policy: CoUsageRelatesToPolicy,
    ) -> int:
        max_observed_at = session.execute(
            text("SELECT MAX(observed_at) FROM skill_usage_observation_runs")
        ).scalar_one_or_none()
        session.execute(text("DELETE FROM skill_co_usage_pairs"))
        if max_observed_at is None:
            return 0
        cutoff = max_observed_at - timedelta(days=policy.window_days)
        session.execute(
            text(
                """
                WITH window_runs AS (
                    SELECT id, observed_at
                    FROM skill_usage_observation_runs
                    WHERE observed_at >= :cutoff
                      AND observed_at <= :max_observed_at
                ),
                total_runs AS (
                    SELECT COUNT(*)::numeric AS run_count
                    FROM window_runs
                ),
                skill_counts AS (
                    SELECT
                        observation.skill_fk,
                        COUNT(DISTINCT observation.run_fk)::numeric AS run_count
                    FROM skill_usage_observations AS observation
                    JOIN window_runs AS run
                        ON run.id = observation.run_fk
                    GROUP BY observation.skill_fk
                ),
                ordered_pairs AS (
                    SELECT
                        anchor.skill_fk AS anchor_skill_fk,
                        related.skill_fk AS related_skill_fk,
                        COUNT(DISTINCT anchor.run_fk)::numeric AS run_count,
                        MAX(run.observed_at) AS last_observed_at
                    FROM skill_usage_observations AS anchor
                    JOIN skill_usage_observations AS related
                        ON related.run_fk = anchor.run_fk
                       AND related.skill_fk <> anchor.skill_fk
                    JOIN window_runs AS run
                        ON run.id = anchor.run_fk
                    GROUP BY anchor.skill_fk, related.skill_fk
                ),
                scored_pairs AS (
                    SELECT
                        pair.anchor_skill_fk,
                        pair.related_skill_fk,
                        pair.run_count,
                        pair.last_observed_at,
                        pair.run_count / anchor_count.run_count AS co_usage_rate,
                        (
                            pair.run_count * total_runs.run_count
                        ) / (
                            anchor_count.run_count * related_count.run_count
                        ) AS lift_score
                    FROM ordered_pairs AS pair
                    JOIN skill_counts AS anchor_count
                        ON anchor_count.skill_fk = pair.anchor_skill_fk
                    JOIN skill_counts AS related_count
                        ON related_count.skill_fk = pair.related_skill_fk
                    CROSS JOIN total_runs
                )
                INSERT INTO skill_co_usage_pairs (
                    anchor_skill_fk,
                    related_skill_fk,
                    observation_count,
                    distinct_run_count,
                    co_usage_rate,
                    lift_score,
                    pmi_score,
                    last_observed_at,
                    window_days
                )
                SELECT
                    anchor_skill_fk,
                    related_skill_fk,
                    run_count::bigint,
                    run_count::bigint,
                    ROUND(co_usage_rate, 6),
                    ROUND(lift_score, 6),
                    ROUND(LN(GREATEST(lift_score, 0.000001)), 6),
                    last_observed_at,
                    :window_days
                FROM scored_pairs
                """
            ),
            {
                "cutoff": cutoff,
                "max_observed_at": max_observed_at,
                "window_days": policy.window_days,
            },
        )
        return int(
            session.execute(text("SELECT COUNT(*) FROM skill_co_usage_pairs")).scalar_one()
        )

    @staticmethod
    def _sync_co_usage_graph_edges(
        *,
        session: Session,
        policy: CoUsageRelatesToPolicy,
    ) -> tuple[int, int]:
        eligible_pairs_sql = """
            SELECT
                LEAST(anchor_skill_fk, related_skill_fk) AS source_skill_fk,
                GREATEST(anchor_skill_fk, related_skill_fk) AS target_skill_fk,
                MAX(observation_count) AS observation_count,
                MAX(distinct_run_count) AS distinct_run_count,
                MAX(co_usage_rate) AS co_usage_rate,
                MAX(lift_score) AS lift_score,
                MAX(pmi_score) AS pmi_score,
                MAX(last_observed_at) AS last_observed_at,
                MAX(window_days) AS window_days
            FROM skill_co_usage_pairs
            WHERE distinct_run_count >= :min_runs
              AND co_usage_rate >= :min_rate
              AND lift_score > :min_lift
            GROUP BY
                LEAST(anchor_skill_fk, related_skill_fk),
                GREATEST(anchor_skill_fk, related_skill_fk)
        """
        parameters = {
            "min_runs": policy.min_runs,
            "min_rate": policy.min_rate,
            "min_lift": policy.min_lift,
        }
        deactivated = session.execute(
            text(
                f"""
                WITH eligible_pairs AS ({eligible_pairs_sql}),
                deactivated AS (
                    UPDATE skill_graph_edges AS edge
                    SET active = FALSE,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE edge.provenance = 'co_usage'
                      AND edge.active IS TRUE
                      AND NOT EXISTS (
                          SELECT 1
                          FROM eligible_pairs AS pair
                          WHERE pair.source_skill_fk = edge.source_skill_fk
                            AND pair.target_skill_fk = edge.target_skill_fk
                      )
                    RETURNING edge.id
                )
                SELECT COUNT(*) FROM deactivated
                """
            ),
            parameters,
        ).scalar_one()
        activated = session.execute(
            text(
                f"""
                WITH eligible_pairs AS ({eligible_pairs_sql}),
                upserted AS (
                    INSERT INTO skill_graph_edges (
                        source_skill_fk,
                        source_skill_version_fk,
                        target_skill_fk,
                        target_slug,
                        edge_type,
                        provenance,
                        active,
                        confidence,
                        evidence
                    )
                    SELECT
                        pair.source_skill_fk,
                        NULL,
                        pair.target_skill_fk,
                        target.slug,
                        'relates_to',
                        'co_usage',
                        TRUE,
                        LEAST(1.0, pair.co_usage_rate)::numeric(10, 6),
                        jsonb_build_object(
                            'observation_count', pair.observation_count,
                            'distinct_run_count', pair.distinct_run_count,
                            'co_usage_rate', pair.co_usage_rate,
                            'lift_score', pair.lift_score,
                            'pmi_score', pair.pmi_score,
                            'window_days', pair.window_days,
                            'last_observed_at', pair.last_observed_at
                        )
                    FROM eligible_pairs AS pair
                    JOIN skills AS target
                        ON target.id = pair.target_skill_fk
                    ON CONFLICT (
                        source_skill_fk,
                        target_skill_fk,
                        edge_type,
                        provenance
                    )
                    WHERE provenance = 'co_usage'
                    DO UPDATE SET
                        active = TRUE,
                        confidence = EXCLUDED.confidence,
                        evidence = EXCLUDED.evidence,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE skill_graph_edges.active IS DISTINCT FROM TRUE
                    RETURNING id
                )
                SELECT COUNT(*) FROM upserted
                """
            ),
            parameters,
        ).scalar_one()
        return int(activated), int(deactivated)

    def _add_pending_search_embedding(
        self,
        *,
        session: Session,
        skill_version_id: int,
        slug: str,
        metadata: MetadataRecordInput,
    ) -> None:
        source = build_embedding_source(
            slug=slug,
            name=metadata.name,
            description=metadata.description,
            tags=metadata.tags,
        )
        session.execute(
            text(
                """
                INSERT INTO skill_search_embeddings (
                    skill_version_fk,
                    embedding_model,
                    embedding_dimensions,
                    source_checksum_digest,
                    index_status
                )
                VALUES (
                    :skill_version_fk,
                    :embedding_model,
                    :embedding_dimensions,
                    :source_checksum_digest,
                    'pending'
                )
                ON CONFLICT (skill_version_fk, embedding_model)
                DO UPDATE SET
                    embedding_dimensions = EXCLUDED.embedding_dimensions,
                    source_checksum_digest = EXCLUDED.source_checksum_digest,
                    index_status = 'stale',
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "skill_version_fk": skill_version_id,
                "embedding_model": self._semantic_embedding_index_key,
                "embedding_dimensions": self._semantic_embedding_dimensions,
                "source_checksum_digest": build_source_checksum_digest(source),
            },
        )

    def _mark_skill_embedding_stale(
        self,
        *,
        skill_version_fk: int,
        embedding_model: str,
        embedding_dimensions: int,
        source_checksum_digest: str,
    ) -> None:
        with self._session_factory() as session:
            session.execute(
                text(
                    """
                    UPDATE skill_search_embeddings
                    SET embedding_dimensions = :embedding_dimensions,
                        source_checksum_digest = :source_checksum_digest,
                        embedding_vector = NULL,
                        index_status = 'stale',
                        indexed_at = NULL,
                        updated_at = CURRENT_TIMESTAMP,
                        last_error = NULL
                    WHERE skill_version_fk = :skill_version_fk
                      AND embedding_model = :embedding_model
                    """
                ),
                {
                    "skill_version_fk": skill_version_fk,
                    "embedding_model": embedding_model,
                    "embedding_dimensions": embedding_dimensions,
                    "source_checksum_digest": source_checksum_digest,
                },
            )
            session.commit()

    @staticmethod
    def _to_search_candidate(row: RowMapping) -> StoredSkillSearchCandidate:
        return StoredSkillSearchCandidate(
            skill_version_fk=int(row["skill_version_fk"]),
            slug=str(row["slug"]),
            version=str(row["version"]),
            name=str(row["name"]),
            description=str(row["description"]) if row["description"] is not None else None,
            tags=tuple(ensure_string_list(row["tags"])),
            lifecycle_status=cast(LifecycleStatus, str(row["lifecycle_status"])),
            trust_tier=cast(TrustTier, str(row["trust_tier"])),
            namespace=str(row["namespace"]),
            artifact_origin=cast(ArtifactOrigin, str(row["artifact_origin"])),
            review_state=cast(ReviewState, str(row["review_state"])),
            promotion_channel=cast(PromotionChannel, str(row["promotion_channel"])),
            policy_pack=(
                None
                if row["policy_pack_slug"] is None
                else DomainPolicyPack(
                    slug=str(row["policy_pack_slug"]),
                    rules=dict(row["policy_pack_rules"] or {}),
                )
            ),
            published_at=ensure_datetime(row["published_at"]),
            content_size_bytes=int(row["content_size_bytes"]),
            usage_count=int(row["usage_count"]),
            exact_slug_match=bool(row["exact_slug_match"]),
            exact_name_match=bool(row["exact_name_match"]),
            lexical_score=float(row["lexical_score"]),
            tag_overlap_count=int(row["tag_overlap_count"]),
            semantic_distance=(
                None
                if "semantic_distance" not in row or row["semantic_distance"] is None
                else float(row["semantic_distance"])
            ),
        )

    @staticmethod
    def _sync_search_governance(
        *,
        session: Session,
        entity: SkillVersion,
        policy_pack_slug: str | None,
    ) -> None:
        search_document = session.get(SkillSearchDocument, entity.id)
        if search_document is None:
            return
        search_document.trust_tier = entity.trust_tier
        search_document.artifact_origin = entity.artifact_origin
        search_document.review_state = entity.review_state
        search_document.promotion_channel = entity.promotion_channel
        search_document.policy_pack_slug = policy_pack_slug
        session.add(search_document)


SQLAlchemySkillRegistryRepository = SQLAlchemySkillCatalogRepository
