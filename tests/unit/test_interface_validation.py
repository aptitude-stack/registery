"""Unit tests for shared HTTP validation constants."""

from __future__ import annotations

import pytest

from app.interface.validation import MARKER_PATTERN, SLUG_PATTERN, VERSION_CONSTRAINT_PATTERN


@pytest.mark.unit
@pytest.mark.parametrize(
    ("value", "is_valid"),
    [
        ("python-lint", True),
        ("python.lint", False),
        ("python_lint", False),
        ("Python-Lint", False),
        ("python lint", False),
        ("", False),
    ],
)
def test_slug_pattern_matches_expected_values(value: str, *, is_valid: bool) -> None:
    assert (bool(__import__("re").fullmatch(SLUG_PATTERN, value))) is is_valid


@pytest.mark.unit
@pytest.mark.parametrize(
    ("value", "is_valid"),
    [
        (">=1.0.0", True),
        (">=1.0.0, <2.0.0", True),
        ("1.0.0", False),
        (">=1", False),
    ],
)
def test_version_constraint_pattern_matches_expected_values(
    value: str,
    *,
    is_valid: bool,
) -> None:
    assert (VERSION_CONSTRAINT_PATTERN.fullmatch(value) is not None) is is_valid


@pytest.mark.unit
@pytest.mark.parametrize(
    ("value", "is_valid"),
    [
        ("python:lint", True),
        ("py.lint-3", True),
        ("lint flag", False),
    ],
)
def test_marker_pattern_matches_expected_values(value: str, *, is_valid: bool) -> None:
    assert (MARKER_PATTERN.fullmatch(value) is not None) is is_valid
