"""Unit tests for pure search normalization and explanation helpers."""

from __future__ import annotations

import pytest

from app.intelligence.search_ranking import (
    build_search_audit_payload,
    build_search_explanation,
    normalize_search_request,
)


@pytest.mark.unit
def test_normalize_search_request_merges_language_into_effective_tags() -> None:
    normalized = normalize_search_request(
        q="  Python Lint  ",
        tags=("Lint", "python", "lint"),
        language=" Python ",
        fresh_within_days=7,
        max_footprint_bytes=1024,
        limit=20,
    )

    assert normalized.query_text == "python lint"
    assert normalized.query_terms == ("python", "lint")
    assert normalized.tags == ("lint", "python")
    assert normalized.language == "python"
    assert normalized.effective_tags == ("lint", "python")


@pytest.mark.unit
def test_build_search_explanation_tracks_text_and_tag_matches() -> None:
    explanation = build_search_explanation(
        query_terms=("python", "lint"),
        requested_tags=("python",),
        slug="python-lint",
        name="Python Lint",
        description="Linting skill for Python codebases",
        tags=("python", "lint"),
        exact_slug_match=False,
        exact_name_match=False,
        lexical_score=0.42,
        tag_overlap_count=1,
    )

    assert explanation.matched_fields == ("slug", "name", "description", "tags")
    assert explanation.matched_tags == ("python",)
    assert explanation.reasons == ("text_match", "tag_filter_match")


@pytest.mark.unit
def test_build_search_audit_payload_redacts_raw_values() -> None:
    request = normalize_search_request(
        q="secret query",
        tags=("private-tag",),
        language=None,
        fresh_within_days=None,
        max_footprint_bytes=2048,
        limit=10,
    )

    payload = build_search_audit_payload(request=request, result_count=3)

    assert payload == {
        "query_present": True,
        "tag_count": 1,
        "language_present": False,
        "fresh_within_days_present": False,
        "max_footprint_bytes_present": True,
        "limit": 10,
        "result_count": 3,
    }
    assert "secret query" not in str(payload)
    assert "private-tag" not in str(payload)
