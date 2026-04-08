"""Regression coverage for the demo seed runner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.bootstrap.demo_catalog import build_demo_catalog
from app.bootstrap.seed_demo import seed_demo_catalog
from app.core.skills.models import (
    DuplicateSkillVersionError,
    SkillAlreadyExistsError,
    SkillChecksum,
    SkillContentSummary,
    SkillMetadata,
    SkillVersionDetail,
    SkillVersionNotFoundError,
    SkillVersionStatusUpdate,
)


@dataclass
class _StoredVersion:
    lifecycle_status: str
    trust_tier: str
    published_at: datetime


class _FakeRegistryService:
    def __init__(self, store: dict[tuple[str, str], _StoredVersion]) -> None:
        self._store = store

    def publish_version(self, *, caller, command):  # type: ignore[no-untyped-def]
        key = (command.slug, command.version)
        if key in self._store:
            raise DuplicateSkillVersionError(slug=command.slug, version=command.version)
        self._store[key] = _StoredVersion(
            lifecycle_status="published",
            trust_tier=command.governance.trust_tier,
            published_at=datetime.now(UTC),
        )
        return _detail_for(
            slug=command.slug,
            version=command.version,
            lifecycle_status="published",
            trust_tier=command.governance.trust_tier,
        )

    def update_version_status(
        self,
        *,
        caller,
        slug: str,
        version: str,
        lifecycle_status: str,
        note: str | None = None,
    ) -> SkillVersionStatusUpdate:
        del caller, note
        key = (slug, version)
        stored = self._store[key]
        stored.lifecycle_status = lifecycle_status
        return SkillVersionStatusUpdate(
            slug=slug,
            version=version,
            status=lifecycle_status,
            trust_tier=stored.trust_tier,
            lifecycle_changed_at=datetime.now(UTC),
            is_current_default=lifecycle_status == "published",
        )


class _FakeFetchService:
    def __init__(self, store: dict[tuple[str, str], _StoredVersion]) -> None:
        self._store = store

    def get_version_metadata(self, *, caller, slug: str, version: str) -> SkillVersionDetail:
        del caller
        key = (slug, version)
        stored = self._store.get(key)
        if stored is None:
            raise SkillVersionNotFoundError(slug=slug, version=version)
        return _detail_for(
            slug=slug,
            version=version,
            lifecycle_status=stored.lifecycle_status,
            trust_tier=stored.trust_tier,
        )


def _detail_for(
    *,
    slug: str,
    version: str,
    lifecycle_status: str,
    trust_tier: str,
) -> SkillVersionDetail:
    return SkillVersionDetail(
        slug=slug,
        version=version,
        install_count=0,
        version_checksum=SkillChecksum(algorithm="sha256", digest="0" * 64),
        content=SkillContentSummary(
            checksum=SkillChecksum(algorithm="sha256", digest="1" * 64),
            size_bytes=123,
        ),
        metadata=SkillMetadata(
            name=slug,
            description=f"{slug} description",
            tags=("python", "demo"),
            inputs_schema={"type": "object"},
            outputs_schema={"type": "object"},
            token_estimate=256,
            maturity_score=0.9,
            security_score=0.95,
        ),
        lifecycle_status=lifecycle_status,
        trust_tier=trust_tier,
        provenance=None,
        published_at=datetime.now(UTC),
    )


def test_demo_seed_runner_is_idempotent_and_preserves_unrelated_versions() -> None:
    store: dict[tuple[str, str], _StoredVersion] = {
        ("python.custom.local", "9.9.9"): _StoredVersion(
            lifecycle_status="published",
            trust_tier="untrusted",
            published_at=datetime.now(UTC),
        )
    }
    registry_service = _FakeRegistryService(store)
    fetch_service = _FakeFetchService(store)
    catalog = build_demo_catalog()

    first = seed_demo_catalog(
        registry_service=registry_service,
        fetch_service=fetch_service,
        catalog=catalog,
    )
    second = seed_demo_catalog(
        registry_service=registry_service,
        fetch_service=fetch_service,
        catalog=catalog,
    )

    assert first.published_count == len(catalog)
    assert first.skipped_existing_count == 0
    assert first.status_updated_count == 3

    assert second.published_count == 0
    assert second.skipped_existing_count == len(catalog)
    assert second.status_updated_count == 0

    assert store[("python.custom.local", "9.9.9")].lifecycle_status == "published"
    assert len(store) == len(catalog) + 1
    assert store[("python.lint", "1.0.0")].lifecycle_status == "deprecated"
    assert store[("python.format", "1.0.0")].lifecycle_status == "archived"
    assert store[("python.legacy.audit", "0.9.0")].lifecycle_status == "deprecated"


def test_demo_seed_treats_existing_skill_slug_as_already_seeded() -> None:
    catalog = build_demo_catalog()
    first_entry = catalog[0]
    store: dict[tuple[str, str], _StoredVersion] = {
        (first_entry.command.slug, first_entry.command.version): _StoredVersion(
            lifecycle_status=first_entry.desired_lifecycle_status,
            trust_tier=first_entry.command.governance.trust_tier,
            published_at=datetime.now(UTC),
        )
    }
    fetch_service = _FakeFetchService(store)

    class _ExistingSkillRegistryService(_FakeRegistryService):
        def publish_version(self, *, caller, command):  # type: ignore[no-untyped-def]
            del caller
            if (
                command.slug == first_entry.command.slug
                and command.version == first_entry.command.version
            ):
                raise SkillAlreadyExistsError(slug=command.slug)
            return super().publish_version(caller=None, command=command)

    summary = seed_demo_catalog(
        registry_service=_ExistingSkillRegistryService(store),  # type: ignore[arg-type]
        fetch_service=fetch_service,
        catalog=catalog[0:1],
    )

    assert summary.published_count == 0
    assert summary.skipped_existing_count == 1
    assert summary.status_updated_count == 0
