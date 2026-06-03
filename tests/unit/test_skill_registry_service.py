"""Unit tests for normalized skill registry core behavior."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.governance import (
    CallerIdentity,
    GovernancePolicy,
    PolicyViolation,
    ProvenanceMetadata,
    SkillGovernanceInput,
    build_default_policy_profile,
)
from app.core.ports import (
    AuditEventRecord,
    CreateSkillVersionRecord,
    DuplicateSkillSlugPersistenceError,
    DuplicateSkillVersionPersistenceError,
)
from app.core.skills.bundle_archive import SKILL_ARTIFACT_MEDIA_TYPE, build_skill_bundle
from app.core.skills.models import (
    CreateSkillVersionCommand,
    SkillAlreadyExistsError,
    SkillChecksum,
    SkillContentInput,
    SkillContentSummary,
    SkillMetadata,
    SkillMetadataInput,
    SkillNotFoundError,
    SkillRelationshipsInput,
    SkillVersionDetail,
    SkillVersionNotFoundError,
    SkillVersionStatusUpdate,
)
from app.core.skills.registry import (
    DuplicateSkillVersionError,
    SkillRegistryService,
)


class FakeCatalogRepository:
    """In-memory stub for core registry tests."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], SkillVersionDetail] = {}
        self.audit_events: list[AuditEventRecord] = []

    def skill_exists(self, *, slug: str) -> bool:
        return any(record_slug == slug for record_slug, _ in self._records)

    def version_exists(self, *, slug: str, version: str) -> bool:
        return (slug, version) in self._records

    def create_version(
        self,
        *,
        record: CreateSkillVersionRecord,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> SkillVersionDetail:
        key = (record.slug, record.version)
        if key in self._records:
            raise DuplicateSkillVersionPersistenceError("duplicate immutable version")

        stored = SkillVersionDetail(
            slug=record.slug,
            version=record.version,
            install_count=0,
            version_checksum=SkillChecksum(
                algorithm="sha256",
                digest=record.version_checksum_digest,
            ),
            content=SkillContentSummary(
                checksum=SkillChecksum(
                    algorithm="sha256",
                    digest=record.content.checksum_digest,
                ),
                media_type=record.content.media_type,
                size_bytes=record.content.size_bytes,
            ),
            metadata=SkillMetadata(
                name=record.metadata.name,
                description=record.metadata.description,
                tags=record.metadata.tags,
                inputs_schema=record.metadata.inputs_schema,
                outputs_schema=record.metadata.outputs_schema,
                token_estimate=record.metadata.token_estimate,
                maturity_score=record.metadata.maturity_score,
                security_score=record.metadata.security_score,
            ),
            lifecycle_status="published",
            trust_tier=record.governance.trust_tier,
            provenance=record.governance.provenance,
            published_at=datetime.now(tz=UTC),
        )
        self._records[key] = stored
        self.audit_events.extend(audit_events)
        return stored

    def get_version_detail(self, *, slug: str, version: str) -> SkillVersionDetail | None:
        return self._records.get((slug, version))

    def update_version_status(
        self,
        *,
        slug: str,
        version: str,
        lifecycle_status: str,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> SkillVersionStatusUpdate | None:
        record = self._records.get((slug, version))
        if record is None:
            return None
        updated = SkillVersionDetail(
            slug=record.slug,
            version=record.version,
            install_count=record.install_count,
            version_checksum=record.version_checksum,
            content=record.content,
            metadata=record.metadata,
            lifecycle_status=lifecycle_status,
            trust_tier=record.trust_tier,
            provenance=record.provenance,
            published_at=record.published_at,
        )
        self._records[(slug, version)] = updated
        self.audit_events.extend(audit_events)
        return SkillVersionStatusUpdate(
            slug=slug,
            version=version,
            status=lifecycle_status,
            trust_tier=updated.trust_tier,
            lifecycle_changed_at=datetime.now(tz=UTC),
            is_current_default=True,
        )


class FakeAuditRecorder:
    """Audit stub collecting event names."""

    def __init__(self) -> None:
        self.events: list[str] = []

    def record_event(self, *, event_type: str, payload: dict[str, object] | None = None) -> None:
        del payload
        self.events.append(event_type)


class SlugConflictRepository(FakeCatalogRepository):
    """Repository stub that simulates a slug uniqueness race during persistence."""

    def create_version(
        self,
        *,
        record: CreateSkillVersionRecord,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> SkillVersionDetail:
        del record, audit_events
        raise DuplicateSkillSlugPersistenceError("skills.slug already exists")


def _command(
    slug: str,
    version: str,
    *,
    intent: str = "create_skill",
) -> CreateSkillVersionCommand:
    return CreateSkillVersionCommand(
        slug=slug,
        intent=intent,
        version=version,
        content=SkillContentInput(
            payload=build_skill_bundle("# Python Lint\n"),
            media_type=SKILL_ARTIFACT_MEDIA_TYPE,
        ),
        metadata=SkillMetadataInput(
            name="Python Lint",
            description="Linting skill",
            tags=("python", "lint"),
        ),
        relationships=SkillRelationshipsInput(),
    )


def _governance_policy() -> GovernancePolicy:
    return GovernancePolicy(profile=build_default_policy_profile())


def _publish_caller() -> CallerIdentity:
    return CallerIdentity(token_id="publish", scopes=frozenset({"publish", "read"}))


@pytest.mark.unit
def test_publish_version_returns_checksum_and_records_audit() -> None:
    repository = FakeCatalogRepository()
    audit_recorder = FakeAuditRecorder()
    service = SkillRegistryService(
        repository=repository,
        audit_recorder=audit_recorder,
        governance_policy=_governance_policy(),
    )

    response = service.publish_version(
        caller=_publish_caller(),
        command=_command(slug="python-lint", version="1.0.0"),
    )

    assert response.slug == "python-lint"
    assert response.version == "1.0.0"
    assert response.version_checksum.algorithm == "sha256"
    assert response.content.media_type == SKILL_ARTIFACT_MEDIA_TYPE
    assert response.content.size_bytes == len(build_skill_bundle("# Python Lint\n"))
    assert "skill.version_published" in [event.event_type for event in repository.audit_events]


@pytest.mark.unit
def test_publish_version_uses_stable_checksum_for_same_immutable_payload() -> None:
    first_service = SkillRegistryService(
        repository=FakeCatalogRepository(),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )
    second_service = SkillRegistryService(
        repository=FakeCatalogRepository(),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )
    command = _command(slug="python-lint", version="1.0.0")

    first = first_service.publish_version(caller=_publish_caller(), command=command)
    second = second_service.publish_version(caller=_publish_caller(), command=command)

    assert first.content.checksum.digest == second.content.checksum.digest
    assert first.version_checksum.digest == second.version_checksum.digest


@pytest.mark.unit
def test_publish_version_distinguishes_version_checksum_from_content_checksum() -> None:
    repository = FakeCatalogRepository()
    service = SkillRegistryService(
        repository=repository,
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )

    first = service.publish_version(
        caller=_publish_caller(),
        command=_command(slug="python-lint", version="1.0.0"),
    )
    second = service.publish_version(
        caller=_publish_caller(),
        command=CreateSkillVersionCommand(
            slug="python-lint",
            intent="publish_version",
            version="2.0.0",
            content=SkillContentInput(
                payload=build_skill_bundle("# Python Lint\n"),
                media_type=SKILL_ARTIFACT_MEDIA_TYPE,
            ),
            metadata=SkillMetadataInput(
                name="Python Lint v2",
                description="Linting skill with richer metadata",
                tags=("python", "lint", "quality"),
            ),
            relationships=SkillRelationshipsInput(),
        ),
    )

    assert first.content.checksum.digest == second.content.checksum.digest
    assert first.version_checksum.digest != second.version_checksum.digest


@pytest.mark.unit
def test_publish_version_rejects_duplicates() -> None:
    repository = FakeCatalogRepository()
    service = SkillRegistryService(
        repository=repository,
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )
    service.publish_version(
        caller=_publish_caller(),
        command=_command(slug="python-lint", version="1.0.0"),
    )

    with pytest.raises(DuplicateSkillVersionError):
        service.publish_version(
            caller=_publish_caller(),
            command=_command(slug="python-lint", version="1.0.0", intent="publish_version"),
        )


@pytest.mark.unit
def test_create_skill_intent_rejects_existing_slug() -> None:
    repository = FakeCatalogRepository()
    service = SkillRegistryService(
        repository=repository,
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )
    service.publish_version(
        caller=_publish_caller(),
        command=_command(slug="python-lint", version="1.0.0", intent="create_skill"),
    )

    with pytest.raises(SkillAlreadyExistsError):
        service.publish_version(
            caller=_publish_caller(),
            command=_command(slug="python-lint", version="2.0.0", intent="create_skill"),
        )


@pytest.mark.unit
def test_publish_version_intent_rejects_missing_slug() -> None:
    repository = FakeCatalogRepository()
    service = SkillRegistryService(
        repository=repository,
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )

    with pytest.raises(SkillNotFoundError):
        service.publish_version(
            caller=_publish_caller(),
            command=_command(slug="python-lint", version="1.0.0", intent="publish_version"),
        )


@pytest.mark.unit
def test_publish_version_denied_by_policy_records_audit_event() -> None:
    repository = FakeCatalogRepository()
    audit_recorder = FakeAuditRecorder()
    service = SkillRegistryService(
        repository=repository,
        audit_recorder=audit_recorder,
        governance_policy=_governance_policy(),
    )

    with pytest.raises(PolicyViolation) as exc_info:
        service.publish_version(
            caller=_publish_caller(),
            command=CreateSkillVersionCommand(
                slug="python-lint",
                intent="create_skill",
                version="1.0.0",
                content=SkillContentInput(
                    payload=build_skill_bundle("# Python Lint\n"),
                    media_type=SKILL_ARTIFACT_MEDIA_TYPE,
                ),
                metadata=SkillMetadataInput(
                    name="Python Lint",
                    description="Linting skill",
                    tags=("python", "lint"),
                ),
                relationships=SkillRelationshipsInput(),
                governance=SkillGovernanceInput(
                    trust_tier="internal",
                    provenance=ProvenanceMetadata(
                        repo_url="  https://github.com/acme/python-lint  ",
                        commit_sha="  ",
                    ),
                ),
            ),
        )

    assert exc_info.value.code == "POLICY_PROVENANCE_INVALID"
    assert "skill.version_publish_denied" in audit_recorder.events


@pytest.mark.unit
def test_publish_version_maps_slug_uniqueness_race_to_skill_already_exists() -> None:
    service = SkillRegistryService(
        repository=SlugConflictRepository(),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )

    with pytest.raises(SkillAlreadyExistsError):
        service.publish_version(
            caller=_publish_caller(),
            command=_command(slug="python-race", version="1.0.0"),
        )


@pytest.mark.unit
def test_update_version_status_raises_for_missing_version() -> None:
    service = SkillRegistryService(
        repository=FakeCatalogRepository(),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )

    with pytest.raises(SkillVersionNotFoundError):
        service.update_version_status(
            caller=CallerIdentity(token_id="admin", scopes=frozenset({"admin"})),
            slug="python-lint",
            version="1.0.0",
            lifecycle_status="deprecated",
        )
