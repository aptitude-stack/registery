"""Application entrypoint and startup wiring."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from typing import cast
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ExceptionHandler

from app.core.governance import PolicyViolation
from app.core.settings import Settings, get_settings, load_settings, reset_settings_cache
from app.interface.api.discovery import router as discovery_router
from app.interface.api.errors import (
    ApiError,
    api_error_exception_handler,
    policy_violation_exception_handler,
    request_validation_exception_handler,
)
from app.interface.api.fetch import router as fetch_router
from app.interface.api.health import router as health_router
from app.interface.api.operability import router as operability_router
from app.interface.api.resolution import router as resolution_router
from app.interface.api.root import router as root_router
from app.interface.api.skills import router as skills_router
from app.observability.context import clear_request_context, set_request_context
from app.observability.logging import (
    build_logging_config,
    configure_logging,
    normalize_log_format,
)
from app.observability.metrics import (
    observe_http_request,
    outcome_for_status_code,
    surface_for_request,
)
from app.persistence.db import dispose_engine
from app.service_container import build_service_container

STARTUP_BANNER = r"""
      //| |
     // | |
    //__| |     ___     ___ ___
   / ___  |   //   ) )   / /
  //    | |  //___/ /   / /
 //     | | //         / /      ()
================================================
"""

# Configure logging before lifespan starts so startup logs are consistently formatted.
configure_logging(
    os.getenv("LOG_LEVEL", "INFO"),
    log_format=normalize_log_format(os.getenv("LOG_FORMAT")),
    app_env=os.getenv("APP_ENV", "dev"),
    log_file_path=os.getenv("LOG_FILE_PATH"),
)

logger = logging.getLogger(__name__)

API_VERSION = "1.0.0"
API_DESCRIPTION = """
Registry-first API for immutable skill publication, candidate discovery,
exact dependency reads, immutable metadata fetch, immutable `.tar.zst` content
fetch, and governed lifecycle updates.

The server owns data-local registry operations only. Prompt interpretation,
reranking, dependency solving, final selection, lock generation, and execution
planning remain client-owned behavior outside this API boundary.
""".strip()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize process-wide resources and tear them down on shutdown."""
    reset_settings_cache()
    settings = get_settings()
    configure_logging(
        settings.log_level,
        log_format=settings.log_format,
        app_env=settings.app_env,
        log_file_path=settings.log_file_path,
    )
    if settings.auth_service_tokens:
        logger.info(
            "loaded %d governed service token(s) from settings",
            len(settings.auth_service_tokens),
        )
    else:
        logger.warning(
            "no service tokens configured; authenticated endpoints will reject all bearer tokens"
        )
    app.state.services = build_service_container(settings=settings)
    logger.info("service startup complete")
    try:
        yield
    finally:
        dispose_engine()
        logger.info("service shutdown complete")


def create_app() -> FastAPI:
    """Create and configure a FastAPI application instance."""
    app_settings = _load_app_settings_for_wiring()
    app_env = "dev" if app_settings is None else app_settings.app_env
    app = FastAPI(
        title="Aptitude Registry Service",
        description=API_DESCRIPTION,
        version=API_VERSION,
        lifespan=lifespan,
        docs_url="/docs" if app_env == "dev" else None,
        redoc_url="/redoc" if app_env == "dev" else None,
        openapi_url="/openapi.json" if app_env == "dev" else None,
    )
    if app_settings is not None and app_settings.app_env == "prod":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=list(app_settings.allowed_hosts),
        )

    @app.middleware("http")
    async def observability_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        started_at = perf_counter()
        request.state.request_id = request_id
        set_request_context(
            request_id=request_id,
            http_method=request.method,
            client_ip=request.client.host if request.client is not None else None,
            user_agent=request.headers.get("user-agent"),
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            route = _route_template(request)
            duration_seconds = perf_counter() - started_at
            status_code = 500
            set_request_context(
                http_route=route,
                status_code=status_code,
                duration_ms=round(duration_seconds * 1000, 3),
                surface=surface_for_request(method=request.method, route=route),
                outcome=outcome_for_status_code(status_code),
                exception_type=type(exc).__name__,
            )
            observe_http_request(
                method=request.method,
                route=route,
                status_code=status_code,
                duration_seconds=duration_seconds,
            )
            logger.exception("request failed", extra={"event_type": "request.failed"})
            clear_request_context()
            raise

        route = _route_template(request)
        duration_seconds = perf_counter() - started_at
        outcome = outcome_for_status_code(response.status_code)
        error_code = (
            getattr(request.state, "error_code", None)
            or getattr(response, "error_code", None)
            or _response_error_code(response)
        )
        set_request_context(
            http_route=route,
            status_code=response.status_code,
            duration_ms=round(duration_seconds * 1000, 3),
            surface=surface_for_request(method=request.method, route=route),
            outcome=outcome,
            error_code=error_code,
        )
        observe_http_request(
            method=request.method,
            route=route,
            status_code=response.status_code,
            duration_seconds=duration_seconds,
        )
        response.headers.setdefault("X-Request-ID", request_id)
        logger.info("request complete", extra={"event_type": "request.completed"})
        clear_request_context()
        return response

    app.add_exception_handler(
        RequestValidationError,
        cast(ExceptionHandler, cast(object, request_validation_exception_handler)),
    )
    app.add_exception_handler(
        ApiError,
        cast(ExceptionHandler, cast(object, api_error_exception_handler)),
    )
    app.add_exception_handler(
        PolicyViolation,
        cast(ExceptionHandler, cast(object, policy_violation_exception_handler)),
    )
    app.include_router(root_router)
    app.include_router(health_router)
    app.include_router(operability_router)
    app.include_router(discovery_router)
    app.include_router(resolution_router)
    app.include_router(fetch_router)
    app.include_router(skills_router)
    return app


def run_dev_server() -> None:
    """Run uvicorn with the centralized aptitude logging configuration."""
    import uvicorn

    app_env = os.getenv("APP_ENV", "dev")
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_format = normalize_log_format(os.getenv("LOG_FORMAT"))
    print(STARTUP_BANNER)
    reload_enabled = os.getenv("UVICORN_RELOAD", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=int(os.getenv("PORT", "8000")),
        reload=reload_enabled,
        log_config=build_logging_config(
            log_level,
            log_format=log_format,
            app_env=app_env,
            log_file_path=os.getenv("LOG_FILE_PATH"),
        ),
    )


if __name__ == "__main__":
    run_dev_server()


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    if isinstance(route, APIRoute):
        return route.path
    return "__unmatched__"


def _response_error_code(response: Response) -> str | None:
    if response.status_code < 400:
        return None
    if "application/json" not in response.headers.get("content-type", ""):
        return None
    body = getattr(response, "body", None)
    if not isinstance(body, bytes):
        return None
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    error = payload.get("error")
    if not isinstance(error, dict):
        return None
    code = error.get("code")
    return code if isinstance(code, str) else None


def _load_app_settings_for_wiring() -> Settings | None:
    try:
        return load_settings()
    except ValidationError:
        return None


app = create_app()
