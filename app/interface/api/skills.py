"""Primary normalized skill write and lifecycle routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, Path, Request, UploadFile, status
from fastapi.responses import JSONResponse

from app.core.skills.registry import (
    DuplicateSkillVersionError,
    SkillAlreadyExistsError,
    SkillNotFoundError,
    SkillRegistryError,
    SkillVersionNotFoundError,
)
from app.interface.api.dependencies import (
    AdminCallerDep,
    PublishCallerDep,
    SkillRegistryServiceDep,
)
from app.interface.api.errors import error_response
from app.interface.api.response_docs import ApiResponses, invalid_request_response
from app.interface.api.skill_api_support_fetch import to_metadata_response
from app.interface.api.skill_api_support_lifecycle import to_version_status_response
from app.interface.api.skill_api_support_publish import (
    parse_publish_request_metadata,
    read_publish_bundle_bytes,
    to_create_command,
    validate_publish_bundle,
)
from app.interface.dto.errors import ErrorEnvelope
from app.interface.dto.examples import (
    CONTENT_STORAGE_FAILURE_ERROR_EXAMPLE,
    DUPLICATE_SKILL_VERSION_ERROR_EXAMPLE,
    PUBLISH_REQUEST_EXAMPLE,
    SKILL_ALREADY_EXISTS_ERROR_EXAMPLE,
    SKILL_NOT_FOUND_ERROR_EXAMPLE,
    SKILL_VERSION_METADATA_RESPONSE_EXAMPLE,
    SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE,
    SKILL_VERSION_STATUS_RESPONSE_EXAMPLE,
)
from app.interface.dto.skills_fetch import SkillVersionMetadataResponse
from app.interface.dto.skills_lifecycle import (
    SkillVersionStatusResponse,
    SkillVersionStatusUpdateRequest,
)
from app.interface.validation import SEMVER_PATTERN, SLUG_PATTERN

router = APIRouter(tags=["publish"])

REQUEST_VALIDATION_ERROR_RESPONSE: ApiResponses = invalid_request_response(
    description="The request body, path parameters, or query parameters are invalid."
)

PUBLISH_RESPONSES: ApiResponses = {
    status.HTTP_201_CREATED: {
        "description": "Immutable skill version published successfully.",
        "content": {"application/json": {"example": SKILL_VERSION_METADATA_RESPONSE_EXAMPLE}},
    },
    status.HTTP_409_CONFLICT: {
        "model": ErrorEnvelope,
        "description": (
            "The requested publish conflicts with existing state because the immutable "
            "`slug@version` already exists or the skill slug already exists for "
            "`intent=create_skill`."
        ),
        "content": {
            "application/json": {
                "examples": {
                    "duplicate_skill_version": {
                        "summary": "Duplicate immutable version",
                        "value": DUPLICATE_SKILL_VERSION_ERROR_EXAMPLE,
                    },
                    "skill_already_exists": {
                        "summary": "Skill slug already exists",
                        "value": SKILL_ALREADY_EXISTS_ERROR_EXAMPLE,
                    },
                }
            }
        },
    },
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorEnvelope,
        "description": "The requested skill slug does not exist for `intent=publish_version`.",
        "content": {"application/json": {"example": SKILL_NOT_FOUND_ERROR_EXAMPLE}},
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "model": ErrorEnvelope,
        "description": "Normalized content or metadata persistence failed.",
        "content": {"application/json": {"example": CONTENT_STORAGE_FAILURE_ERROR_EXAMPLE}},
    },
    **REQUEST_VALIDATION_ERROR_RESPONSE,
}

STATUS_RESPONSES: ApiResponses = {
    status.HTTP_200_OK: {
        "description": "Lifecycle status updated successfully.",
        "content": {"application/json": {"example": SKILL_VERSION_STATUS_RESPONSE_EXAMPLE}},
    },
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorEnvelope,
        "description": "The requested immutable `slug@version` does not exist.",
        "content": {"application/json": {"example": SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE}},
    },
    **REQUEST_VALIDATION_ERROR_RESPONSE,
}


@router.post(
    "/skills/{slug}",
    operation_id="createSkillVersion",
    summary="Publish an immutable skill version",
    description=(
        "Create a new immutable skill version for the slug in the path from a "
        "`multipart/form-data` request containing one JSON metadata part and "
        "one `.tar.zst` artifact."
    ),
    response_model=SkillVersionMetadataResponse,
    response_model_exclude_unset=True,
    status_code=status.HTTP_201_CREATED,
    responses=PUBLISH_RESPONSES,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["metadata", "bundle"],
                        "properties": {
                            "metadata": {
                                "type": "string",
                                "description": "JSON-encoded publish metadata payload.",
                            },
                            "bundle": {
                                "type": "string",
                                "format": "binary",
                                "description": "Validated immutable `.tar.zst` skill artifact.",
                            },
                        },
                    },
                    "encoding": {
                        "metadata": {"contentType": "application/json"},
                        "bundle": {"contentType": "application/zstd"},
                    },
                    "example": {
                        "metadata": PUBLISH_REQUEST_EXAMPLE,
                    },
                }
            },
        }
    },
)
def create_skill_version(
    http_request: Request,
    slug: Annotated[
        str,
        Path(pattern=SLUG_PATTERN, description="Stable public slug for the skill identity."),
    ],
    metadata: Annotated[
        str,
        Form(description="JSON-encoded publish metadata and relationship declarations."),
    ],
    bundle: Annotated[
        UploadFile,
        File(description="Opaque `.tar.zst` artifact persisted exactly as uploaded."),
    ],
    registry_service: SkillRegistryServiceDep,
    caller: PublishCallerDep,
) -> SkillVersionMetadataResponse | JSONResponse:
    """Publish one immutable normalized skill version."""
    request = parse_publish_request_metadata(metadata)
    bundle_bytes = read_publish_bundle_bytes(bundle)
    bundle_media_type = validate_publish_bundle(
        bundle_bytes=bundle_bytes,
        filename=bundle.filename,
        media_type=bundle.content_type,
    )

    try:
        stored = registry_service.publish_version(
            caller=caller,
            command=to_create_command(
                slug,
                request,
                bundle_bytes=bundle_bytes,
                bundle_media_type=bundle_media_type,
            ),
        )
        return to_metadata_response(stored)
    except DuplicateSkillVersionError as exc:
        return error_response(
            request=http_request,
            status_code=status.HTTP_409_CONFLICT,
            code="DUPLICATE_SKILL_VERSION",
            message=str(exc),
            details={"slug": exc.slug, "version": exc.version},
        )
    except SkillAlreadyExistsError as exc:
        return error_response(
            request=http_request,
            status_code=status.HTTP_409_CONFLICT,
            code="SKILL_ALREADY_EXISTS",
            message=str(exc),
            details={"slug": exc.slug},
        )
    except SkillNotFoundError as exc:
        return error_response(
            request=http_request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="SKILL_NOT_FOUND",
            message=str(exc),
            details={"slug": exc.slug},
        )
    except SkillRegistryError as exc:
        return error_response(
            request=http_request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="CONTENT_STORAGE_FAILURE",
            message=str(exc),
        )


@router.patch(
    "/skills/{slug}/{version}/status",
    operation_id="updateSkillVersionStatus",
    summary="Update immutable version lifecycle status",
    description="Transition the lifecycle state for one immutable skill version.",
    response_model=SkillVersionStatusResponse,
    response_model_exclude_unset=True,
    responses=STATUS_RESPONSES,
    include_in_schema=False,
)
def update_skill_version_status(
    http_request: Request,
    request: SkillVersionStatusUpdateRequest,
    registry_service: SkillRegistryServiceDep,
    caller: AdminCallerDep,
    slug: Annotated[
        str,
        Path(pattern=SLUG_PATTERN, description="Stable public slug of the skill."),
    ],
    version: Annotated[
        str,
        Path(pattern=SEMVER_PATTERN, description="Exact immutable semantic version to update."),
    ],
) -> SkillVersionStatusResponse | JSONResponse:
    """Update lifecycle state for one immutable version."""
    try:
        updated = registry_service.update_version_status(
            caller=caller,
            slug=slug,
            version=version,
            lifecycle_status=request.status,
            note=request.note,
        )
        return to_version_status_response(updated)
    except SkillVersionNotFoundError as exc:
        return error_response(
            request=http_request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="SKILL_VERSION_NOT_FOUND",
            message=str(exc),
            details={"slug": exc.slug, "version": exc.version},
        )
