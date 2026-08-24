"""Exact-fetch API mappers."""

from __future__ import annotations

from app.core.governance import TrustTier
from app.core.skills.models import (
    ProvenanceMetadata,
    SkillChecksum,
    SkillGraph,
    SkillMetadata,
    SkillVersionDetail,
    SkillVersionList,
    SkillVersionSummary,
)
from app.interface.dto.skills_fetch import (
    SkillGraphEdgeResponse,
    SkillGraphNodeResponse,
    SkillGraphResponse,
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


def to_metadata_response(
    detail: SkillVersionDetail,
    *,
    include_overall_score: bool = True,
) -> SkillVersionMetadataResponse:
    """Convert a core detail projection into the immutable metadata response schema."""
    return SkillVersionMetadataResponse(
        slug=detail.slug,
        version=detail.version,
        install_count=detail.install_count,
        star_count=detail.star_count,
        version_checksum=_checksum_response(detail.version_checksum),
        content=_content_summary_response(
            detail.content.checksum,
            media_type=detail.content.media_type,
            size_bytes=detail.content.size_bytes,
        ),
        metadata=_metadata_response(detail.metadata, include_overall_score=include_overall_score),
        lifecycle_status=detail.lifecycle_status,
        trust_tier=detail.trust_tier,
        namespace=detail.namespace,
        artifact_origin=detail.artifact_origin,
        review_state=detail.review_state,
        promotion_channel=detail.promotion_channel,
        policy_pack_slug=None if detail.policy_pack is None else detail.policy_pack.slug,
        provenance=_provenance_response(detail.provenance, trust_tier=detail.trust_tier),
        published_at=detail.published_at,
    )


def to_version_list_response(detail: SkillVersionList) -> SkillVersionListResponse:
    """Convert a core list projection into the public identity-level list schema."""
    return SkillVersionListResponse(
        slug=detail.slug,
        versions=[_version_summary_response(item) for item in detail.versions],
    )


def to_skill_graph_response(graph: SkillGraph) -> SkillGraphResponse:
    """Convert a core catalog graph projection into the public graph response schema."""
    return SkillGraphResponse(
        nodes=[
            SkillGraphNodeResponse(
                slug=node.slug,
                version=node.version,
                name=node.name,
                install_count=node.install_count,
                star_count=node.star_count,
                trust_tier=node.trust_tier,
                lifecycle_status=node.lifecycle_status,
            )
            for node in graph.nodes
        ],
        edges=[
            SkillGraphEdgeResponse(
                source_slug=edge.source_slug,
                target_slug=edge.target_slug,
                edge_type=edge.edge_type,
                provenance=edge.provenance,
                confidence=edge.confidence,
            )
            for edge in graph.edges
        ],
    )


def _checksum_response(checksum: SkillChecksum) -> ChecksumResponse:
    return ChecksumResponse(algorithm=checksum.algorithm, digest=checksum.digest)


def _content_summary_response(
    checksum: SkillChecksum,
    *,
    media_type: str,
    size_bytes: int,
) -> SkillContentSummaryResponse:
    return SkillContentSummaryResponse(
        checksum=_checksum_response(checksum),
        media_type=media_type,
        size_bytes=size_bytes,
    )


def _metadata_response(
    metadata: SkillMetadata,
    *,
    include_overall_score: bool = True,
) -> SkillMetadataResponse:
    response = SkillMetadataResponse(
        name=metadata.name,
        description=metadata.description,
        tags=list(metadata.tags),
        inputs_schema=metadata.inputs_schema,
        outputs_schema=metadata.outputs_schema,
        token_estimate=metadata.token_estimate,
        maturity_score=metadata.maturity_score,
        security_score=metadata.security_score,
    )
    if include_overall_score:
        response.overall_score = metadata.overall_score
    return response


def _version_summary_response(summary: SkillVersionSummary) -> SkillVersionSummaryResponse:
    return SkillVersionSummaryResponse(
        version=summary.version,
        lifecycle_status=summary.lifecycle_status,
        trust_tier=summary.trust_tier,
        namespace=summary.namespace,
        artifact_origin=summary.artifact_origin,
        review_state=summary.review_state,
        promotion_channel=summary.promotion_channel,
        policy_pack_slug=summary.policy_pack_slug,
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
