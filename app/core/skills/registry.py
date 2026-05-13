"""Core normalized skill registry service."""

from __future__ import annotations

import hashlib
import json
from typing import cast

from app.core.audit_events import (
    build_enterprise_audit_event,
    build_lifecycle_audit_event,
    build_publish_audit_event,
)
from app.core.governance import (
    CallerIdentity,
    GovernancePolicy,
    LifecycleStatus,
    PolicyViolation,
    PromotionChannel,
    ProvenanceMetadata,
    ReviewState,
    SkillGovernanceInput,
    TrustTier,
)
from app.core.ports import (
    AuditPort,
    ContentRecordInput,
    CreateSkillVersionRecord,
    DuplicateSkillSlugPersistenceError,
    DuplicateSkillVersionPersistenceError,
    GovernanceRecordInput,
    MetadataRecordInput,
    RelationshipEdgeType,
    RelationshipSelectorRecordInput,
    SkillRegistryPort,
    SkillRegistryPersistenceError,
)

from .models import (
    SHA256_ALGORITHM,
    CreateSkillVersionCommand,
    DuplicateSkillVersionError,
    NamespaceRecord,
    OrganizationRecord,
    PolicyPackRecord,
    PublishIntent,
    SkillAlreadyExistsError,
    SkillChecksum,
    SkillContentDocument,
    SkillContentInput,
    SkillMetadata,
    SkillMetadataInput,
    SkillNotFoundError,
    SkillOwnershipUpdate,
    SkillRegistryError,
    SkillRelationshipSelector,
    SkillRelationshipsInput,
    SkillVersionDetail,
    SkillVersionGovernanceUpdate,
    SkillVersionNotFoundError,
    SkillVersionStatusUpdate,
    TrustEvidenceRecord,
)

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
        repository: SkillRegistryPort,
        audit_recorder: AuditPort,
        governance_policy: GovernancePolicy,
    ) -> None:
        self._repository = repository
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

        if self._repository.version_exists(slug=command.slug, version=command.version):
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
            namespace=normalized_governance.namespace,
            artifact_origin=normalized_governance.artifact_origin,
            review_state=normalized_governance.review_state or "approved",
            promotion_channel=normalized_governance.promotion_channel or "prod",
            policy_pack_slug=normalized_governance.policy_pack_slug,
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
            return self._repository.create_version(
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
        except DuplicateSkillVersionPersistenceError as exc:
            raise DuplicateSkillVersionError(slug=command.slug, version=command.version) from exc
        except DuplicateSkillSlugPersistenceError as exc:
            if command.intent == "create_skill":
                raise SkillAlreadyExistsError(slug=command.slug) from exc
            raise SkillRegistryError("Failed to persist immutable skill version.") from exc
        except SkillRegistryPersistenceError as exc:
            raise SkillRegistryError("Failed to persist immutable skill version.") from exc

    def _enforce_publish_intent(self, *, intent: PublishIntent, slug: str) -> None:
        skill_exists = self._repository.skill_exists(slug=slug)
        if intent == "create_skill":
            if skill_exists:
                raise SkillAlreadyExistsError(slug=slug)
            return
        if not skill_exists:
            raise SkillNotFoundError(slug=slug)

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
        stored = self._repository.get_version_detail(slug=slug, version=version)
        if stored is None:
            raise SkillVersionNotFoundError(slug=slug, version=version)

        try:
            self._governance_policy.evaluate_transition(
                caller=caller,
                current_status=stored.lifecycle_status,
                next_status=lifecycle_status,
                namespace=stored.namespace,
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

        updated = self._repository.update_version_status(
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
        return updated

    def create_organization(
        self,
        *,
        caller: CallerIdentity,
        slug: str,
        display_name: str,
    ) -> OrganizationRecord:
        """Create one enterprise organization."""
        event = build_enterprise_audit_event(
            caller=caller,
            event_type="enterprise.organization_created",
            surface="enterprise_admin",
            outcome="allowed",
            policy_profile=self._governance_policy.profile_name,
            payload={"organization": slug},
        )
        return self._repository.create_organization(
            slug=slug,
            display_name=display_name,
            audit_events=(event,),
        )

    def create_namespace(
        self,
        *,
        caller: CallerIdentity,
        slug: str,
        organization_slug: str,
        visibility: str,
    ) -> NamespaceRecord:
        """Create one enterprise namespace."""
        event = build_enterprise_audit_event(
            caller=caller,
            event_type="enterprise.namespace_created",
            surface="enterprise_admin",
            outcome="allowed",
            policy_profile=self._governance_policy.profile_name,
            payload={
                "namespace": slug,
                "organization": organization_slug,
                "visibility": visibility,
            },
        )
        return self._repository.create_namespace(
            slug=slug,
            organization_slug=organization_slug,
            visibility=visibility,
            audit_events=(event,),
        )

    def upsert_policy_pack(
        self,
        *,
        caller: CallerIdentity,
        slug: str,
        description: str | None,
        rules: dict[str, object],
    ) -> PolicyPackRecord:
        """Create or update one policy pack reference."""
        event = build_enterprise_audit_event(
            caller=caller,
            event_type="enterprise.policy_pack_upserted",
            surface="enterprise_admin",
            outcome="allowed",
            policy_profile=self._governance_policy.profile_name,
            payload={"policy_pack": slug},
        )
        return self._repository.upsert_policy_pack(
            slug=slug,
            description=description,
            rules=rules,
            audit_events=(event,),
        )

    def update_skill_ownership(
        self,
        *,
        caller: CallerIdentity,
        slug: str,
        namespace: str,
    ) -> SkillOwnershipUpdate:
        """Move one skill identity into a namespace."""
        event = build_enterprise_audit_event(
            caller=caller,
            event_type="enterprise.skill_ownership_updated",
            surface="enterprise_admin",
            outcome="allowed",
            policy_profile=self._governance_policy.profile_name,
            payload={"slug": slug, "namespace": namespace},
        )
        updated = self._repository.update_skill_ownership(
            slug=slug,
            namespace=namespace,
            audit_events=(event,),
        )
        if updated is None:
            raise SkillNotFoundError(slug=slug)
        return updated

    def update_version_governance(
        self,
        *,
        caller: CallerIdentity,
        slug: str,
        version: str,
        review_state: ReviewState | None = None,
        promotion_channel: PromotionChannel | None = None,
        trust_tier: TrustTier | None = None,
        policy_pack_slug: str | None = None,
        note: str | None = None,
    ) -> SkillVersionGovernanceUpdate:
        """Update mutable enterprise governance state for one immutable version."""
        stored = self._repository.get_version_detail(slug=slug, version=version)
        if stored is None:
            raise SkillVersionNotFoundError(slug=slug, version=version)
        if not caller.has_namespace_grant(
            namespace=stored.namespace,
            role="review",
            promotion_channel=stored.promotion_channel,
        ):
            denied_event = build_enterprise_audit_event(
                caller=caller,
                event_type="enterprise.version_governance_update_denied",
                surface="enterprise_admin",
                outcome="denied",
                policy_profile=self._governance_policy.profile_name,
                reason_code="POLICY_NAMESPACE_FORBIDDEN",
                payload={
                    "slug": slug,
                    "version": version,
                    "namespace": stored.namespace,
                    "required_role": "review",
                },
            )
            self._audit_recorder.record_event(
                event_type=denied_event.event_type,
                payload=denied_event.payload,
            )
            raise PolicyViolation(
                code="POLICY_NAMESPACE_FORBIDDEN",
                message="Caller is not allowed to review this namespace.",
                details={"namespace": stored.namespace, "required_role": "review"},
            )
        event = build_enterprise_audit_event(
            caller=caller,
            event_type="enterprise.version_governance_updated",
            surface="enterprise_admin",
            outcome="allowed",
            policy_profile=self._governance_policy.profile_name,
            payload={
                "slug": slug,
                "version": version,
                "namespace": stored.namespace,
                "previous_review_state": stored.review_state,
                "next_review_state": review_state,
                "previous_promotion_channel": stored.promotion_channel,
                "next_promotion_channel": promotion_channel,
                "previous_trust_tier": stored.trust_tier,
                "next_trust_tier": trust_tier,
                "policy_pack": policy_pack_slug,
                "note": note,
            },
        )
        updated = self._repository.update_version_governance(
            slug=slug,
            version=version,
            review_state=review_state,
            promotion_channel=promotion_channel,
            trust_tier=trust_tier,
            policy_pack_slug=policy_pack_slug,
            audit_events=(event,),
        )
        if updated is None:
            raise SkillVersionNotFoundError(slug=slug, version=version)
        return updated

    def add_trust_evidence(
        self,
        *,
        caller: CallerIdentity,
        slug: str,
        version: str,
        evidence_type: str,
        subject: str,
        digest: str | None,
        uri: str | None,
        payload: dict[str, object] | None,
    ) -> TrustEvidenceRecord:
        """Append evidence for one immutable version without exposing raw payloads in response."""
        stored = self._repository.get_version_detail(slug=slug, version=version)
        if stored is None:
            raise SkillVersionNotFoundError(slug=slug, version=version)
        if not caller.has_namespace_grant(
            namespace=stored.namespace,
            role="review",
            promotion_channel=stored.promotion_channel,
        ):
            denied_event = build_enterprise_audit_event(
                caller=caller,
                event_type="enterprise.trust_evidence_add_denied",
                surface="enterprise_admin",
                outcome="denied",
                policy_profile=self._governance_policy.profile_name,
                reason_code="POLICY_NAMESPACE_FORBIDDEN",
                payload={
                    "slug": slug,
                    "version": version,
                    "namespace": stored.namespace,
                    "required_role": "review",
                },
            )
            self._audit_recorder.record_event(
                event_type=denied_event.event_type,
                payload=denied_event.payload,
            )
            raise PolicyViolation(
                code="POLICY_NAMESPACE_FORBIDDEN",
                message="Caller is not allowed to add trust evidence for this namespace.",
                details={"namespace": stored.namespace, "required_role": "review"},
            )
        event = build_enterprise_audit_event(
            caller=caller,
            event_type="enterprise.trust_evidence_added",
            surface="enterprise_admin",
            outcome="allowed",
            policy_profile=self._governance_policy.profile_name,
            payload={
                "slug": slug,
                "version": version,
                "namespace": stored.namespace,
                "evidence_type": evidence_type,
                "subject": subject,
                "digest_present": digest is not None,
                "uri_present": uri is not None,
            },
        )
        created = self._repository.add_trust_evidence(
            slug=slug,
            version=version,
            evidence_type=evidence_type,
            subject=subject,
            digest=digest,
            uri=uri,
            payload=payload,
            audit_events=(event,),
        )
        if created is None:
            raise SkillVersionNotFoundError(slug=slug, version=version)
        return created


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
