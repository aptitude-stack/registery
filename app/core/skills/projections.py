"""Shared stored-to-domain projections for immutable skill versions."""

from __future__ import annotations

from app.core.ports import StoredSkillVersion, StoredSkillVersionSummary

from .models import (
    SHA256_ALGORITHM,
    SkillChecksum,
    SkillContentSummary,
    SkillMetadata,
    SkillVersionDetail,
    SkillVersionSummary,
)


def to_skill_version_detail(*, stored: StoredSkillVersion) -> SkillVersionDetail:
    """Project one stored version into the shared detailed domain model."""
    return SkillVersionDetail(
        slug=stored.slug,
        version=stored.version,
        install_count=stored.install_count,
        version_checksum=SkillChecksum(
            algorithm=SHA256_ALGORITHM,
            digest=stored.version_checksum_digest,
        ),
        content=SkillContentSummary(
            checksum=SkillChecksum(
                algorithm=SHA256_ALGORITHM,
                digest=stored.content_checksum_digest,
            ),
            size_bytes=stored.content_size_bytes,
        ),
        metadata=SkillMetadata(
            name=stored.name,
            description=stored.description,
            tags=stored.tags,
            inputs_schema=stored.inputs_schema,
            outputs_schema=stored.outputs_schema,
            token_estimate=stored.token_estimate,
            maturity_score=stored.maturity_score,
            security_score=stored.security_score,
        ),
        lifecycle_status=stored.lifecycle_status,
        trust_tier=stored.trust_tier,
        provenance=stored.provenance,
        published_at=stored.published_at,
    )


def to_skill_version_summary(
    *,
    stored: StoredSkillVersionSummary,
    is_current_default: bool,
) -> SkillVersionSummary:
    """Project one stored summary row into the public list domain model."""
    return SkillVersionSummary(
        version=stored.version,
        lifecycle_status=stored.lifecycle_status,
        trust_tier=stored.trust_tier,
        published_at=stored.published_at,
        is_current_default=is_current_default,
    )
