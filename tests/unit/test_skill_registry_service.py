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
    SkillRegistryPersistenceError,
    StoredSkillVersion,
    StoredSkillVersionStatus,
)
from app.core.skills.registry import (
    CreateSkillVersionCommand,
    DuplicateSkillVersionError,
    SkillAlreadyExistsError,
    SkillContentInput,
    SkillMetadataInput,
    SkillNotFoundError,
    SkillRegistryService,
    SkillRelationshipsInput,
)


class _SlugConflictCause(Exception):
    """Synthetic DB cause carrying the skills.slug constraint name."""


class FakeRegistry:
    """In-memory stub for core registry tests."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], StoredSkillVersion] = {}
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
    ) -> StoredSkillVersion:
        key = (record.slug, record.version)
        if key in self._records:
            raise DuplicateSkillVersionError(slug=record.slug, version=record.version)

        stored = StoredSkillVersion(
            slug=record.slug,
            version=record.version,
            install_count=0,
            version_checksum_digest=record.version_checksum_digest,
            content_checksum_digest=record.content.checksum_digest,
            content_size_bytes=record.content.size_bytes,
            name=record.metadata.name,
            description=record.metadata.description,
            tags=record.metadata.tags,
            inputs_schema=record.metadata.inputs_schema,
            outputs_schema=record.metadata.outputs_schema,
            token_estimate=record.metadata.token_estimate,
            maturity_score=record.metadata.maturity_score,
            security_score=record.metadata.security_score,
            lifecycle_status="published",
            trust_tier=record.governance.trust_tier,
            provenance=record.governance.provenance,
            lifecycle_changed_at=datetime.now(tz=UTC),
            published_at=datetime.now(tz=UTC),
            relationships=(),
        )
        self._records[key] = stored
        self.audit_events.extend(audit_events)
        return stored

    def get_version(self, *, slug: str, version: str) -> StoredSkillVersion | None:
        return self._records.get((slug, version))

    def update_version_status(
        self,
        *,
        slug: str,
        version: str,
        lifecycle_status: str,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> StoredSkillVersionStatus | None:
        record = self._records.get((slug, version))
        if record is None:
            return None
        updated = StoredSkillVersion(
            slug=record.slug,
            version=record.version,
            install_count=record.install_count,
            version_checksum_digest=record.version_checksum_digest,
            content_checksum_digest=record.content_checksum_digest,
            content_size_bytes=record.content_size_bytes,
            name=record.name,
            description=record.description,
            tags=record.tags,
            inputs_schema=record.inputs_schema,
            outputs_schema=record.outputs_schema,
            token_estimate=record.token_estimate,
            maturity_score=record.maturity_score,
            security_score=record.security_score,
            lifecycle_status=lifecycle_status,
            trust_tier=record.trust_tier,
            provenance=record.provenance,
            lifecycle_changed_at=datetime.now(tz=UTC),
            published_at=record.published_at,
            relationships=record.relationships,
        )
        self._records[(slug, version)] = updated
        self.audit_events.extend(audit_events)
        return StoredSkillVersionStatus(
            slug=slug,
            version=version,
            lifecycle_status=lifecycle_status,
            trust_tier=updated.trust_tier,
            lifecycle_changed_at=updated.lifecycle_changed_at,
            is_current_default=True,
        )


class FakeAuditRecorder:
    """Audit stub collecting event names."""

    def __init__(self) -> None:
        self.events: list[str] = []

    def record_event(self, *, event_type: str, payload: dict[str, object] | None = None) -> None:
        self.events.append(event_type)


class SlugConflictRegistry(FakeRegistry):
    """Registry stub that simulates a slug uniqueness race during persistence."""

    def create_version(
        self,
        *,
        record: CreateSkillVersionRecord,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> StoredSkillVersion:
        del record, audit_events
        raise SkillRegistryPersistenceError(
            "Failed to persist immutable skill version."
        ) from _SlugConflictCause('duplicate key value violates unique constraint "uq_skills_slug"')


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
        content=SkillContentInput(raw_markdown="# Python Lint\n"),
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
    return CallerIdentity(token="publish", scopes=frozenset({"publish", "read"}))


@pytest.mark.unit
def test_publish_version_returns_checksum_and_records_audit() -> None:
    registry = FakeRegistry()
    audit_recorder = FakeAuditRecorder()
    service = SkillRegistryService(
        registry=registry,
        audit_recorder=audit_recorder,
        governance_policy=_governance_policy(),
    )

    response = service.publish_version(
        caller=_publish_caller(),
        command=_command(slug="python.lint", version="1.0.0"),
    )

    assert response.slug == "python.lint"
    assert response.version == "1.0.0"
    assert response.version_checksum.algorithm == "sha256"
    assert response.content.size_bytes == len(b"# Python Lint\n")
    assert "skill.version_published" in [event.event_type for event in registry.audit_events]


@pytest.mark.unit
def test_publish_version_uses_stable_checksum_for_same_immutable_payload() -> None:
    first_service = SkillRegistryService(
        registry=FakeRegistry(),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )
    second_service = SkillRegistryService(
        registry=FakeRegistry(),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )
    command = _command(slug="python.lint", version="1.0.0")

    first = first_service.publish_version(caller=_publish_caller(), command=command)
    second = second_service.publish_version(caller=_publish_caller(), command=command)

    assert first.content.checksum.digest == second.content.checksum.digest
    assert first.version_checksum.digest == second.version_checksum.digest


@pytest.mark.unit
def test_publish_version_distinguishes_version_checksum_from_content_checksum() -> None:
    registry = FakeRegistry()
    service = SkillRegistryService(
        registry=registry,
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )

    first = service.publish_version(
        caller=_publish_caller(),
        command=_command(slug="python.lint", version="1.0.0"),
    )
    second = service.publish_version(
        caller=_publish_caller(),
        command=CreateSkillVersionCommand(
            slug="python.lint",
            intent="publish_version",
            version="2.0.0",
            content=SkillContentInput(raw_markdown="# Python Lint\n"),
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
    registry = FakeRegistry()
    service = SkillRegistryService(
        registry=registry,
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )
    service.publish_version(
        caller=_publish_caller(),
        command=_command(slug="python.lint", version="1.0.0"),
    )

    with pytest.raises(DuplicateSkillVersionError):
        service.publish_version(
            caller=_publish_caller(),
            command=_command(slug="python.lint", version="1.0.0", intent="publish_version"),
        )


@pytest.mark.unit
def test_create_skill_intent_rejects_existing_slug() -> None:
    registry = FakeRegistry()
    service = SkillRegistryService(
        registry=registry,
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )
    service.publish_version(
        caller=_publish_caller(),
        command=_command(slug="python.lint", version="1.0.0", intent="create_skill"),
    )

    with pytest.raises(SkillAlreadyExistsError):
        service.publish_version(
            caller=_publish_caller(),
            command=_command(slug="python.lint", version="2.0.0", intent="create_skill"),
        )


@pytest.mark.unit
def test_publish_version_intent_rejects_missing_slug() -> None:
    registry = FakeRegistry()
    service = SkillRegistryService(
        registry=registry,
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )

    with pytest.raises(SkillNotFoundError):
        service.publish_version(
            caller=_publish_caller(),
            command=_command(slug="python.lint", version="1.0.0", intent="publish_version"),
        )


@pytest.mark.unit
def test_publish_version_denied_by_policy_records_audit_event() -> None:
    registry = FakeRegistry()
    audit_recorder = FakeAuditRecorder()
    service = SkillRegistryService(
        registry=registry,
        audit_recorder=audit_recorder,
        governance_policy=_governance_policy(),
    )

    with pytest.raises(PolicyViolation) as exc_info:
        service.publish_version(
            caller=_publish_caller(),
            command=CreateSkillVersionCommand(
                slug="python.lint",
                intent="create_skill",
                version="1.0.0",
                content=SkillContentInput(raw_markdown="# Python Lint\n"),
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
        registry=SlugConflictRegistry(),
        audit_recorder=FakeAuditRecorder(),
        governance_policy=_governance_policy(),
    )

    with pytest.raises(SkillAlreadyExistsError):
        service.publish_version(
            caller=_publish_caller(),
            command=_command(slug="python.race", version="1.0.0"),
        )
