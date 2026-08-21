"""HTTP contract for body-based discovery candidate lookup."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.core.skills.discovery import SkillDiscoveryRequest as CoreSkillDiscoveryRequest
from app.core.skills.models import SkillCoordinate
from app.interface.api.dependencies import ReadCallerDep, SkillDiscoveryServiceDep
from app.interface.api.response_docs import ApiResponses, invalid_request_response
from app.interface.dto.examples import (
    DISCOVERY_REQUEST_EXAMPLE,
    DISCOVERY_RESPONSE_EXAMPLE,
)
from app.interface.dto.skills_discovery import SkillDiscoveryRequest, SkillDiscoveryResponse

router = APIRouter(tags=["discovery"])

DISCOVERY_RESPONSES: ApiResponses = {
    status.HTTP_200_OK: {
        "description": "Ordered candidate slugs returned successfully.",
        "content": {"application/json": {"example": DISCOVERY_RESPONSE_EXAMPLE}},
    },
    **invalid_request_response(description="The discovery request is invalid."),
}


@router.post(
    "/discovery",
    operation_id="discoverSkillCandidates",
    summary="Discover candidate skill slugs",
    description=(
        "Return ordered candidate slugs from indexed metadata and description search. "
        "This route is discovery-only: it does not resolve dependencies, choose a final "
        "candidate, or perform solver behavior."
    ),
    response_model=SkillDiscoveryResponse,
    response_model_exclude_unset=True,
    responses=DISCOVERY_RESPONSES,
    openapi_extra={
        "requestBody": {"content": {"application/json": {"example": DISCOVERY_REQUEST_EXAMPLE}}}
    },
)
def discover_skills(
    request: SkillDiscoveryRequest,
    discovery_service: SkillDiscoveryServiceDep,
    caller: ReadCallerDep,
) -> SkillDiscoveryResponse:
    """Return ordered candidate slugs for the provided discovery request."""
    candidates = discovery_service.discover_candidates(
        caller=caller,
        request=CoreSkillDiscoveryRequest(
            query=request.query,
            tags=tuple(request.tags),
            context_skills=tuple(
                SkillCoordinate(slug=item.slug, version=item.version)
                for item in request.context_skills
            ),
        ),
    )
    return SkillDiscoveryResponse(candidates=list(candidates))
