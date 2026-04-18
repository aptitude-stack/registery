"""Reusable FastAPI dependencies for core services and settings.

This module centralizes dependency wiring for request handlers so interface code
can declare typed dependencies with minimal boilerplate.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import AuthError, AuthorizationError, AuthService
from app.core.governance import CallerIdentity, CallerScope
from app.core.settings import Settings, get_settings
from app.core.skills.discovery import SkillDiscoveryService
from app.core.skills.fetch import SkillFetchService
from app.core.skills.registry import SkillRegistryService
from app.core.skills.resolution import SkillResolutionService
from app.interface.api.errors import ApiError
from app.observability.readiness import ReadinessService
from app.service_container import ServiceContainer

# Shared settings dependency used by route handlers and adapters.
SettingsDep = Annotated[Settings, Depends(get_settings)]
_bearer_scheme = HTTPBearer(auto_error=False)
BearerCredentialsDep = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(_bearer_scheme),
]


def get_readiness_service(request: Request) -> ReadinessService:
    """Return the process-scoped readiness service from the service container.

    Raises:
        RuntimeError: If startup wiring did not initialize the service container.
    """
    return _service_container(request).readiness_service


# Typed alias for injecting the readiness service via FastAPI dependencies.
ReadinessServiceDep = Annotated[ReadinessService, Depends(get_readiness_service)]


def get_auth_service(request: Request) -> AuthService:
    """Return the process-scoped auth service from the service container."""
    return _service_container(request).auth_service


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_skill_registry_service(request: Request) -> SkillRegistryService:
    """Return the immutable skill catalog service from the service container.

    Raises:
        RuntimeError: If startup wiring did not initialize the service container.
    """
    return _service_container(request).skill_registry_service


# Typed alias for injecting the skill catalog service in endpoint signatures.
SkillRegistryServiceDep = Annotated[SkillRegistryService, Depends(get_skill_registry_service)]


def get_skill_discovery_service(request: Request) -> SkillDiscoveryService:
    """Return the process-scoped discovery service from the service container."""
    return _service_container(request).skill_discovery_service


SkillDiscoveryServiceDep = Annotated[SkillDiscoveryService, Depends(get_skill_discovery_service)]


def get_skill_fetch_service(request: Request) -> SkillFetchService:
    """Return the process-scoped exact fetch service from the service container."""
    return _service_container(request).skill_fetch_service


SkillFetchServiceDep = Annotated[SkillFetchService, Depends(get_skill_fetch_service)]


def get_skill_resolution_service(request: Request) -> SkillResolutionService:
    """Return the process-scoped resolution service from the service container."""
    return _service_container(request).skill_resolution_service


SkillResolutionServiceDep = Annotated[SkillResolutionService, Depends(get_skill_resolution_service)]


def _service_container(request: Request) -> ServiceContainer:
    """Return the typed application service container from app state."""
    services = getattr(request.app.state, "services", None)
    if not isinstance(services, ServiceContainer):
        raise RuntimeError("Service container is not initialized.")
    return services


def _caller_from_request(
    *,
    credentials: HTTPAuthorizationCredentials | None,
    auth_service: AuthService,
) -> CallerIdentity:
    try:
        return auth_service.authenticate(
            scheme=None if credentials is None else credentials.scheme,
            credentials=None if credentials is None else credentials.credentials,
        )
    except AuthError as exc:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=exc.code,
            message=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _require_scope(
    *,
    caller: CallerIdentity,
    auth_service: AuthService,
    scope: CallerScope,
) -> CallerIdentity:
    try:
        return auth_service.require_scope(caller=caller, scope=scope)
    except AuthorizationError as exc:
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="INSUFFICIENT_SCOPE",
            message=str(exc),
            details={"required_scope": exc.required_scope},
        ) from exc


def get_read_caller(
    credentials: BearerCredentialsDep, auth_service: AuthServiceDep
) -> CallerIdentity:
    """Authenticate a caller with read scope."""
    caller = _caller_from_request(credentials=credentials, auth_service=auth_service)
    return _require_scope(caller=caller, auth_service=auth_service, scope="read")


ReadCallerDep = Annotated[CallerIdentity, Depends(get_read_caller)]


def get_publish_caller(
    credentials: BearerCredentialsDep,
    auth_service: AuthServiceDep,
) -> CallerIdentity:
    """Authenticate a caller with publish scope."""
    caller = _caller_from_request(credentials=credentials, auth_service=auth_service)
    return _require_scope(caller=caller, auth_service=auth_service, scope="publish")


PublishCallerDep = Annotated[CallerIdentity, Depends(get_publish_caller)]


def get_admin_caller(
    credentials: BearerCredentialsDep, auth_service: AuthServiceDep
) -> CallerIdentity:
    """Authenticate a caller with admin scope."""
    caller = _caller_from_request(credentials=credentials, auth_service=auth_service)
    return _require_scope(caller=caller, auth_service=auth_service, scope="admin")


AdminCallerDep = Annotated[CallerIdentity, Depends(get_admin_caller)]
