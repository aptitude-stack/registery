"""Regression coverage for the rich demo catalog fixtures."""

from __future__ import annotations

from app.bootstrap.demo_catalog import build_demo_catalog


def test_demo_catalog_contains_expected_versions_relationships_and_sections() -> None:
    catalog = build_demo_catalog()

    assert len(catalog) == 10

    by_coordinate = {(entry.command.slug, entry.command.version): entry for entry in catalog}
    assert set(by_coordinate) == {
        ("python.base", "1.0.0"),
        ("python.base", "1.1.0"),
        ("python.lint", "1.0.0"),
        ("python.lint", "2.0.0"),
        ("python.format", "1.0.0"),
        ("python.format", "2.0.0"),
        ("python.test", "1.0.0"),
        ("python.security.scan", "1.0.0"),
        ("python.legacy.audit", "0.9.0"),
        ("python.bundle.code-quality", "1.0.0"),
    }

    lint_v1 = by_coordinate[("python.lint", "1.0.0")]
    lint_v2 = by_coordinate[("python.lint", "2.0.0")]
    format_v1 = by_coordinate[("python.format", "1.0.0")]
    test_v1 = by_coordinate[("python.test", "1.0.0")]
    security_v1 = by_coordinate[("python.security.scan", "1.0.0")]
    legacy_v1 = by_coordinate[("python.legacy.audit", "0.9.0")]
    bundle_v1 = by_coordinate[("python.bundle.code-quality", "1.0.0")]

    assert lint_v1.desired_lifecycle_status == "deprecated"
    assert lint_v2.desired_lifecycle_status == "published"
    assert format_v1.desired_lifecycle_status == "archived"
    assert legacy_v1.desired_lifecycle_status == "deprecated"

    assert lint_v2.command.relationships.depends_on[0].slug == "python.base"
    assert lint_v2.command.relationships.depends_on[0].version_constraint == ">=1.0.0,<2.0.0"
    assert lint_v2.command.relationships.extends[0].slug == "python.base"
    assert lint_v2.command.relationships.extends[0].version == "1.1.0"
    assert lint_v2.command.relationships.overlaps_with[0].slug == "python.format"
    assert lint_v2.command.relationships.overlaps_with[0].version == "2.0.0"

    assert test_v1.command.governance.trust_tier == "verified"
    assert test_v1.command.relationships.depends_on[0].slug == "python.base"
    assert test_v1.command.relationships.depends_on[0].version == "1.1.0"
    assert test_v1.command.relationships.depends_on[1].slug == "python.lint"
    assert test_v1.command.relationships.depends_on[1].version_constraint == ">=2.0.0,<3.0.0"
    assert test_v1.command.relationships.depends_on[1].optional is True
    assert test_v1.command.relationships.depends_on[1].markers == ("ci", "linux")

    assert security_v1.command.governance.trust_tier == "verified"
    assert security_v1.command.relationships.conflicts_with[0].slug == "python.legacy.audit"
    assert security_v1.command.relationships.conflicts_with[0].version == "0.9.0"

    assert bundle_v1.command.relationships.depends_on[0].slug == "python.lint"
    assert bundle_v1.command.relationships.depends_on[1].slug == "python.format"
    assert bundle_v1.command.relationships.depends_on[2].slug == "python.test"
    assert bundle_v1.command.relationships.depends_on[2].version_constraint == ">=1.0.0,<2.0.0"
    assert bundle_v1.command.relationships.extends[0].version == "1.1.0"

    for entry in catalog:
        markdown = entry.command.content.raw_markdown
        assert len(markdown) > 900
        assert "# " in markdown
        assert "## Purpose" in markdown
        assert "## When To Use" in markdown
        assert "## Prerequisites" in markdown
        assert "## Inputs" in markdown
        assert "## Outputs" in markdown
        assert "## Step-By-Step Flow" in markdown
        assert "## Examples" in markdown
        assert "## Failure Modes" in markdown
        assert "## Version Notes" in markdown
