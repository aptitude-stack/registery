"""Enterprise control-plane API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Request, status
from fastapi.responses import JSONResponse

from app.core.skills.models import SkillNotFoundError, SkillRegistryError, SkillVersionNotFoundError
from app.interface.api.dependencies import AdminCallerDep, ReviewCallerDep, SkillRegistryServiceDep
from app.interface.api.errors import error_response
from app.interface.dto.enterprise import (
    NamespaceCreateRequest,
    NamespaceResponse,
    OrganizationCreateRequest,
    OrganizationResponse,
    PolicyPackResponse,
    PolicyPackUpsertRequest,
    SkillOwnershipResponse,
    SkillOwnershipUpdateRequest,
    TrustEvidenceCreateRequest,
    TrustEvidenceResponse,
    VersionGovernanceResponse,
    VersionGovernanceUpdateRequest,
)
from app.interface.validation import GOVERNANCE_SLUG_PATTERN, SEMVER_PATTERN, SLUG_PATTERN

router = APIRouter(prefix="/admin", tags=["enterprise-admin"])


@router.post(
    "/organizations",
    operation_id="createOrganization",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_organization(
    request: OrganizationCreateRequest,
    registry_service: SkillRegistryServiceDep,
    caller: AdminCallerDep,
) -> OrganizationResponse:
    """Create one enterprise organization."""
    created = registry_service.create_organization(
        caller=caller,
        slug=request.slug,
        display_name=request.display_name,
    )
    return OrganizationResponse(
        slug=created.slug,
        display_name=created.display_name,
        created_at=created.created_at,
    )


@router.post(
    "/namespaces",
    operation_id="createNamespace",
    response_model=NamespaceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_namespace(
    request: NamespaceCreateRequest,
    registry_service: SkillRegistryServiceDep,
    caller: AdminCallerDep,
) -> NamespaceResponse:
    """Create one enterprise namespace."""
    created = registry_service.create_namespace(
        caller=caller,
        slug=request.slug,
        organization_slug=request.organization_slug,
        visibility=request.visibility,
    )
    return NamespaceResponse(
        slug=created.slug,
        organization_slug=created.organization_slug,
        visibility=created.visibility,
        created_at=created.created_at,
    )


@router.put(
    "/policy-packs/{slug}",
    operation_id="upsertPolicyPack",
    response_model=PolicyPackResponse,
)
def upsert_policy_pack(
    slug: Annotated[str, Path(pattern=GOVERNANCE_SLUG_PATTERN)],
    request: PolicyPackUpsertRequest,
    registry_service: SkillRegistryServiceDep,
    caller: AdminCallerDep,
) -> PolicyPackResponse:
    """Create or update one policy-pack reference."""
    updated = registry_service.upsert_policy_pack(
        caller=caller,
        slug=slug,
        description=request.description,
        rules=request.rules,
    )
    return PolicyPackResponse(
        slug=updated.slug, description=updated.description, rules=updated.rules
    )


@router.patch(
    "/skills/{slug}/ownership",
    operation_id="updateSkillOwnership",
    response_model=SkillOwnershipResponse,
)
def update_skill_ownership(
    http_request: Request,
    request: SkillOwnershipUpdateRequest,
    slug: Annotated[str, Path(pattern=SLUG_PATTERN)],
    registry_service: SkillRegistryServiceDep,
    caller: AdminCallerDep,
) -> SkillOwnershipResponse | JSONResponse:
    """Move one skill identity into a namespace."""
    try:
        updated = registry_service.update_skill_ownership(
            caller=caller,
            slug=slug,
            namespace=request.namespace,
        )
    except SkillNotFoundError as exc:
        return error_response(
            request=http_request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="SKILL_NOT_FOUND",
            message=str(exc),
            details={"slug": exc.slug},
        )
    return SkillOwnershipResponse(slug=updated.slug, namespace=updated.namespace)


@router.patch(
    "/skills/{slug}/{version}/governance",
    operation_id="updateSkillVersionGovernance",
    response_model=VersionGovernanceResponse,
)
def update_skill_version_governance(
    http_request: Request,
    request: VersionGovernanceUpdateRequest,
    slug: Annotated[str, Path(pattern=SLUG_PATTERN)],
    version: Annotated[str, Path(pattern=SEMVER_PATTERN)],
    registry_service: SkillRegistryServiceDep,
    caller: ReviewCallerDep,
) -> VersionGovernanceResponse | JSONResponse:
    """Update mutable enterprise governance state for one immutable version."""
    try:
        updated = registry_service.update_version_governance(
            caller=caller,
            slug=slug,
            version=version,
            review_state=request.review_state,
            promotion_channel=request.promotion_channel,
            trust_tier=request.trust_tier,
            policy_pack_slug=request.policy_pack_slug,
            note=request.note,
        )
    except SkillVersionNotFoundError as exc:
        return _version_not_found_response(http_request, exc)
    return VersionGovernanceResponse(
        slug=updated.slug,
        version=updated.version,
        lifecycle_status=updated.lifecycle_status,
        trust_tier=updated.trust_tier,
        namespace=updated.namespace,
        artifact_origin=updated.artifact_origin,
        review_state=updated.review_state,
        promotion_channel=updated.promotion_channel,
        policy_pack_slug=updated.policy_pack_slug,
    )


@router.post(
    "/skills/{slug}/{version}/trust-evidence",
    operation_id="addSkillVersionTrustEvidence",
    response_model=TrustEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_skill_version_trust_evidence(
    http_request: Request,
    request: TrustEvidenceCreateRequest,
    slug: Annotated[str, Path(pattern=SLUG_PATTERN)],
    version: Annotated[str, Path(pattern=SEMVER_PATTERN)],
    registry_service: SkillRegistryServiceDep,
    caller: ReviewCallerDep,
) -> TrustEvidenceResponse | JSONResponse:
    """Append trust evidence to one immutable version."""
    try:
        created = registry_service.add_trust_evidence(
            caller=caller,
            slug=slug,
            version=version,
            evidence_type=request.evidence_type,
            subject=request.subject,
            digest=request.digest,
            uri=request.uri,
            payload=request.payload,
        )
    except SkillVersionNotFoundError as exc:
        return _version_not_found_response(http_request, exc)
    except SkillRegistryError as exc:
        return error_response(
            request=http_request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="TRUST_EVIDENCE_FAILURE",
            message=str(exc),
        )
    return TrustEvidenceResponse(
        slug=created.slug,
        version=created.version,
        evidence_type=created.evidence_type,
        subject=created.subject,
        digest=created.digest,
        uri=created.uri,
        created_at=created.created_at,
    )


def _version_not_found_response(
    request: Request,
    exc: SkillVersionNotFoundError,
) -> JSONResponse:
    return error_response(
        request=request,
        status_code=status.HTTP_404_NOT_FOUND,
        code="SKILL_VERSION_NOT_FOUND",
        message=str(exc),
        details={"slug": exc.slug, "version": exc.version},
    )
