"""HTTP contract for aggregate skill telemetry endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import JSONResponse

from app.core.skills.models import (
    EmptyStarEventBatchError,
    StarEvent,
    StarEventBatchTooLargeError,
    UnknownStarEventSkillsError,
)
from app.interface.api.dependencies import (
    SkillTelemetryServiceDep,
    TelemetryCallerDep,
)
from app.interface.api.errors import error_response
from app.interface.api.response_docs import ApiResponses, invalid_request_response
from app.interface.dto.errors import ErrorEnvelope
from app.interface.dto.examples import (
    STAR_EVENT_BATCH_REQUEST_EXAMPLE,
    STAR_EVENT_BATCH_RESPONSE_EXAMPLE,
    UNKNOWN_SKILL_SLUG_ERROR_EXAMPLE,
)
from app.interface.dto.skills_telemetry import (
    StarCountResponse,
    StarEventBatchRequest,
    StarEventBatchResponse,
    UserStarredSkillsResponse,
)

router = APIRouter(tags=["telemetry"])

STAR_EVENTS_RESPONSES: ApiResponses = {
    status.HTTP_200_OK: {
        "description": "Star events accepted and aggregate counts returned.",
        "content": {"application/json": {"example": STAR_EVENT_BATCH_RESPONSE_EXAMPLE}},
    },
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorEnvelope,
        "description": "One or more referenced skill slugs do not exist.",
        "content": {"application/json": {"example": UNKNOWN_SKILL_SLUG_ERROR_EXAMPLE}},
    },
    **invalid_request_response(description="The request body is invalid."),
}


@router.post(
    "/catalog/star-events",
    operation_id="recordSkillStarEvents",
    summary="Record a batch of skill star toggle events",
    description=(
        "Apply a batch of `star` and `unstar` toggle events for one or more skill "
        "identities and return the post-update aggregate star counts. Counts are "
        "clamped at zero. The endpoint requires a service token with the "
        "`telemetry` scope and is intended for trusted server-side aggregation, "
        "not direct user traffic."
    ),
    response_model=StarEventBatchResponse,
    response_model_exclude_unset=True,
    responses=STAR_EVENTS_RESPONSES,
    openapi_extra={
        "requestBody": {
            "content": {"application/json": {"example": STAR_EVENT_BATCH_REQUEST_EXAMPLE}}
        }
    },
)
def record_skill_star_events(
    http_request: Request,
    request: StarEventBatchRequest,
    telemetry_service: SkillTelemetryServiceDep,
    caller: TelemetryCallerDep,
) -> StarEventBatchResponse | JSONResponse:
    """Record a batch of star/unstar events and return aggregate star counts."""
    try:
        events = tuple(StarEvent(slug=event.slug, action=event.action) for event in request.events)
        counts = telemetry_service.record_user_star_events(
            caller=caller,
            user_subject=request.user_subject,
            events=events,
        )
    except EmptyStarEventBatchError as exc:
        return error_response(
            request=http_request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="INVALID_REQUEST",
            message=str(exc),
        )
    except StarEventBatchTooLargeError as exc:
        return error_response(
            request=http_request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="INVALID_REQUEST",
            message=str(exc),
            details={"limit": exc.limit, "received": exc.received},
        )
    except UnknownStarEventSkillsError as exc:
        return error_response(
            request=http_request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="STAR_EVENT_UNKNOWN_SKILL",
            message=str(exc),
            details={"slugs": list(exc.slugs)},
        )

    return StarEventBatchResponse(
        accepted=len(request.events),
        counts=[
            StarCountResponse(slug=count.slug, star_count=count.star_count) for count in counts
        ],
    )


@router.get(
    "/catalog/user-stars",
    operation_id="listUserStarredSkills",
    summary="List starred skills for a trusted user subject",
    description=(
        "Return skill slugs starred by one authenticated user subject. The endpoint "
        "requires a service token with the `telemetry` scope and is intended for "
        "trusted server-side callers."
    ),
    response_model=UserStarredSkillsResponse,
)
def list_user_starred_skills(
    user_subject: Annotated[
        str,
        Query(min_length=1, max_length=320, description="Trusted authenticated user subject."),
    ],
    telemetry_service: SkillTelemetryServiceDep,
    caller: TelemetryCallerDep,
) -> UserStarredSkillsResponse:
    """Return starred skill slugs for one authenticated user subject."""
    return UserStarredSkillsResponse(
        starred_slugs=list(
            telemetry_service.list_user_starred_skill_slugs(
                caller=caller,
                user_subject=user_subject,
            )
        )
    )
