"""Operational routes for metrics exposition."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.core.dependencies import AdminCallerDep
from app.observability.metrics import generate_latest, metrics_content_type

router = APIRouter(tags=["operability"])


@router.get(
    "/metrics",
    operation_id="getMetrics",
    summary="Expose Prometheus metrics",
    description=(
        "Return Prometheus-compatible operational metrics for scraping and local "
        "dashboard validation."
    ),
    response_model=None,
    include_in_schema=False,
)
def get_metrics(_caller: AdminCallerDep) -> Response:
    """Expose the current Prometheus metrics payload."""
    return Response(
        content=generate_latest(),
        media_type=metrics_content_type(),
    )
