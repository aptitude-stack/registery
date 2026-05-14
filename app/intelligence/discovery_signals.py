"""Pure helpers for lexical-primary discovery expansion signals."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

from app.core.ports import StoredSkillSearchCandidate
from app.core.skills.normalization import normalize_search_text, normalize_tag_list

SOURCE_CHECKSUM_ALGORITHM = "sha256"
DEFAULT_CO_USAGE_BOOST_CAP = 0.05


@dataclass(frozen=True, slots=True)
class _RankedCandidate:
    candidate: StoredSkillSearchCandidate
    lexical_rank: int | None
    semantic_rank: int | None
    co_usage_boost: float


def build_embedding_source(
    *,
    slug: str,
    name: str,
    description: str | None,
    tags: tuple[str, ...],
) -> str:
    """Return the description/tag text source used for semantic indexing."""
    del slug, name
    source = build_semantic_query_source(description=description, tags=tags)
    return source or ""


def build_semantic_query_source(
    *,
    description: str | None,
    tags: tuple[str, ...],
) -> str | None:
    """Return normalized description/tag text used for semantic query embeddings."""
    parts: list[str] = []
    if description is not None:
        parts.append(normalize_search_text(description) or "")
    parts.extend(normalize_tag_list(tags))
    source = " ".join(part for part in parts if part)
    return source or None


def build_source_checksum_digest(source: str) -> str:
    """Return a stable checksum for one embedding source string."""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def validate_embedding_vector(
    values: tuple[float, ...],
    *,
    dimensions: int,
) -> tuple[float, ...]:
    """Validate one embedding vector before persistence or query use."""
    if len(values) != dimensions:
        raise ValueError(f"Embedding vector must contain exactly {dimensions} dimensions.")
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Embedding vector values must be finite.")
    return values


def serialize_embedding_vector(values: tuple[float, ...]) -> str:
    """Return pgvector-compatible text representation for a validated vector."""
    return "[" + ",".join(str(value) for value in values) + "]"


def fuse_discovery_candidates(
    *,
    lexical_candidates: tuple[StoredSkillSearchCandidate, ...],
    semantic_candidates: tuple[StoredSkillSearchCandidate, ...],
    co_usage_boosts: dict[str, float],
    limit: int,
    co_usage_boost_cap: float = DEFAULT_CO_USAGE_BOOST_CAP,
) -> tuple[StoredSkillSearchCandidate, ...]:
    """Return candidates fused across lexical, semantic, and bounded boost signals."""
    ranked: dict[str, _RankedCandidate] = {}
    for index, candidate in enumerate(lexical_candidates, start=1):
        ranked[candidate.slug] = _RankedCandidate(
            candidate=candidate,
            lexical_rank=index,
            semantic_rank=None,
            co_usage_boost=_bounded_boost(
                co_usage_boosts.get(candidate.slug, 0.0),
                cap=co_usage_boost_cap,
            ),
        )

    for index, candidate in enumerate(semantic_candidates, start=1):
        existing = ranked.get(candidate.slug)
        if existing is None:
            ranked[candidate.slug] = _RankedCandidate(
                candidate=candidate,
                lexical_rank=None,
                semantic_rank=index,
                co_usage_boost=_bounded_boost(
                    co_usage_boosts.get(candidate.slug, 0.0),
                    cap=co_usage_boost_cap,
                ),
            )
            continue
        ranked[candidate.slug] = _RankedCandidate(
            candidate=existing.candidate,
            lexical_rank=existing.lexical_rank,
            semantic_rank=index,
            co_usage_boost=existing.co_usage_boost,
        )

    ordered = sorted(ranked.values(), key=_sort_key)
    return tuple(item.candidate for item in ordered[:limit])


def _bounded_boost(value: float, *, cap: float) -> float:
    return min(max(value, 0.0), cap)


def _sort_key(item: _RankedCandidate) -> tuple[object, ...]:
    candidate = item.candidate
    lexical_component = 0.0
    if item.lexical_rank is not None:
        lexical_component = 1.0 / (item.lexical_rank + 60)
    semantic_component = 0.0
    if item.semantic_rank is not None:
        semantic_component = 1.0 / (item.semantic_rank + 60)
    fused_score = lexical_component + semantic_component + item.co_usage_boost

    return (
        not candidate.exact_slug_match,
        not candidate.exact_name_match,
        -fused_score,
        -candidate.tag_overlap_count,
        -candidate.usage_count,
        -candidate.published_at.timestamp(),
        candidate.content_size_bytes,
        candidate.slug,
        -candidate.skill_version_fk,
    )
