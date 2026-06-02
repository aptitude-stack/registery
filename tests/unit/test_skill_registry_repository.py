"""Unit coverage for persistence adapter helpers."""

from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy.exc import IntegrityError

from app.core.ports import (
    DuplicateSkillVersionPersistenceError,
    MetadataRecordInput,
)
from app.persistence.models.skill_relationship_selector import SkillRelationshipSelector
from app.persistence.skill_registry_repository_support import (
    SEARCH_CANDIDATES_SQL,
    build_contains_pattern,
    build_search_document_source,
    classify_integrity_error,
    sort_relationship_selectors,
)


def test_sort_relationship_selectors_uses_canonical_edge_family_order() -> None:
    selectors = [
        SkillRelationshipSelector(edge_type="overlaps_with", ordinal=0, target_slug="overlap"),
        SkillRelationshipSelector(edge_type="conflicts_with", ordinal=0, target_slug="conflict"),
        SkillRelationshipSelector(edge_type="extends", ordinal=1, target_slug="extends-1"),
        SkillRelationshipSelector(edge_type="depends_on", ordinal=1, target_slug="depends-1"),
        SkillRelationshipSelector(edge_type="extends", ordinal=0, target_slug="extends-0"),
        SkillRelationshipSelector(edge_type="depends_on", ordinal=0, target_slug="depends-0"),
    ]

    ordered = sort_relationship_selectors(selectors)

    assert [(item.edge_type, item.ordinal) for item in ordered] == [
        ("depends_on", 0),
        ("depends_on", 1),
        ("extends", 0),
        ("extends", 1),
        ("conflicts_with", 0),
        ("overlaps_with", 0),
    ]


def test_build_contains_pattern_normalizes_none_and_escapes_like_wildcards() -> None:
    assert build_contains_pattern(None) is None
    assert build_contains_pattern("python.discovery") == "%python.discovery%"
    assert build_contains_pattern(r"python\_%") == r"%python\\\_\%%"


def test_build_search_document_source_combines_searchable_fields() -> None:
    source = build_search_document_source(
        slug="Python.Discovery",
        metadata=MetadataRecordInput(
            name="  Python Hard Cut Source  ",
            description=" Hard cut discovery candidate ",
            tags=("Python", "hard-cut", "python"),
            inputs_schema=None,
            outputs_schema=None,
            token_estimate=None,
            maturity_score=None,
            security_score=None,
        ),
    )

    assert "python.discovery" in source
    assert "python hard cut source" in source
    assert "hard cut discovery candidate" in source
    assert "hard-cut" in source


def test_build_search_document_source_expands_known_search_aliases() -> None:
    source = build_search_document_source(
        slug="documentation-writing",
        metadata=MetadataRecordInput(
            name="Documentation Writing",
            description="Write long-form docs and reference guides.",
            tags=("documentation", "writing"),
            inputs_schema=None,
            outputs_schema=None,
            token_estimate=None,
            maturity_score=None,
            security_score=None,
        ),
    )

    assert "docs documentation" in source


def test_search_sql_uses_identity_query_separately_from_full_text_query() -> None:
    sql = " ".join(str(SEARCH_CANDIDATES_SQL).split())

    assert "doc.search_vector @@ plainto_tsquery(" in sql
    assert ":full_text_query_text" in sql
    assert "doc.normalized_slug = :identity_query_text" in sql
    assert "doc.normalized_name = :identity_query_text" in sql


def test_classify_integrity_error_returns_typed_duplicate_version_error() -> None:
    version_conflict = IntegrityError(
        statement="INSERT INTO skill_versions ...",
        params={},
        orig=SimpleNamespace(
            diag=SimpleNamespace(constraint_name="uq_skill_versions_skill_fk_version")
        ),
    )

    classified = classify_integrity_error(version_conflict)

    assert isinstance(classified, DuplicateSkillVersionPersistenceError)
