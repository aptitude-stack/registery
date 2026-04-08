"""Shared SQL and projection helpers for the SQLAlchemy registry repository."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from sqlalchemy import BigInteger, DateTime, Integer, Text, bindparam, func, literal_column, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.exc import IntegrityError

from app.core.governance import LifecycleStatus, ProvenanceMetadata, TrustTier
from app.core.ports import (
    GovernanceRecordInput,
    MetadataRecordInput,
    RelationshipEdgeType,
    SkillRegistryPersistenceError,
    StoredRelationshipSelector,
    StoredSkillVersion,
)
from app.persistence.models.skill_relationship_selector import SkillRelationshipSelector
from app.persistence.models.skill_search_document import SkillSearchDocument
from app.persistence.models.skill_version import SkillVersion

RELATIONSHIP_EDGE_ORDER: dict[RelationshipEdgeType, int] = {
    "depends_on": 0,
    "extends": 1,
    "conflicts_with": 2,
    "overlaps_with": 3,
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
            doc.published_at,
            doc.content_size_bytes,
            doc.usage_count,
            CASE
                WHEN :query_text IS NOT NULL AND doc.normalized_slug = :query_text THEN TRUE
                ELSE FALSE
            END AS exact_slug_match,
            CASE
                WHEN :query_text IS NOT NULL AND doc.normalized_name = :query_text THEN TRUE
                ELSE FALSE
            END AS exact_name_match,
            CASE
                WHEN :query_text IS NOT NULL THEN ts_rank_cd(
                    doc.search_vector,
                    plainto_tsquery('simple'::regconfig, :query_text)
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
        WHERE (
            :query_text IS NULL
            OR doc.search_vector @@ plainto_tsquery('simple'::regconfig, :query_text)
            OR doc.normalized_slug = :query_text
            OR doc.normalized_name = :query_text
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
    bindparam("query_text", type_=Text()),
    bindparam("query_contains_pattern", type_=Text()),
    bindparam("required_tags", type_=ARRAY(Text())),
    bindparam("required_tag_count", type_=Integer()),
    bindparam("published_after", type_=DateTime(timezone=True)),
    bindparam("max_content_size_bytes", type_=BigInteger()),
    bindparam("lifecycle_statuses", type_=ARRAY(Text())),
    bindparam("trust_tiers", type_=ARRAY(Text())),
    bindparam("limit", type_=Integer()),
)


def to_stored_selector(selector: SkillRelationshipSelector) -> StoredRelationshipSelector:
    """Project one selector ORM row into the stored selector model."""
    return StoredRelationshipSelector(
        edge_type=cast(RelationshipEdgeType, selector.edge_type),
        ordinal=selector.ordinal,
        slug=selector.target_slug,
        version=selector.target_version,
        version_constraint=selector.version_constraint,
        optional=selector.optional,
        markers=tuple(selector.markers),
    )


def to_stored_skill_version(entity: SkillVersion) -> StoredSkillVersion:
    """Project one eagerly loaded ORM version into the stored detail model."""
    return StoredSkillVersion(
        slug=entity.skill.slug,
        version=entity.version,
        install_count=entity.skill.install_count,
        version_checksum_digest=entity.checksum_digest,
        content_checksum_digest=entity.content.checksum_digest,
        content_size_bytes=entity.content.storage_size_bytes,
        name=entity.metadata_row.name,
        description=entity.metadata_row.description,
        tags=tuple(entity.metadata_row.tags),
        inputs_schema=entity.metadata_row.inputs_schema,
        outputs_schema=entity.metadata_row.outputs_schema,
        token_estimate=entity.metadata_row.token_estimate,
        maturity_score=entity.metadata_row.maturity_score,
        security_score=entity.metadata_row.security_score,
        lifecycle_status=cast(LifecycleStatus, entity.lifecycle_status),
        trust_tier=cast(TrustTier, entity.trust_tier),
        provenance=to_provenance(entity),
        lifecycle_changed_at=entity.lifecycle_changed_at,
        published_at=entity.published_at,
        relationships=tuple(
            to_stored_selector(selector)
            for selector in sort_relationship_selectors(entity.relationship_selectors)
        ),
    )


def sort_relationship_selectors(
    selectors: list[SkillRelationshipSelector],
) -> list[SkillRelationshipSelector]:
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
) -> SkillSearchDocument:
    """Build the denormalized search row for one immutable version."""
    return SkillSearchDocument(
        skill_version_fk=skill_version_id,
        slug=slug,
        normalized_slug=normalize_text(slug),
        version=version,
        name=metadata.name,
        normalized_name=normalize_text(metadata.name),
        description=metadata.description,
        tags=list(metadata.tags),
        normalized_tags=sorted({normalize_text(tag) for tag in metadata.tags if tag.strip()}),
        lifecycle_status="published",
        trust_tier=governance.trust_tier,
        search_vector=cast(
            Any,
            func.to_tsvector(
                literal_column("'simple'::regconfig"),
                build_search_document_source(slug=slug, metadata=metadata),
            ),
        ),
        published_at=ensure_datetime(published_at),
        content_size_bytes=content_size_bytes,
        usage_count=0,
    )


def build_search_document_source(*, slug: str, metadata: MetadataRecordInput) -> str:
    """Combine immutable searchable fields into one deterministic text source."""
    parts = [normalize_text(slug), normalize_text(metadata.name)]
    if metadata.description is not None:
        parts.append(normalize_text(metadata.description))
    parts.extend(normalize_text(tag) for tag in metadata.tags)
    return " ".join(part for part in parts if part)


def is_duplicate_skill_version_error(error: IntegrityError) -> bool:
    """Return whether an integrity error represents the immutable version key."""
    message = str(error.orig).lower()
    return "uq_skill_versions_skill_fk_version" in message


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


def normalize_text(value: str) -> str:
    """Normalize a search document field into a compact lowercase value."""
    return " ".join(value.split()).strip().lower()


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
