"""Pure search normalization and explanation helpers."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.skills.normalization import normalize_search_text, normalize_tag, normalize_tag_list


@dataclass(frozen=True, slots=True)
class NormalizedSkillSearchRequest:
    """Pure normalized representation of a search request."""

    query_text: str | None
    query_terms: tuple[str, ...]
    tags: tuple[str, ...]
    language: str | None
    effective_tags: tuple[str, ...]
    fresh_within_days: int | None
    max_footprint_bytes: int | None
    limit: int


@dataclass(frozen=True, slots=True)
class SearchExplanation:
    """Deterministic explanation fields returned to API consumers."""

    matched_fields: tuple[str, ...]
    matched_tags: tuple[str, ...]
    reasons: tuple[str, ...]


def tokenize_query(query_text: str | None) -> tuple[str, ...]:
    """Split normalized query text into deduplicated terms."""
    if query_text is None:
        return ()

    return tuple(dict.fromkeys(query_text.split()))


def normalize_search_request(
    *,
    q: str | None,
    tags: tuple[str, ...],
    language: str | None,
    fresh_within_days: int | None,
    max_footprint_bytes: int | None,
    limit: int,
) -> NormalizedSkillSearchRequest:
    """Normalize external search inputs into a deterministic internal shape."""
    normalized_query = normalize_search_text(q)
    normalized_tags = normalize_tag_list(tags)
    normalized_language = normalize_tag(language)
    effective_values: tuple[str, ...] = normalized_tags
    if normalized_language is not None:
        effective_values = (*effective_values, normalized_language)
    effective_tags = normalize_tag_list(effective_values)

    return NormalizedSkillSearchRequest(
        query_text=normalized_query,
        query_terms=tokenize_query(normalized_query),
        tags=normalized_tags,
        language=normalized_language,
        effective_tags=effective_tags,
        fresh_within_days=fresh_within_days,
        max_footprint_bytes=max_footprint_bytes,
        limit=limit,
    )


def build_search_explanation(
    *,
    query_terms: tuple[str, ...],
    requested_tags: tuple[str, ...],
    slug: str,
    name: str,
    description: str | None,
    tags: tuple[str, ...],
    exact_slug_match: bool,
    exact_name_match: bool,
    lexical_score: float,
    tag_overlap_count: int,
) -> SearchExplanation:
    """Build stable explanation fields from ranking inputs."""
    normalized_slug = normalize_search_text(slug) or ""
    normalized_name = normalize_search_text(name) or ""
    normalized_description = normalize_search_text(description) or ""
    normalized_tags = normalize_tag_list(tags)

    matched_fields: list[str] = []
    if exact_slug_match or any(term in normalized_slug for term in query_terms):
        matched_fields.append("slug")
    if exact_name_match or any(term in normalized_name for term in query_terms):
        matched_fields.append("name")
    if normalized_description and any(term in normalized_description for term in query_terms):
        matched_fields.append("description")
    if normalized_tags and any(term in normalized_tags for term in query_terms):
        matched_fields.append("tags")

    matched_tags = tuple(sorted(set(normalized_tags).intersection(requested_tags)))
    if matched_tags:
        matched_fields.append("tags")

    reasons: list[str] = []
    if exact_slug_match:
        reasons.append("exact_slug_match")
    if exact_name_match:
        reasons.append("exact_name_match")
    if lexical_score > 0:
        reasons.append("text_match")
    if tag_overlap_count > 0:
        reasons.append("tag_filter_match")
    if not reasons:
        reasons.append("structured_filter_match")

    return SearchExplanation(
        matched_fields=tuple(dict.fromkeys(matched_fields)),
        matched_tags=matched_tags,
        reasons=tuple(reasons),
    )


def build_search_audit_payload(
    *,
    request: NormalizedSkillSearchRequest,
    result_count: int,
) -> dict[str, int | bool]:
    """Return a redacted audit payload for search activity."""
    return {
        "query_present": request.query_text is not None,
        "tag_count": len(request.tags),
        "language_present": request.language is not None,
        "fresh_within_days_present": request.fresh_within_days is not None,
        "max_footprint_bytes_present": request.max_footprint_bytes is not None,
        "limit": request.limit,
        "result_count": result_count,
    }
