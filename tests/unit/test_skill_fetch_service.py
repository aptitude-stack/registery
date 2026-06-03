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
from app.core.skills.bundle_archive import SKILL_ARTIFACT_MEDIA_TYPE, build_skill_bundle
from app.core.skills.discovery import SkillDiscoveryRequest
from app.core.skills.fetch import SkillFetchService
from app.core.skills.models import (
    SkillChecksum,
    SkillContentRecord,
    SkillContentSummary,
    SkillGraphEdge,
    SkillMetadata,
    SkillNotFoundError,
    SkillVersionDetail,
    SkillVersionListEntry,
    SkillVersionNotFoundError,
)


class FakeAuditRecorder:
    """Collect audit events emitted by the fetch service."""

    def __init__(self) -> None:
        self.events: list[str] = []

    def record_event(self, *, event_type: str, payload: dict[str, object] | None = None) -> None:
        del payload
        self.events.append(event_type)


class FakeCatalogRepository:
    """Stub catalog repository keyed by exact immutable coordinates."""

    def __init__(
        self,
        *,
        version: SkillVersionDetail | None = None,
        content: SkillContentRecord | None = None,
        versions: tuple[SkillVersionListEntry, ...] = (),
        top_versions: tuple[SkillVersionDetail, ...] = (),
        details: tuple[SkillVersionDetail, ...] = (),
        graph_edges: tuple[SkillGraphEdge, ...] = (),
    ) -> None:
        self._version = version
        self._content = content
        self._versions = versions
        self._top_versions = top_versions
        self._details = details
        self._graph_edges = graph_edges
        self.install_calls: list[tuple[str, str]] = []

    def get_version_detail(self, *, slug: str, version: str) -> SkillVersionDetail | None:
        for detail in self._details:
            if (detail.slug, detail.version) == (slug, version):
                return detail
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
    ) -> SkillContentRecord | None:
        if self._content is None:
            return None
        if (self._content.slug, self._content.version) != (slug, version):
            return None
        return self._content

    def list_versions(self, *, slug: str) -> tuple[SkillVersionListEntry, ...]:
        return tuple(item for item in self._versions if item.slug == slug)

    def list_top_installed_versions(self, *, limit: int) -> tuple[SkillVersionDetail, ...]:
        return self._top_versions[:limit]

    def list_catalog_skill_versions(self) -> tuple[SkillVersionDetail, ...]:
        return self._top_versions

    def list_skill_graph_edges(
        self,
        *,
        sources: tuple[tuple[str, str], ...],
        edge_types: tuple[str, ...],
    ) -> tuple[SkillGraphEdge, ...]:
        source_set = set(sources)
        edge_type_set = set(edge_types)
        return tuple(
            edge
            for edge in self._graph_edges
            if (edge.source_slug, edge.source_version) in source_set
            and edge.edge_type in edge_type_set
        )

    def record_install(self, *, slug: str, version: str) -> None:
        self.install_calls.append((slug, version))


class FakeDiscoveryService:
    """Stub discovery service that returns fixed slug order."""

    def __init__(self, candidates: tuple[str, ...]) -> None:
        self.candidates = candidates

    def discover_candidates(self, *, caller: CallerIdentity, request: object) -> tuple[str, ...]:
        del caller, request
        return self.candidates


def _governance_policy() -> GovernancePolicy:
    return GovernancePolicy(profile=build_default_policy_profile())


def _caller(*scopes: str) -> CallerIdentity:
    return CallerIdentity(token_id="token", scopes=frozenset(scopes))


def _stored_version(
    *,
    slug: str = "python-lint",
    version: str = "1.0.0",
    lifecycle_status: str = "published",
) -> SkillVersionDetail:
    return SkillVersionDetail(
        slug=slug,
        version=version,
        install_count=0,
        version_checksum=SkillChecksum(algorithm="sha256", digest="version-digest"),
        content=SkillContentSummary(
            checksum=SkillChecksum(algorithm="sha256", digest="content-digest"),
            media_type=SKILL_ARTIFACT_MEDIA_TYPE,
            size_bytes=len(build_skill_bundle("# Python Lint\n")),
        ),
        metadata=SkillMetadata(
            name="Python Lint",
            description="Linting skill",
            tags=("python", "lint"),
            inputs_schema={"type": "object"},
            outputs_schema={"type": "object"},
            token_estimate=128,
            maturity_score=0.9,
            security_score=0.95,
        ),
        lifecycle_status=lifecycle_status,
        trust_tier="internal",
        provenance=None,
        published_at=datetime(2026, 3, 13, 9, 0, tzinfo=UTC),
    )


def _top_version(
    slug: str,
    *,
    install_count: int,
    lifecycle_status: str = "published",
    published_at: datetime | None = None,
) -> SkillVersionDetail:
    base = _stored_version(lifecycle_status=lifecycle_status)
    return SkillVersionDetail(
        slug=slug,
        version=base.version,
        install_count=install_count,
        version_checksum=base.version_checksum,
        content=base.content,
        metadata=base.metadata,
        lifecycle_status=base.lifecycle_status,
        trust_tier=base.trust_tier,
        provenance=base.provenance,
        published_at=published_at or base.published_at,
        namespace=base.namespace,
        artifact_origin=base.artifact_origin,
        review_state=base.review_state,
        promotion_channel=base.promotion_channel,
        policy_pack=base.policy_pack,
    )


def _stored_content(*, lifecycle_status: str = "published") -> SkillContentRecord:
    payload = build_skill_bundle("# Python Lint\n")
    return SkillContentRecord(
        slug="python-lint",
        version="1.0.0",
        payload=payload,
        checksum=SkillChecksum(algorithm="sha256", digest="content-digest"),
        media_type=SKILL_ARTIFACT_MEDIA_TYPE,
        size_bytes=len(payload),
        lifecycle_status=lifecycle_status,
        trust_tier="internal",
    )


def _stored_version_summary(
    version: str,
    *,
    slug: str = "python-lint",
    lifecycle_status: str = "published",
    published_at: datetime | None = None,
) -> SkillVersionListEntry:
    return SkillVersionListEntry(
        slug=slug,
        version=version,
        lifecycle_status=lifecycle_status,
        trust_tier="internal",
        published_at=published_at or datetime(2026, 3, 13, 9, 0, tzinfo=UTC),
    )


@pytest.mark.unit
def test_get_version_metadata_returns_immutable_detail() -> None:
    audit_recorder = FakeAuditRecorder()
    repository = FakeCatalogRepository(version=_stored_version())
    service = SkillFetchService(
        repository=repository,
        audit_recorder=audit_recorder,
        governance_policy=_governance_policy(),
    )

    detail = service.get_version_metadata(
        caller=_caller("read"),
        slug="python-lint",
        version="1.0.0",
    )

    assert detail.slug == "python-lint"
    assert detail.version == "1.0.0"
    assert detail.content.checksum.digest == "content-digest"
    assert not hasattr(detail.metadata, "headers")
    assert audit_recorder.events == ["skill.version_metadata_read"]


@pytest.mark.unit
def test_get_content_returns_bundle_document() -> None:
    audit_recorder = FakeAuditRecorder()
    repository = FakeCatalogRepository(content=_stored_content())
    service = SkillFetchService(
        repository=repository,
        audit_recorder=audit_recorder,
        governance_policy=_governance_policy(),
    )

    document = service.get_content(
        caller=_caller("read"),
        slug="python-lint",
        version="1.0.0",
    )

    assert document.payload == build_skill_bundle("# Python Lint\n")
    assert document.checksum.digest == "content-digest"
    assert document.media_type == SKILL_ARTIFACT_MEDIA_TYPE
    assert document.size_bytes == len(build_skill_bundle("# Python Lint\n"))
    assert audit_recorder.events == ["skill.version_content_read"]
    assert repository.install_calls == [("python-lint", "1.0.0")]


@pytest.mark.unit
def test_get_version_metadata_raises_not_found_for_unknown_coordinate() -> None:
    service = SkillFetchService(
        repository=FakeCatalogRepository(),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )

    with pytest.raises(SkillVersionNotFoundError):
        service.get_version_metadata(
            caller=_caller("read"),
            slug="python-missing",
            version="9.9.9",
        )


@pytest.mark.unit
def test_get_content_applies_exact_read_policy() -> None:
    audit_recorder = FakeAuditRecorder()
    repository = FakeCatalogRepository(content=_stored_content(lifecycle_status="archived"))
    service = SkillFetchService(
        repository=repository,
        audit_recorder=audit_recorder,
        governance_policy=_governance_policy(),
    )

    with pytest.raises(PolicyViolation):
        service.get_content(
            caller=_caller("read"),
            slug="python-lint",
            version="1.0.0",
        )

    assert audit_recorder.events == ["skill.version_exact_read_denied"]
    assert repository.install_calls == []


@pytest.mark.unit
def test_list_versions_returns_visible_versions_with_current_default_first() -> None:
    audit_recorder = FakeAuditRecorder()
    service = SkillFetchService(
        repository=FakeCatalogRepository(
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
    )

    result = service.list_versions(caller=_caller("read"), slug="python-lint")

    assert result.slug == "python-lint"
    assert [item.version for item in result.versions] == ["2.0.0", "1.0.0"]
    assert result.versions[0].is_current_default is True
    assert result.versions[1].is_current_default is False
    assert audit_recorder.events == ["skill.version_list_read"]


@pytest.mark.unit
def test_list_versions_hides_fully_invisible_skills() -> None:
    service = SkillFetchService(
        repository=FakeCatalogRepository(
            versions=(_stored_version_summary("1.0.0", lifecycle_status="archived"),)
        ),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )

    with pytest.raises(SkillNotFoundError):
        service.list_versions(caller=_caller("read"), slug="python-lint")


@pytest.mark.unit
def test_list_versions_includes_archived_versions_for_admin_without_marking_default() -> None:
    service = SkillFetchService(
        repository=FakeCatalogRepository(
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
    )

    result = service.list_versions(caller=_caller("admin"), slug="python-lint")

    assert [item.version for item in result.versions] == ["1.0.0", "2.0.0"]
    assert result.versions[0].is_current_default is True
    assert result.versions[1].is_current_default is False


@pytest.mark.unit
def test_list_versions_uses_version_as_final_tie_break_for_current_default() -> None:
    published_at = datetime(2026, 3, 13, 9, 0, tzinfo=UTC)
    service = SkillFetchService(
        repository=FakeCatalogRepository(
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
    )

    result = service.list_versions(caller=_caller("read"), slug="python-lint")

    assert [item.version for item in result.versions] == ["1.0.0", "2.0.0"]
    assert result.versions[0].is_current_default is True
    assert result.versions[1].is_current_default is False


@pytest.mark.unit
def test_list_top_installed_returns_visible_versions_with_limit() -> None:
    service = SkillFetchService(
        repository=FakeCatalogRepository(
            top_versions=(
                _top_version("python-first", install_count=10),
                _top_version("python-hidden", install_count=9, lifecycle_status="archived"),
                _top_version("python-second", install_count=8),
            )
        ),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )

    result = service.list_top_installed(caller=_caller("read"), limit=2)

    assert [item.slug for item in result] == ["python-first", "python-second"]


@pytest.mark.unit
def test_list_catalog_skills_returns_all_visible_versions_ordered_by_installs() -> None:
    service = SkillFetchService(
        repository=FakeCatalogRepository(
            top_versions=(
                _top_version("python-first", install_count=10),
                _top_version("python-hidden", install_count=9, lifecycle_status="archived"),
                _top_version("python-second", install_count=8),
                _top_version("python-third", install_count=7),
            )
        ),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )

    result = service.list_catalog_skills(caller=_caller("read"))

    assert [item.slug for item in result] == [
        "python-first",
        "python-second",
        "python-third",
    ]


@pytest.mark.unit
def test_list_skill_graph_returns_visible_nodes_and_authored_safe_edges() -> None:
    service = SkillFetchService(
        repository=FakeCatalogRepository(
            top_versions=(
                _top_version("python-first", install_count=10),
                _top_version("python-hidden", install_count=9, lifecycle_status="archived"),
                _top_version("python-second", install_count=8),
                _top_version("python-third", install_count=7),
            ),
            graph_edges=(
                SkillGraphEdge(
                    source_slug="python-first",
                    source_version="1.0.0",
                    target_slug="python-second",
                    edge_type="depends_on",
                ),
                SkillGraphEdge(
                    source_slug="python-first",
                    source_version="1.0.0",
                    target_slug="python-third",
                    edge_type="extends",
                ),
                SkillGraphEdge(
                    source_slug="python.first",
                    source_version="1.0.0",
                    target_slug="python.second",
                    edge_type="conflicts_with",
                ),
                SkillGraphEdge(
                    source_slug="python-second",
                    source_version="1.0.0",
                    target_slug="python-hidden",
                    edge_type="overlaps_with",
                ),
            ),
        ),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )

    graph = service.list_skill_graph(caller=_caller("read"), limit=3)

    assert [node.slug for node in graph.nodes] == [
        "python-first",
        "python-second",
        "python-third",
    ]
    assert [(edge.source_slug, edge.target_slug, edge.edge_type) for edge in graph.edges] == [
        ("python-first", "python-second", "depends_on"),
        ("python-first", "python-third", "extends"),
    ]


@pytest.mark.unit
def test_search_catalog_returns_current_default_metadata_in_discovery_order() -> None:
    service = SkillFetchService(
        repository=FakeCatalogRepository(
            versions=(
                _stored_version_summary("1.0.0", slug="python-second"),
                _stored_version_summary("1.0.0", slug="python-first"),
                _stored_version_summary(
                    "2.0.0",
                    slug="python-first",
                    published_at=datetime(2026, 3, 14, 9, 0, tzinfo=UTC),
                ),
            ),
            details=(
                _stored_version(slug="python-first", version="2.0.0"),
                _stored_version(slug="python-second", version="1.0.0"),
            ),
        ),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
        discovery_service=FakeDiscoveryService(("python-first", "python-second")),
    )

    result = service.search_catalog(
        caller=_caller("read"),
        request=SkillDiscoveryRequest(name="python", description=None, tags=()),
        limit=20,
    )

    assert [(item.slug, item.version) for item in result] == [
        ("python-first", "2.0.0"),
        ("python-second", "1.0.0"),
    ]


@pytest.mark.unit
def test_search_catalog_filters_non_visible_candidates() -> None:
    service = SkillFetchService(
        repository=FakeCatalogRepository(
            versions=(
                _stored_version_summary(
                    "1.0.0",
                    slug="python-hidden",
                    lifecycle_status="archived",
                ),
                _stored_version_summary("1.0.0", slug="python-visible"),
            ),
            details=(
                _stored_version(
                    slug="python-hidden",
                    version="1.0.0",
                    lifecycle_status="archived",
                ),
                _stored_version(slug="python-visible", version="1.0.0"),
            ),
        ),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
        discovery_service=FakeDiscoveryService(("python-hidden", "python-visible")),
    )

    result = service.search_catalog(
        caller=_caller("read"),
        request=SkillDiscoveryRequest(name="python", description=None, tags=()),
        limit=20,
    )

    assert [item.slug for item in result] == ["python-visible"]


@pytest.mark.unit
def test_search_catalog_respects_limit() -> None:
    service = SkillFetchService(
        repository=FakeCatalogRepository(
            versions=(
                _stored_version_summary("1.0.0", slug="python-first"),
                _stored_version_summary("1.0.0", slug="python-second"),
            ),
            details=(
                _stored_version(slug="python-first", version="1.0.0"),
                _stored_version(slug="python-second", version="1.0.0"),
            ),
        ),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
        discovery_service=FakeDiscoveryService(("python-first", "python-second")),
    )

    result = service.search_catalog(
        caller=_caller("read"),
        request=SkillDiscoveryRequest(name="python", description=None, tags=()),
        limit=1,
    )

    assert [item.slug for item in result] == ["python-first"]
