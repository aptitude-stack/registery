"""HTTP contract for exact first-degree dependency reads."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Request, status
from fastapi.responses import JSONResponse

from app.interface.api.dependencies import ReadCallerDep, SkillResolutionServiceDep
from app.core.skills.models import SkillVersionNotFoundError
from app.interface.api.errors import error_response
from app.interface.api.response_docs import (
    ApiResponses,
    invalid_request_response,
    skill_version_not_found_response,
)
from app.interface.api.skill_api_support_resolution import to_dependency_resolution_response
from app.interface.dto.examples import RESOLUTION_RESPONSE_EXAMPLE
from app.interface.dto.skills_resolution import SkillDependencyResolutionResponse
from app.interface.validation import SEMVER_PATTERN, SLUG_PATTERN

router = APIRouter(tags=["resolution"])

RESOLUTION_RESPONSES: ApiResponses = {
    status.HTTP_200_OK: {
        "description": "Direct dependency declarations returned successfully.",
        "content": {"application/json": {"example": RESOLUTION_RESPONSE_EXAMPLE}},
    },
    **skill_version_not_found_response(
        description="The requested immutable `slug@version` does not exist."
    ),
    **invalid_request_response(description="The path parameters are invalid."),
}


@router.get(
    "/resolution/{slug}/{version}",
    operation_id="getDirectDependencies",
    summary="Read direct immutable dependencies",
    description=(
        "Return authored direct `depends_on` declarations for one exact immutable version. "
        "This route does not recurse, solve version constraints, or return non-dependency "
        "relationship families."
    ),
    response_model=SkillDependencyResolutionResponse,
    response_model_exclude_unset=True,
    responses=RESOLUTION_RESPONSES,
)
def get_direct_dependencies(
    request: Request,
    slug: Annotated[
        str,
        Path(pattern=SLUG_PATTERN, description="Stable public slug of the skill to resolve."),
    ],
    version: Annotated[
        str,
        Path(pattern=SEMVER_PATTERN, description="Exact immutable semantic version to resolve."),
    ],
    resolution_service: SkillResolutionServiceDep,
    caller: ReadCallerDep,
) -> SkillDependencyResolutionResponse | JSONResponse:
    """Return direct dependency selectors exactly as authored."""
    try:
        resolved = resolution_service.get_direct_dependencies(
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

    return to_dependency_resolution_response(resolved)
