"""HTTP contract for exact metadata and immutable markdown fetch endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Request, Response, status
from fastapi.responses import JSONResponse

from app.core.dependencies import ReadCallerDep, SkillFetchServiceDep
from app.core.skills.models import SkillNotFoundError, SkillVersionNotFoundError
from app.interface.api.errors import error_response
from app.interface.api.response_docs import (
    ApiResponses,
    invalid_request_response,
    skill_not_found_response,
    skill_version_not_found_response,
)
from app.interface.api.skill_api_support_fetch import to_metadata_response, to_version_list_response
from app.interface.dto.examples import (
    SKILL_VERSION_LIST_RESPONSE_EXAMPLE,
    SKILL_VERSION_METADATA_RESPONSE_EXAMPLE,
)
from app.interface.dto.skills_fetch import SkillVersionListResponse, SkillVersionMetadataResponse
from app.interface.validation import SEMVER_PATTERN, SLUG_PATTERN

router = APIRouter(tags=["fetch"])

NOT_FOUND_RESPONSE = skill_version_not_found_response(
    description="The requested immutable `slug@version` does not exist."
)
SKILL_NOT_FOUND_RESPONSE = skill_not_found_response(
    description="The requested skill slug does not exist or has no visible versions."
)
PATH_VALIDATION_ERROR_RESPONSE = invalid_request_response(
    description="The path parameters are invalid."
)

METADATA_RESPONSES: ApiResponses = {
    status.HTTP_200_OK: {
        "description": "Exact metadata returned successfully.",
        "content": {"application/json": {"example": SKILL_VERSION_METADATA_RESPONSE_EXAMPLE}},
    },
    **NOT_FOUND_RESPONSE,
    **PATH_VALIDATION_ERROR_RESPONSE,
}

CONTENT_RESPONSES: ApiResponses = {
    status.HTTP_200_OK: {
        "description": "Immutable markdown content returned successfully.",
        "content": {
            "text/markdown": {
                "schema": {
                    "type": "string",
                }
            }
        },
    },
    **NOT_FOUND_RESPONSE,
    **PATH_VALIDATION_ERROR_RESPONSE,
}

LIST_RESPONSES: ApiResponses = {
    status.HTTP_200_OK: {
        "description": "Visible immutable versions returned successfully.",
        "content": {"application/json": {"example": SKILL_VERSION_LIST_RESPONSE_EXAMPLE}},
    },
    **SKILL_NOT_FOUND_RESPONSE,
    **PATH_VALIDATION_ERROR_RESPONSE,
}


@router.get(
    "/skills/{slug}",
    operation_id="listImmutableVersions",
    summary="List visible immutable versions",
    description="Return the visible immutable versions for one skill identity.",
    response_model=SkillVersionListResponse,
    response_model_exclude_unset=True,
    responses=LIST_RESPONSES,
)
def list_skill_versions(
    request: Request,
    slug: Annotated[
        str,
        Path(pattern=SLUG_PATTERN, description="Stable public slug of the requested skill."),
    ],
    fetch_service: SkillFetchServiceDep,
    caller: ReadCallerDep,
) -> SkillVersionListResponse | JSONResponse:
    """Return the visible immutable versions for one skill identity."""
    try:
        detail = fetch_service.list_versions(caller=caller, slug=slug)
    except SkillNotFoundError as exc:
        return error_response(
            request=request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="SKILL_NOT_FOUND",
            message=str(exc),
            details={"slug": exc.slug},
        )

    return to_version_list_response(detail)


@router.get(
    "/skills/{slug}/{version}",
    operation_id="getImmutableMetadata",
    summary="Fetch immutable metadata",
    description="Return the exact metadata response for one exact `slug@version`.",
    response_model=SkillVersionMetadataResponse,
    response_model_exclude_unset=True,
    responses=METADATA_RESPONSES,
)
def get_version_metadata(
    request: Request,
    slug: Annotated[
        str,
        Path(pattern=SLUG_PATTERN, description="Stable public slug of the requested skill."),
    ],
    version: Annotated[
        str,
        Path(
            pattern=SEMVER_PATTERN,
            description="Exact immutable semantic version of the requested skill.",
        ),
    ],
    fetch_service: SkillFetchServiceDep,
    caller: ReadCallerDep,
) -> SkillVersionMetadataResponse | JSONResponse:
    """Return the exact metadata response for one exact coordinate."""
    try:
        detail = fetch_service.get_version_metadata(
            caller=caller,
            slug=slug,
            version=version,
        )
    except SkillVersionNotFoundError as exc:
        return error_response(
            request=request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="SKILL_VERSION_NOT_FOUND",
            message=str(exc),
            details={"slug": exc.slug, "version": exc.version},
        )

    return to_metadata_response(detail)


@router.get(
    "/skills/{slug}/{version}/content",
    operation_id="getImmutableContent",
    summary="Fetch immutable markdown content",
    description="Return the immutable markdown body for one exact `slug@version`.",
    response_model=None,
    responses=CONTENT_RESPONSES,
)
def get_version_content(
    request: Request,
    slug: Annotated[
        str,
        Path(pattern=SLUG_PATTERN, description="Stable public slug of the requested skill."),
    ],
    version: Annotated[
        str,
        Path(
            pattern=SEMVER_PATTERN,
            description="Exact immutable semantic version of the requested skill.",
        ),
    ],
    fetch_service: SkillFetchServiceDep,
    caller: ReadCallerDep,
) -> Response | JSONResponse:
    """Return the immutable markdown body for one exact coordinate."""
    try:
        document = fetch_service.get_content(
            caller=caller,
            slug=slug,
            version=version,
        )
    except SkillVersionNotFoundError as exc:
        return error_response(
            request=request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="SKILL_VERSION_NOT_FOUND",
            message=str(exc),
            details={"slug": exc.slug, "version": exc.version},
        )

    return Response(
        content=document.raw_markdown.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={
            "ETag": document.checksum.digest,
            "Cache-Control": "public, immutable",
            "Content-Length": str(document.size_bytes),
        },
    )
