"""Unit tests for shared skill normalization helpers."""

from __future__ import annotations

from app.core.ports import MetadataRecordInput
from app.core.skills.normalization import (
    expand_search_aliases,
    normalize_search_text,
    normalize_tag_list,
)
from app.intelligence.search_ranking import normalize_search_request
from app.persistence.skill_registry_repository_support import build_search_document_source


def test_shared_normalization_aligns_search_documents_and_queries() -> None:
    document_source = build_search_document_source(
        slug="  Python-Lint  ",
        metadata=MetadataRecordInput(
            name=" Python   Lint ",
            description="  Lint Python files  ",
            tags=("Lint", "python", "lint"),
            token_estimate=None,
            maturity_score=None,
            security_score=None,
        ),
    )
    normalized_request = normalize_search_request(
        q=" Python  Lint ",
        tags=("Lint", "python", "lint"),
        language=" Python ",
        fresh_within_days=None,
        max_footprint_bytes=None,
        limit=20,
    )

    assert normalize_search_text(" Python  Lint ") == "python lint"
    assert normalize_tag_list(("Lint", "python", "lint")) == ("lint", "python")
    assert "python-lint" in document_source
    assert normalized_request.query_text == "python lint"
    assert normalized_request.full_text_query_text == "python lint"
    assert normalized_request.effective_tags == ("lint", "python")


def test_search_alias_expansion_is_deterministic_and_deduplicated() -> None:
    assert expand_search_aliases("docs doc documentation writing") == (
        "docs documentation doc writing"
    )

    normalized_request = normalize_search_request(
        q="docs",
        tags=(),
        language=None,
        fresh_within_days=None,
        max_footprint_bytes=None,
        limit=20,
    )

    assert normalized_request.query_text == "docs"
    assert normalized_request.full_text_query_text == "docs documentation"
