"""One-shot rich demo catalog seeding for local Docker workflows."""

from __future__ import annotations

from dataclasses import dataclass

from app.bootstrap.demo_catalog import DemoSeedEntry, build_demo_catalog
from app.core.governance import CallerIdentity
from app.core.settings import get_settings, reset_settings_cache
from app.core.skills.fetch import SkillFetchService
from app.core.skills.models import DuplicateSkillVersionError, SkillVersionNotFoundError
from app.core.skills.registry import SkillRegistryService
from app.persistence.db import dispose_engine
from app.service_container import build_service_container

_STATUS_CALLER = CallerIdentity(
    token="demo-seed-admin",
    scopes=frozenset({"read", "publish", "admin"}),
)


@dataclass(frozen=True, slots=True)
class DemoSeedSummary:
    """Structured result for one demo seeding run."""

    total_entries: int
    published_count: int
    skipped_existing_count: int
    status_updated_count: int


def seed_demo_catalog(
    *,
    registry_service: SkillRegistryService,
    fetch_service: SkillFetchService,
    catalog: tuple[DemoSeedEntry, ...] | None = None,
) -> DemoSeedSummary:
    """Seed the local demo catalog using the real publish and lifecycle services."""
    entries = build_demo_catalog() if catalog is None else catalog
    published_count = 0
    skipped_existing_count = 0
    status_updated_count = 0

    for entry in entries:
        try:
            registry_service.publish_version(
                caller=entry.publish_caller,
                command=entry.command,
            )
            published_count += 1
        except DuplicateSkillVersionError:
            skipped_existing_count += 1

        current_status = _current_lifecycle_status(
            fetch_service=fetch_service,
            slug=entry.command.slug,
            version=entry.command.version,
        )
        if current_status != entry.desired_lifecycle_status:
            registry_service.update_version_status(
                caller=_STATUS_CALLER,
                slug=entry.command.slug,
                version=entry.command.version,
                lifecycle_status=entry.desired_lifecycle_status,
                note="Synchronized by local demo catalog seeder.",
            )
            status_updated_count += 1

    return DemoSeedSummary(
        total_entries=len(entries),
        published_count=published_count,
        skipped_existing_count=skipped_existing_count,
        status_updated_count=status_updated_count,
    )


def run_demo_seed() -> DemoSeedSummary:
    """Build services from settings, seed the demo catalog, and dispose the engine."""
    reset_settings_cache()
    settings = get_settings()
    services = build_service_container(settings=settings)
    try:
        return seed_demo_catalog(
            registry_service=services.skill_registry_service,
            fetch_service=services.skill_fetch_service,
        )
    finally:
        dispose_engine()


def main() -> int:
    """Run the demo seed workflow and emit a concise operator summary."""
    summary = run_demo_seed()
    print(
        "Demo seed complete: "
        f"total={summary.total_entries} "
        f"published={summary.published_count} "
        f"skipped_existing={summary.skipped_existing_count} "
        f"status_updated={summary.status_updated_count}"
    )
    return 0


def _current_lifecycle_status(
    *,
    fetch_service: SkillFetchService,
    slug: str,
    version: str,
) -> str | None:
    try:
        detail = fetch_service.get_version_metadata(
            caller=_STATUS_CALLER,
            slug=slug,
            version=version,
        )
    except SkillVersionNotFoundError:
        return None
    return detail.lifecycle_status


if __name__ == "__main__":
    raise SystemExit(main())
