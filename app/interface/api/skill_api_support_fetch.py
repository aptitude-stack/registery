"""Exact-fetch API mappers."""

from __future__ import annotations

from app.core.governance import TrustTier
from app.core.skills.models import (
    ProvenanceMetadata,
    SkillChecksum,
    SkillMetadata,
    SkillVersionDetail,
    SkillVersionList,
    SkillVersionSummary,
)
from app.interface.dto.skills_fetch import (
    SkillVersionListResponse,
    SkillVersionMetadataResponse,
    SkillVersionSummaryResponse,
)
from app.interface.dto.skills_shared import (
    ChecksumResponse,
    ProvenanceResponse,
    SkillContentSummaryResponse,
    SkillMetadataResponse,
    TrustContextResponse,
)


def to_metadata_response(detail: SkillVersionDetail) -> SkillVersionMetadataResponse:
    """Convert a core detail projection into the immutable metadata response schema."""
    return SkillVersionMetadataResponse(
        slug=detail.slug,
        version=detail.version,
        install_count=detail.install_count,
        version_checksum=_checksum_response(detail.version_checksum),
        content=_content_summary_response(detail.content.checksum, detail.content.size_bytes),
        metadata=_metadata_response(detail.metadata),
        lifecycle_status=detail.lifecycle_status,
        trust_tier=detail.trust_tier,
        provenance=_provenance_response(detail.provenance, trust_tier=detail.trust_tier),
        published_at=detail.published_at,
    )


def to_version_list_response(detail: SkillVersionList) -> SkillVersionListResponse:
    """Convert a core list projection into the public identity-level list schema."""
    return SkillVersionListResponse(
        slug=detail.slug,
        versions=[_version_summary_response(item) for item in detail.versions],
    )


def _checksum_response(checksum: SkillChecksum) -> ChecksumResponse:
    return ChecksumResponse(algorithm=checksum.algorithm, digest=checksum.digest)


def _content_summary_response(
    checksum: SkillChecksum,
    size_bytes: int,
) -> SkillContentSummaryResponse:
    return SkillContentSummaryResponse(
        checksum=_checksum_response(checksum),
        size_bytes=size_bytes,
    )


def _metadata_response(metadata: SkillMetadata) -> SkillMetadataResponse:
    return SkillMetadataResponse(
        name=metadata.name,
        description=metadata.description,
        tags=list(metadata.tags),
        inputs_schema=metadata.inputs_schema,
        outputs_schema=metadata.outputs_schema,
        token_estimate=metadata.token_estimate,
        maturity_score=metadata.maturity_score,
        security_score=metadata.security_score,
    )


def _version_summary_response(summary: SkillVersionSummary) -> SkillVersionSummaryResponse:
    return SkillVersionSummaryResponse(
        version=summary.version,
        lifecycle_status=summary.lifecycle_status,
        trust_tier=summary.trust_tier,
        published_at=summary.published_at,
        is_current_default=summary.is_current_default,
    )


def _provenance_response(
    provenance: ProvenanceMetadata | None,
    *,
    trust_tier: TrustTier,
) -> ProvenanceResponse | None:
    if provenance is None:
        return None
    return ProvenanceResponse(
        repo_url=provenance.repo_url,
        commit_sha=provenance.commit_sha,
        tree_path=provenance.tree_path,
        publisher_identity=provenance.publisher_identity,
        trust_context=(
            None
            if provenance.policy_profile is None
            else TrustContextResponse(
                trust_tier=trust_tier,
                policy_profile=provenance.policy_profile,
            )
        ),
    )
