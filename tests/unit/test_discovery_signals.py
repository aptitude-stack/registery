"""Unit tests for hybrid discovery signal helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.governance import LifecycleStatus, PromotionChannel, ReviewState, TrustTier
from app.core.ports import StoredSkillSearchCandidate
from app.intelligence.discovery_signals import (
    build_embedding_source,
    build_source_checksum_digest,
    fuse_discovery_candidates,
    validate_embedding_vector,
)


def _candidate(
    slug: str,
    *,
    exact_slug_match: bool = False,
    exact_name_match: bool = False,
    lexical_score: float = 0.0,
    tag_overlap_count: int = 0,
    usage_count: int = 0,
) -> StoredSkillSearchCandidate:
    return StoredSkillSearchCandidate(
        skill_version_fk=1,
        slug=slug,
        version="1.0.0",
        name=slug.replace(".", " ").title(),
        description=None,
        tags=(),
        lifecycle_status="published",
        trust_tier="internal",
        namespace="public",
        artifact_origin="internal",
        review_state="approved",
        promotion_channel="prod",
        policy_pack=None,
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        content_size_bytes=100,
        usage_count=usage_count,
        exact_slug_match=exact_slug_match,
        exact_name_match=exact_name_match,
        lexical_score=lexical_score,
        tag_overlap_count=tag_overlap_count,
    )


@pytest.mark.unit
def test_embedding_source_is_metadata_only_and_checksum_is_stable() -> None:
    source = build_embedding_source(
        slug="Python.Lint",
        name=" Python Lint ",
        description="  Static checks for Python codebases  ",
        tags=("Lint", "python", "lint"),
    )

    assert source == "python.lint python lint static checks for python codebases lint python"
    assert build_source_checksum_digest(source) == build_source_checksum_digest(source)


@pytest.mark.unit
def test_validate_embedding_vector_rejects_wrong_dimensions_and_non_finite_values() -> None:
    assert validate_embedding_vector((0.1, 0.2), dimensions=2) == (0.1, 0.2)

    with pytest.raises(ValueError, match="1536"):
        validate_embedding_vector((0.1, 0.2), dimensions=1536)

    with pytest.raises(ValueError, match="finite"):
        validate_embedding_vector((float("nan"),), dimensions=1)


@pytest.mark.unit
def test_fusion_keeps_exact_and_lexical_primary_before_semantic_expansion() -> None:
    exact = _candidate("python.lint", exact_slug_match=True, lexical_score=1.0)
    strong_lexical = _candidate("python.format", lexical_score=0.8)
    weak_lexical = _candidate("python.style", lexical_score=0.1)
    semantic_only = _candidate("python.static-analysis")

    fused = fuse_discovery_candidates(
        lexical_candidates=(exact, strong_lexical, weak_lexical),
        semantic_candidates=(semantic_only, weak_lexical),
        co_usage_boosts={},
        limit=20,
    )

    assert tuple(item.slug for item in fused) == (
        "python.lint",
        "python.format",
        "python.style",
        "python.static-analysis",
    )


@pytest.mark.unit
def test_co_usage_boost_is_capped_and_cannot_outrank_exact_matches() -> None:
    exact = _candidate("python.lint", exact_slug_match=True, lexical_score=1.0)
    related = _candidate("python.pytest", lexical_score=0.2)
    unrelated = _candidate("python.docs", lexical_score=0.3)

    fused = fuse_discovery_candidates(
        lexical_candidates=(exact, unrelated, related),
        semantic_candidates=(),
        co_usage_boosts={"python.pytest": 100.0},
        limit=20,
    )

    assert tuple(item.slug for item in fused) == (
        "python.lint",
        "python.pytest",
        "python.docs",
    )


def test_candidate_literal_types_stay_visible_to_type_checkers() -> None:
    candidate = _candidate("python.types")

    lifecycle: LifecycleStatus = candidate.lifecycle_status
    trust: TrustTier = candidate.trust_tier
    review: ReviewState = candidate.review_state
    promotion: PromotionChannel = candidate.promotion_channel

    assert (lifecycle, trust, review, promotion) == (
        "published",
        "internal",
        "approved",
        "prod",
    )
