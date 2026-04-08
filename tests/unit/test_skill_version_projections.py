"""Unit tests for shared stored-to-domain skill projections."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.governance import ProvenanceMetadata
from app.core.ports import StoredRelationshipSelector, StoredSkillVersion
from app.core.skills.projections import to_skill_version_detail


def _stored_version() -> StoredSkillVersion:
    return StoredSkillVersion(
        slug="python.lint",
        version="1.0.0",
        install_count=7,
        version_checksum_digest="version-digest",
        content_checksum_digest="content-digest",
        content_size_bytes=42,
        name="Python Lint",
        description="Checks Python code style.",
        tags=("python", "lint"),
        inputs_schema={"type": "object"},
        outputs_schema={"type": "object"},
        token_estimate=128,
        maturity_score=0.8,
        security_score=0.9,
        lifecycle_status="published",
        trust_tier="verified",
        provenance=ProvenanceMetadata(
            repo_url="https://github.com/acme/python-lint",
            commit_sha="0123456789abcdef0123456789abcdef01234567",
            tree_path="skills/python/lint",
            publisher_identity="ci/acme-release",
            policy_profile="default",
        ),
        lifecycle_changed_at=datetime(2026, 3, 13, 9, 0, tzinfo=UTC),
        published_at=datetime(2026, 3, 13, 9, 0, tzinfo=UTC),
        relationships=(
            StoredRelationshipSelector(
                edge_type="depends_on",
                ordinal=0,
                slug="python.base",
                version="2.0.0",
                version_constraint=None,
                optional=False,
                markers=("linux",),
            ),
        ),
    )


@pytest.mark.unit
def test_to_skill_version_detail_returns_immutable_metadata_without_relationships() -> None:
    detail = to_skill_version_detail(stored=_stored_version())

    assert detail.slug == "python.lint"
    assert detail.content.checksum.digest == "content-digest"
    assert not hasattr(detail.content, "rendered_summary")
    assert detail.install_count == 7
    assert detail.metadata.name == "Python Lint"
    assert not hasattr(detail.metadata, "headers")
    assert detail.lifecycle_status == "published"
    assert detail.published_at == datetime(2026, 3, 13, 9, 0, tzinfo=UTC)
    assert detail.provenance is not None
    assert detail.provenance.publisher_identity == "ci/acme-release"
    assert detail.provenance.policy_profile == "default"
