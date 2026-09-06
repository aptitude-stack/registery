"""Shared SQL and projection helpers for the SQLAlchemy catalog repository."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    Text,
    bindparam,
    func,
    literal_column,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.exc import IntegrityError

from app.core.governance import (
    ArtifactOrigin,
    LifecycleStatus,
    PromotionChannel,
    ProvenanceMetadata,
    ReviewState,
    TrustTier,
)
from app.core.governance import (
    PolicyPack as DomainPolicyPack,
)
from app.core.ports import (
    DuplicateSkillSlugPersistenceError,
    DuplicateSkillVersionPersistenceError,
    GovernanceRecordInput,
    MetadataRecordInput,
    RelationshipEdgeType,
    SkillRegistryPersistenceError,
)
from app.core.skills.models import (
    SHA256_ALGORITHM,
    SkillChecksum,
    SkillContentRecord,
    SkillContentSummary,
    SkillMetadata,
    SkillRelationshipSelector,
    SkillRelationshipSource,
    SkillVersionDetail,
    SkillVersionListEntry,
    SkillVersionStatusUpdate,
)
from app.core.skills.normalization import (
    expand_search_aliases,
    normalize_search_text,
    normalize_tag_list,
)
from app.persistence.models.skill_version import SkillVersion

RELATIONSHIP_EDGE_ORDER: dict[RelationshipEdgeType, int] = {
    "depends_on": 0,
    "extends": 1,
    "conflicts_with": 2,
    "overlaps_with": 3,
}
GRAPH_EDGE_ORDER: dict[str, int] = {
    "depends_on": 0,
    "extends": 1,
    "overlaps_with": 2,
    "relates_to": 3,
}

SEARCH_CANDIDATES_SQL = text(
    """
    WITH filtered AS (
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
            skill.install_count AS usage_count,
            CASE
                WHEN :identity_query_text IS NOT NULL
                    AND doc.normalized_slug = :identity_query_text THEN TRUE
                ELSE FALSE
            END AS exact_slug_match,
            CASE
                WHEN :identity_query_text IS NOT NULL
                    AND doc.normalized_name = :identity_query_text THEN TRUE
                ELSE FALSE
            END AS exact_name_match,
            CASE
                WHEN :full_text_query_text IS NOT NULL THEN ts_rank_cd(
                    doc.search_vector,
                    plainto_tsquery('simple'::regconfig, :full_text_query_text)
                )
                ELSE 0.0
            END AS lexical_score,
            CASE
                WHEN :required_tag_count > 0 THEN (
                    SELECT COUNT(*)
                    FROM unnest(doc.normalized_tags) AS tag
                    WHERE tag = ANY(:required_tags)
                )
                ELSE 0
            END AS tag_overlap_count
        FROM skill_search_documents AS doc
        JOIN skill_versions AS version ON version.id = doc.skill_version_fk
        JOIN skills AS skill ON skill.id = version.skill_fk
        LEFT JOIN policy_packs AS pack
            ON pack.slug = doc.policy_pack_slug
        WHERE (
            (:identity_query_text IS NULL AND :full_text_query_text IS NULL)
            OR (
                :full_text_query_text IS NOT NULL
                AND doc.search_vector @@ plainto_tsquery(
                    'simple'::regconfig,
                    :full_text_query_text
                )
            )
            OR doc.normalized_slug = :identity_query_text
            OR doc.normalized_name = :identity_query_text
            OR (
                :query_contains_pattern IS NOT NULL
                AND (
                    doc.normalized_slug LIKE :query_contains_pattern ESCAPE '\\'
                    OR doc.normalized_name LIKE :query_contains_pattern ESCAPE '\\'
                )
            )
        )
          AND (
            :required_tag_count = 0
            OR doc.normalized_slug = :identity_query_text
            OR doc.normalized_name = :identity_query_text
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
    ),
    ranked AS (
        SELECT
            filtered.*,
            ROW_NUMBER() OVER (
                PARTITION BY filtered.slug
                ORDER BY
                    filtered.exact_slug_match DESC,
                    filtered.exact_name_match DESC,
                    filtered.lexical_score DESC,
                    filtered.tag_overlap_count DESC,
                    filtered.usage_count DESC,
                    filtered.published_at DESC,
                    filtered.content_size_bytes ASC,
                    filtered.slug ASC,
                    filtered.skill_version_fk DESC
            ) AS skill_rank
        FROM filtered
    )
    SELECT
        skill_version_fk,
        slug,
        version,
        name,
        description,
        tags,
        lifecycle_status,
        trust_tier,
        namespace,
        artifact_origin,
        review_state,
        promotion_channel,
        policy_pack_slug,
        policy_pack_rules,
        published_at,
        content_size_bytes,
        usage_count,
        exact_slug_match,
        exact_name_match,
        lexical_score,
        tag_overlap_count
    FROM ranked
    WHERE skill_rank = 1
    ORDER BY
        exact_slug_match DESC,
        exact_name_match DESC,
        lexical_score DESC,
        tag_overlap_count DESC,
        usage_count DESC,
        published_at DESC,
        content_size_bytes ASC,
        slug ASC,
        skill_version_fk DESC
    LIMIT :limit
    """
).bindparams(
    bindparam("identity_query_text", type_=Text()),
    bindparam("full_text_query_text", type_=Text()),
    bindparam("query_contains_pattern", type_=Text()),
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


def to_skill_version_detail(entity: SkillVersion) -> SkillVersionDetail:
    """Project one eagerly loaded ORM version into the core detail model."""
    return SkillVersionDetail(
        slug=entity.skill.slug,
        version=entity.version,
        install_count=entity.skill.install_count,
        star_count=entity.skill.star_count,
        version_checksum=SkillChecksum(
            algorithm=SHA256_ALGORITHM,
            digest=entity.checksum_digest,
        ),
        content=SkillContentSummary(
            checksum=SkillChecksum(
                algorithm=SHA256_ALGORITHM,
                digest=entity.content.checksum_digest,
            ),
            media_type=entity.content.media_type,
            size_bytes=entity.content.storage_size_bytes,
        ),
        metadata=SkillMetadata(
            name=entity.name,
            description=entity.description,
            tags=tuple(entity.tags),
            token_estimate=entity.token_estimate,
            maturity_score=entity.maturity_score,
            security_score=entity.security_score,
            overall_score=entity.overall_score,
            assessment=(None if entity.assessment is None else dict(entity.assessment)),
        ),
        lifecycle_status=cast(LifecycleStatus, entity.lifecycle_status),
        trust_tier=cast(TrustTier, entity.trust_tier),
        namespace=entity.skill.namespace.slug,
        artifact_origin=cast(ArtifactOrigin, entity.artifact_origin),
        review_state=cast(ReviewState, entity.review_state),
        promotion_channel=cast(PromotionChannel, entity.promotion_channel),
        policy_pack=to_policy_pack(entity),
        provenance=to_provenance(entity),
        published_at=ensure_datetime(entity.published_at),
    )


def to_skill_content_record(entity: SkillVersion) -> SkillContentRecord:
    """Project one ORM version into the core content-read model."""
    return SkillContentRecord(
        slug=entity.skill.slug,
        version=entity.version,
        payload=entity.content.payload,
        checksum=SkillChecksum(
            algorithm=SHA256_ALGORITHM,
            digest=entity.content.checksum_digest,
        ),
        media_type=entity.content.media_type,
        size_bytes=entity.content.storage_size_bytes,
        lifecycle_status=cast(LifecycleStatus, entity.lifecycle_status),
        trust_tier=cast(TrustTier, entity.trust_tier),
        namespace=entity.skill.namespace.slug,
        artifact_origin=cast(ArtifactOrigin, entity.artifact_origin),
        review_state=cast(ReviewState, entity.review_state),
        promotion_channel=cast(PromotionChannel, entity.promotion_channel),
        policy_pack=to_policy_pack(entity),
    )


def to_skill_version_list_entry(entity: SkillVersion) -> SkillVersionListEntry:
    """Project one ORM version into the internal version-list row."""
    return SkillVersionListEntry(
        slug=entity.skill.slug,
        version=entity.version,
        lifecycle_status=cast(LifecycleStatus, entity.lifecycle_status),
        trust_tier=cast(TrustTier, entity.trust_tier),
        namespace=entity.skill.namespace.slug,
        artifact_origin=cast(ArtifactOrigin, entity.artifact_origin),
        review_state=cast(ReviewState, entity.review_state),
        promotion_channel=cast(PromotionChannel, entity.promotion_channel),
        policy_pack=to_policy_pack(entity),
        published_at=ensure_datetime(entity.published_at),
    )


def to_skill_relationship_source(entity: SkillVersion) -> SkillRelationshipSource:
    """Project one ORM version into the core relationship source model."""
    return SkillRelationshipSource(
        slug=entity.skill.slug,
        version=entity.version,
        lifecycle_status=cast(LifecycleStatus, entity.lifecycle_status),
        trust_tier=cast(TrustTier, entity.trust_tier),
        namespace=entity.skill.namespace.slug,
        artifact_origin=cast(ArtifactOrigin, entity.artifact_origin),
        review_state=cast(ReviewState, entity.review_state),
        promotion_channel=cast(PromotionChannel, entity.promotion_channel),
        policy_pack=to_policy_pack(entity),
        relationships=tuple(
            SkillRelationshipSelector(
                slug=selector.target_slug,
                version=selector.target_version,
                version_constraint=selector.version_constraint,
                optional=selector.optional,
                markers=tuple(selector.markers),
            )
            for selector in sort_relationship_selectors(entity.relationship_selectors)
            if selector.edge_type == "depends_on"
        ),
    )


def to_skill_version_status_update(
    *,
    entity: SkillVersion,
    lifecycle_changed_at: datetime,
    is_current_default: bool,
) -> SkillVersionStatusUpdate:
    """Project a lifecycle update result into the core status-update model."""
    return SkillVersionStatusUpdate(
        slug=entity.skill.slug,
        version=entity.version,
        status=cast(LifecycleStatus, entity.lifecycle_status),
        trust_tier=cast(TrustTier, entity.trust_tier),
        lifecycle_changed_at=lifecycle_changed_at,
        is_current_default=is_current_default,
    )


def sort_relationship_selectors(selectors: list[Any]) -> list[Any]:
    """Return selectors in stable public edge/ordinal order."""
    return sorted(
        selectors,
        key=lambda row: (
            RELATIONSHIP_EDGE_ORDER[cast(RelationshipEdgeType, row.edge_type)],
            row.ordinal,
        ),
    )


def build_search_document(
    *,
    skill_version_id: int,
    slug: str,
    version: str,
    metadata: MetadataRecordInput,
    governance: GovernanceRecordInput,
    published_at: datetime | None,
    content_size_bytes: int,
) -> Any:
    """Build the denormalized search row for one immutable version."""
    from app.persistence.models.skill_search_document import SkillSearchDocument

    return SkillSearchDocument(
        skill_version_fk=skill_version_id,
        slug=slug,
        normalized_slug=normalize_search_text(slug) or "",
        version=version,
        name=metadata.name,
        normalized_name=normalize_search_text(metadata.name) or "",
        description=metadata.description,
        tags=list(metadata.tags),
        normalized_tags=list(normalize_tag_list(metadata.tags)),
        lifecycle_status="published",
        trust_tier=governance.trust_tier,
        namespace=governance.namespace,
        artifact_origin=governance.artifact_origin,
        review_state=governance.review_state,
        promotion_channel=governance.promotion_channel,
        policy_pack_slug=governance.policy_pack_slug,
        search_vector=cast(
            Any,
            func.to_tsvector(
                literal_column("'simple'::regconfig"),
                build_search_document_source(slug=slug, metadata=metadata),
            ),
        ),
        published_at=ensure_datetime(published_at),
        content_size_bytes=content_size_bytes,
    )


def build_search_document_source(*, slug: str, metadata: MetadataRecordInput) -> str:
    """Combine immutable searchable fields into one deterministic text source."""
    parts = [
        expand_search_aliases(slug) or "",
        expand_search_aliases(metadata.name) or "",
    ]
    if metadata.description is not None:
        parts.append(expand_search_aliases(metadata.description) or "")
    parts.extend(expand_search_aliases(tag) or "" for tag in normalize_tag_list(metadata.tags))
    return " ".join(part for part in parts if part)


def classify_integrity_error(error: IntegrityError) -> SkillRegistryPersistenceError:
    """Return the typed persistence error that best matches an integrity failure."""
    constraint_name = _constraint_name(error)
    if constraint_name == "uq_skill_versions_skill_fk_version":
        return DuplicateSkillVersionPersistenceError("Immutable skill version already exists.")
    if constraint_name == "uq_skills_slug":
        return DuplicateSkillSlugPersistenceError("Skill slug already exists.")
    return SkillRegistryPersistenceError("Failed to persist immutable skill version.")


def ensure_string_list(raw: object) -> list[str]:
    """Validate that a raw DB value is a list of strings."""
    if not isinstance(raw, list):
        raise SkillRegistryPersistenceError("Expected a list of strings.")
    if not all(isinstance(item, str) for item in raw):
        raise SkillRegistryPersistenceError("Expected a list of strings.")
    return [str(item) for item in raw]


def ensure_datetime(value: datetime | None) -> datetime:
    """Validate that an expected timestamp exists."""
    if value is None:
        raise SkillRegistryPersistenceError("Published timestamp is missing.")
    return value


def build_contains_pattern(value: str | None) -> str | None:
    """Build an escaped SQL LIKE pattern for normalized search text."""
    if value is None:
        return None
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def to_provenance(entity: SkillVersion) -> ProvenanceMetadata | None:
    """Project provenance columns into the shared domain model."""
    if entity.provenance_repo_url is None or entity.provenance_commit_sha is None:
        return None
    return ProvenanceMetadata(
        repo_url=entity.provenance_repo_url,
        commit_sha=entity.provenance_commit_sha,
        tree_path=entity.provenance_tree_path,
        publisher_identity=entity.provenance_publisher_identity,
        policy_profile=entity.policy_profile_at_publish,
    )


def to_policy_pack(entity: SkillVersion) -> DomainPolicyPack | None:
    """Project an attached policy pack into the core domain model."""
    if entity.policy_pack is None:
        return None
    return DomainPolicyPack(slug=entity.policy_pack.slug, rules=dict(entity.policy_pack.rules))


def _constraint_name(error: IntegrityError) -> str | None:
    orig = error.orig
    diag = getattr(orig, "diag", None)
    constraint_name = getattr(diag, "constraint_name", None)
    return constraint_name if isinstance(constraint_name, str) else None
