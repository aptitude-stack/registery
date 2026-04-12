"""Core normalized skill registry service."""

from __future__ import annotations

import hashlib
import json
from typing import cast

from app.core.audit_events import build_lifecycle_audit_event, build_publish_audit_event
from app.core.governance import (
    CallerIdentity,
    GovernancePolicy,
    LifecycleStatus,
    PolicyViolation,
    ProvenanceMetadata,
    SkillGovernanceInput,
)
from app.core.ports import (
    AuditPort,
    ContentRecordInput,
    CreateSkillVersionRecord,
    GovernanceRecordInput,
    MetadataRecordInput,
    RelationshipEdgeType,
    RelationshipSelectorRecordInput,
    SkillRegistryPersistenceError,
    SkillRegistryPort,
)

from .models import (
    SHA256_ALGORITHM,
    CreateSkillVersionCommand,
    DuplicateSkillVersionError,
    PublishIntent,
    SkillAlreadyExistsError,
    SkillChecksum,
    SkillContentDocument,
    SkillContentInput,
    SkillMetadata,
    SkillMetadataInput,
    SkillNotFoundError,
    SkillRegistryError,
    SkillRelationshipSelector,
    SkillRelationshipsInput,
    SkillVersionDetail,
    SkillVersionNotFoundError,
    SkillVersionStatusUpdate,
)
from .projections import to_skill_version_detail

__all__ = [
    "SHA256_ALGORITHM",
    "CreateSkillVersionCommand",
    "DuplicateSkillVersionError",
    "PublishIntent",
    "ProvenanceMetadata",
    "SkillChecksum",
    "SkillAlreadyExistsError",
    "SkillContentDocument",
    "SkillContentInput",
    "SkillGovernanceInput",
    "SkillMetadata",
    "SkillMetadataInput",
    "SkillRegistryError",
    "SkillRelationshipSelector",
    "SkillRelationshipsInput",
    "SkillVersionDetail",
    "SkillNotFoundError",
    "SkillVersionNotFoundError",
    "SkillVersionStatusUpdate",
]


class SkillRegistryService:
    """Core service for immutable publish plus lifecycle updates."""

    def __init__(
        self,
        *,
        registry: SkillRegistryPort,
        audit_recorder: AuditPort,
        governance_policy: GovernancePolicy,
    ) -> None:
        self._registry = registry
        self._audit_recorder = audit_recorder
        self._governance_policy = governance_policy

    def publish_version(
        self,
        *,
        caller: CallerIdentity,
        command: CreateSkillVersionCommand,
    ) -> SkillVersionDetail:
        """Publish one immutable normalized version."""
        try:
            normalized_governance = self._governance_policy.prepare_publish_governance(
                caller=caller,
                governance=command.governance,
            )
        except PolicyViolation as exc:
            denied_event = build_publish_audit_event(
                caller=caller,
                slug=command.slug,
                version=command.version,
                trust_tier=command.governance.trust_tier,
                provenance=command.governance.provenance,
                policy_profile=self._governance_policy.profile_name,
                outcome="denied",
                reason_code=exc.code,
            )
            self._audit_recorder.record_event(
                event_type=denied_event.event_type,
                payload=denied_event.payload,
            )
            raise
        self._enforce_publish_intent(intent=command.intent, slug=command.slug)

        if self._registry.version_exists(slug=command.slug, version=command.version):
            raise DuplicateSkillVersionError(slug=command.slug, version=command.version)

        content_record = ContentRecordInput(
            payload=command.content.payload,
            media_type=command.content.media_type,
            size_bytes=len(command.content.payload),
            checksum_digest=_content_checksum_digest(command.content),
        )
        metadata_record = MetadataRecordInput(
            name=command.metadata.name,
            description=command.metadata.description,
            tags=command.metadata.tags,
            inputs_schema=command.metadata.inputs_schema,
            outputs_schema=command.metadata.outputs_schema,
            token_estimate=command.metadata.token_estimate,
            maturity_score=command.metadata.maturity_score,
            security_score=command.metadata.security_score,
        )
        governance_record = GovernanceRecordInput(
            trust_tier=normalized_governance.trust_tier,
            provenance=normalized_governance.provenance,
        )
        relationship_records = _to_relationship_record_inputs(command.relationships)
        version_checksum_digest = _version_checksum_digest(
            slug=command.slug,
            version=command.version,
            content_checksum_digest=content_record.checksum_digest,
            metadata=metadata_record,
            governance=governance_record,
            relationships=relationship_records,
        )

        try:
            stored = self._registry.create_version(
                record=CreateSkillVersionRecord(
                    slug=command.slug,
                    version=command.version,
                    content=content_record,
                    metadata=metadata_record,
                    governance=governance_record,
                    relationships=relationship_records,
                    version_checksum_digest=version_checksum_digest,
                ),
                audit_events=(
                    build_publish_audit_event(
                        caller=caller,
                        slug=command.slug,
                        version=command.version,
                        trust_tier=normalized_governance.trust_tier,
                        provenance=normalized_governance.provenance,
                        policy_profile=self._governance_policy.profile_name,
                        outcome="allowed",
                    ),
                ),
            )
        except DuplicateSkillVersionError:
            raise
        except SkillRegistryPersistenceError as exc:
            # Handle potential race between _enforce_publish_intent() and persistence layer.
            # Under concurrent intent="create_skill" publishes for the same slug, the DB
            # unique constraint on skills.slug may be violated even though the initial
            # skill_exists() check passed. In that case, surface SkillAlreadyExistsError
            # to keep the public contract consistent.
            if command.intent == "create_skill" and self._is_slug_unique_violation(exc):
                raise SkillAlreadyExistsError(slug=command.slug) from exc
            raise SkillRegistryError("Failed to persist immutable skill version.") from exc

        return to_skill_version_detail(stored=stored)

    def _enforce_publish_intent(self, *, intent: PublishIntent, slug: str) -> None:
        skill_exists = self._registry.skill_exists(slug=slug)
        if intent == "create_skill":
            if skill_exists:
                raise SkillAlreadyExistsError(slug=slug)
            return
        if not skill_exists:
            raise SkillNotFoundError(slug=slug)

    def _is_slug_unique_violation(
        self,
        exc: SkillRegistryPersistenceError,
    ) -> bool:
        """Best-effort detection of a unique-constraint violation on skills.slug.

        The exact structure of SkillRegistryPersistenceError is implementation-specific,
        so we conservatively inspect the exception message (and any nested cause) for
        indicators of both a uniqueness violation and the slug field.
        """
        # Start with the direct exception message.
        messages: list[str] = [str(exc)]

        # If the port attaches an underlying cause, include its message as well.
        cause = getattr(exc, "cause", None)
        if cause is None:
            cause = getattr(exc, "__cause__", None)
        if cause is not None:
            messages.append(str(cause))

        combined = " ".join(messages).lower()
        return "uq_skills_slug" in combined

    def update_version_status(
        self,
        *,
        caller: CallerIdentity,
        slug: str,
        version: str,
        lifecycle_status: LifecycleStatus,
        note: str | None = None,
    ) -> SkillVersionStatusUpdate:
        """Transition lifecycle state for one immutable version."""
        stored = self._registry.get_version(slug=slug, version=version)
        if stored is None:
            raise SkillVersionNotFoundError(slug=slug, version=version)

        try:
            self._governance_policy.evaluate_transition(
                caller=caller,
                current_status=stored.lifecycle_status,
                next_status=lifecycle_status,
            )
        except PolicyViolation as exc:
            denied_event = build_lifecycle_audit_event(
                caller=caller,
                slug=slug,
                version=version,
                previous_status=stored.lifecycle_status,
                lifecycle_status=lifecycle_status,
                trust_tier=stored.trust_tier,
                policy_profile=self._governance_policy.profile_name,
                note=note,
                outcome="denied",
                reason_code=exc.code,
            )
            self._audit_recorder.record_event(
                event_type=denied_event.event_type,
                payload=denied_event.payload,
            )
            raise

        updated = self._registry.update_version_status(
            slug=slug,
            version=version,
            lifecycle_status=lifecycle_status,
            audit_events=(
                build_lifecycle_audit_event(
                    caller=caller,
                    slug=slug,
                    version=version,
                    previous_status=stored.lifecycle_status,
                    lifecycle_status=lifecycle_status,
                    trust_tier=stored.trust_tier,
                    policy_profile=self._governance_policy.profile_name,
                    note=note,
                    outcome="allowed",
                ),
            ),
        )
        if updated is None:
            raise SkillVersionNotFoundError(slug=slug, version=version)
        return SkillVersionStatusUpdate(
            slug=updated.slug,
            version=updated.version,
            status=updated.lifecycle_status,
            trust_tier=updated.trust_tier,
            lifecycle_changed_at=updated.lifecycle_changed_at,
            is_current_default=updated.is_current_default,
        )


def _to_relationship_record_inputs(
    relationships: SkillRelationshipsInput,
) -> tuple[RelationshipSelectorRecordInput, ...]:
    rows: list[RelationshipSelectorRecordInput] = []
    for edge_type, selectors in (
        ("depends_on", relationships.depends_on),
        ("extends", relationships.extends),
        ("conflicts_with", relationships.conflicts_with),
        ("overlaps_with", relationships.overlaps_with),
    ):
        for ordinal, selector in enumerate(selectors):
            rows.append(
                RelationshipSelectorRecordInput(
                    edge_type=cast(
                        RelationshipEdgeType,
                        edge_type,
                    ),
                    ordinal=ordinal,
                    slug=selector.slug,
                    version=selector.version,
                    version_constraint=selector.version_constraint,
                    optional=selector.optional,
                    markers=selector.markers,
                )
            )
    return tuple(rows)


def _content_checksum_digest(content: SkillContentInput) -> str:
    return _sha256_hexdigest(content.payload)


def _version_checksum_digest(
    *,
    slug: str,
    version: str,
    content_checksum_digest: str,
    metadata: MetadataRecordInput,
    governance: GovernanceRecordInput,
    relationships: tuple[RelationshipSelectorRecordInput, ...],
) -> str:
    payload = {
        "slug": slug,
        "version": version,
        "content_checksum_digest": content_checksum_digest,
        "metadata": {
            "name": metadata.name,
            "description": metadata.description,
            "tags": list(metadata.tags),
            "inputs_schema": metadata.inputs_schema,
            "outputs_schema": metadata.outputs_schema,
            "token_estimate": metadata.token_estimate,
            "maturity_score": metadata.maturity_score,
            "security_score": metadata.security_score,
        },
        "governance": {
            "trust_tier": governance.trust_tier,
            "provenance": (
                None
                if governance.provenance is None
                else {
                    "repo_url": governance.provenance.repo_url,
                    "commit_sha": governance.provenance.commit_sha,
                    "tree_path": governance.provenance.tree_path,
                    "publisher_identity": governance.provenance.publisher_identity,
                    "policy_profile": governance.provenance.policy_profile,
                }
            ),
        },
        "relationships": _version_checksum_relationships(relationships),
    }
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _sha256_hexdigest(canonical_json.encode("utf-8"))


def _version_checksum_relationships(
    relationships: tuple[RelationshipSelectorRecordInput, ...],
) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {
        "depends_on": [],
        "extends": [],
        "conflicts_with": [],
        "overlaps_with": [],
    }
    for item in relationships:
        grouped[item.edge_type].append(
            {
                "slug": item.slug,
                "version": item.version,
                "version_constraint": item.version_constraint,
                "optional": item.optional,
                "markers": list(item.markers),
            }
        )
    return grouped


def _sha256_hexdigest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
