"""Health and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.interface.api.dependencies import ReadinessServiceDep, SettingsDep
from app.interface.dto.health import HealthzResponse, ReadinessCheck, ReadyzResponse
from app.observability.metrics import set_database_readiness

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthzResponse)
def get_healthz(settings: SettingsDep) -> HealthzResponse:
    """Return process liveness for lightweight probes."""
    return HealthzResponse(service=settings.app_name, environment=settings.app_env)


@router.get("/readyz", response_model=ReadyzResponse)
def get_readyz(response: Response, readiness_service: ReadinessServiceDep) -> ReadyzResponse:
    """Return dependency readiness, including a database connectivity check."""
    readiness_report = readiness_service.get_status()
    set_database_readiness(is_ready=readiness_report.status == "ready")
    checks = [
        ReadinessCheck(name=check.name, status=check.status, detail=check.detail)
        for check in readiness_report.checks
    ]
    if readiness_report.status == "ready":
        return ReadyzResponse(status="ready", checks=checks)

    response.status_code = 503
    return ReadyzResponse(status="not_ready", checks=checks)
