"""Unit tests for exact immutable fetch behavior."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.governance import (
    CallerIdentity,
    GovernancePolicy,
    PolicyViolation,
    build_default_policy_profile,
)
from app.core.ports import (
    StoredSkillVersion,
    StoredSkillVersionContent,
    StoredSkillVersionSummary,
)
from app.core.skills.fetch import SkillFetchService
from app.core.skills.models import SkillNotFoundError, SkillVersionNotFoundError


class FakeAuditRecorder:
    """Collect audit events emitted by the fetch service."""

    def __init__(self) -> None:
        self.events: list[str] = []

    def record_event(self, *, event_type: str, payload: dict[str, object] | None = None) -> None:
        del payload
        self.events.append(event_type)


class FakeVersionReader:
    """Stub version reader keyed by exact immutable coordinates."""

    def __init__(
        self,
        *,
        version: StoredSkillVersion | None = None,
        content: StoredSkillVersionContent | None = None,
        versions: tuple[StoredSkillVersionSummary, ...] = (),
    ) -> None:
        self._version = version
        self._content = content
        self._versions = versions

    def get_version(self, *, slug: str, version: str) -> StoredSkillVersion | None:
        if self._version is None:
            return None
        if (self._version.slug, self._version.version) != (slug, version):
            return None
        return self._version

    def get_version_content(
        self,
        *,
        slug: str,
        version: str,
    ) -> StoredSkillVersionContent | None:
        if self._content is None:
            return None
        if (self._content.slug, self._content.version) != (slug, version):
            return None
        return self._content

    def list_versions(self, *, slug: str) -> tuple[StoredSkillVersionSummary, ...]:
        if any(item.slug != slug for item in self._versions):
            return ()
        return self._versions


class FakeInstallCounter:
    """Collect install-tracking calls made by the fetch service."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def record_install(self, *, slug: str, version: str) -> None:
        self.calls.append((slug, version))


def _governance_policy() -> GovernancePolicy:
    return GovernancePolicy(profile=build_default_policy_profile())


def _caller(*scopes: str) -> CallerIdentity:
    return CallerIdentity(token="token", scopes=frozenset(scopes))


def _stored_version(*, lifecycle_status: str = "published") -> StoredSkillVersion:
    return StoredSkillVersion(
        slug="python.lint",
        version="1.0.0",
        install_count=0,
        version_checksum_digest="version-digest",
        content_checksum_digest="content-digest",
        content_size_bytes=18,
        name="Python Lint",
        description="Linting skill",
        tags=("python", "lint"),
        inputs_schema={"type": "object"},
        outputs_schema={"type": "object"},
        token_estimate=128,
        maturity_score=0.9,
        security_score=0.95,
        lifecycle_status=lifecycle_status,
        trust_tier="internal",
        provenance=None,
        lifecycle_changed_at=datetime(2026, 3, 13, 9, 0, tzinfo=UTC),
        published_at=datetime(2026, 3, 13, 9, 0, tzinfo=UTC),
        relationships=(),
    )


def _stored_content(*, lifecycle_status: str = "published") -> StoredSkillVersionContent:
    return StoredSkillVersionContent(
        slug="python.lint",
        version="1.0.0",
        raw_markdown="# Python Lint\n",
        checksum_digest="content-digest",
        size_bytes=len(b"# Python Lint\n"),
        lifecycle_status=lifecycle_status,
        trust_tier="internal",
    )


def _stored_version_summary(
    version: str,
    *,
    lifecycle_status: str = "published",
    published_at: datetime | None = None,
) -> StoredSkillVersionSummary:
    return StoredSkillVersionSummary(
        slug="python.lint",
        version=version,
        lifecycle_status=lifecycle_status,
        trust_tier="internal",
        published_at=published_at or datetime(2026, 3, 13, 9, 0, tzinfo=UTC),
    )


@pytest.mark.unit
def test_get_version_metadata_returns_immutable_detail() -> None:
    audit_recorder = FakeAuditRecorder()
    service = SkillFetchService(
        version_reader=FakeVersionReader(version=_stored_version()),
        audit_recorder=audit_recorder,
        governance_policy=_governance_policy(),
        install_counter=FakeInstallCounter(),
    )

    detail = service.get_version_metadata(
        caller=_caller("read"),
        slug="python.lint",
        version="1.0.0",
    )

    assert detail.slug == "python.lint"
    assert detail.version == "1.0.0"
    assert detail.content.checksum.digest == "content-digest"
    assert not hasattr(detail.metadata, "headers")
    assert audit_recorder.events == ["skill.version_metadata_read"]


@pytest.mark.unit
def test_get_content_returns_markdown_document() -> None:
    audit_recorder = FakeAuditRecorder()
    install_counter = FakeInstallCounter()
    service = SkillFetchService(
        version_reader=FakeVersionReader(content=_stored_content()),
        audit_recorder=audit_recorder,
        governance_policy=_governance_policy(),
        install_counter=install_counter,
    )

    document = service.get_content(
        caller=_caller("read"),
        slug="python.lint",
        version="1.0.0",
    )

    assert document.raw_markdown == "# Python Lint\n"
    assert document.checksum.digest == "content-digest"
    assert document.size_bytes == len(b"# Python Lint\n")
    assert audit_recorder.events == ["skill.version_content_read"]
    assert install_counter.calls == [("python.lint", "1.0.0")]


@pytest.mark.unit
def test_get_version_metadata_raises_not_found_for_unknown_coordinate() -> None:
    service = SkillFetchService(
        version_reader=FakeVersionReader(),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
        install_counter=FakeInstallCounter(),
    )

    with pytest.raises(SkillVersionNotFoundError):
        service.get_version_metadata(
            caller=_caller("read"),
            slug="python.missing",
            version="9.9.9",
        )


@pytest.mark.unit
def test_get_content_applies_exact_read_policy() -> None:
    audit_recorder = FakeAuditRecorder()
    install_counter = FakeInstallCounter()
    service = SkillFetchService(
        version_reader=FakeVersionReader(content=_stored_content(lifecycle_status="archived")),
        audit_recorder=audit_recorder,
        governance_policy=_governance_policy(),
        install_counter=install_counter,
    )

    with pytest.raises(PolicyViolation):
        service.get_content(
            caller=_caller("read"),
            slug="python.lint",
            version="1.0.0",
        )

    assert audit_recorder.events == ["skill.version_exact_read_denied"]
    assert install_counter.calls == []


@pytest.mark.unit
def test_list_versions_returns_visible_versions_with_current_default_first() -> None:
    audit_recorder = FakeAuditRecorder()
    service = SkillFetchService(
        version_reader=FakeVersionReader(
            versions=(
                _stored_version_summary("2.0.0", lifecycle_status="published"),
                _stored_version_summary(
                    "1.0.0",
                    lifecycle_status="deprecated",
                    published_at=datetime(2026, 3, 12, 9, 0, tzinfo=UTC),
                ),
            )
        ),
        audit_recorder=audit_recorder,
        governance_policy=_governance_policy(),
        install_counter=FakeInstallCounter(),
    )

    result = service.list_versions(caller=_caller("read"), slug="python.lint")

    assert result.slug == "python.lint"
    assert [item.version for item in result.versions] == ["2.0.0", "1.0.0"]
    assert result.versions[0].is_current_default is True
    assert result.versions[1].is_current_default is False
    assert audit_recorder.events == ["skill.version_list_read"]


@pytest.mark.unit
def test_list_versions_hides_fully_invisible_skills() -> None:
    service = SkillFetchService(
        version_reader=FakeVersionReader(
            versions=(_stored_version_summary("1.0.0", lifecycle_status="archived"),)
        ),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
        install_counter=FakeInstallCounter(),
    )

    with pytest.raises(SkillNotFoundError):
        service.list_versions(caller=_caller("read"), slug="python.lint")


@pytest.mark.unit
def test_list_versions_includes_archived_versions_for_admin_without_marking_default() -> None:
    service = SkillFetchService(
        version_reader=FakeVersionReader(
            versions=(
                _stored_version_summary("2.0.0", lifecycle_status="archived"),
                _stored_version_summary(
                    "1.0.0",
                    lifecycle_status="deprecated",
                    published_at=datetime(2026, 3, 12, 9, 0, tzinfo=UTC),
                ),
            )
        ),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
        install_counter=FakeInstallCounter(),
    )

    result = service.list_versions(caller=_caller("admin"), slug="python.lint")

    assert [item.version for item in result.versions] == ["1.0.0", "2.0.0"]
    assert result.versions[0].is_current_default is True
    assert result.versions[1].is_current_default is False


@pytest.mark.unit
def test_list_versions_uses_version_as_final_tie_break_for_current_default() -> None:
    published_at = datetime(2026, 3, 13, 9, 0, tzinfo=UTC)
    service = SkillFetchService(
        version_reader=FakeVersionReader(
            versions=(
                _stored_version_summary(
                    "2.0.0",
                    lifecycle_status="deprecated",
                    published_at=published_at,
                ),
                _stored_version_summary(
                    "1.0.0",
                    lifecycle_status="deprecated",
                    published_at=published_at,
                ),
            )
        ),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
        install_counter=FakeInstallCounter(),
    )

    result = service.list_versions(caller=_caller("read"), slug="python.lint")

    assert [item.version for item in result.versions] == ["1.0.0", "2.0.0"]
    assert result.versions[0].is_current_default is True
    assert result.versions[1].is_current_default is False
