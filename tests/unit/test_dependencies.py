"""Unit tests for typed service-container dependency wiring."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from app.core.auth import AuthService
from app.core.dependencies import (
    get_auth_service,
    get_readiness_service,
    get_skill_fetch_service,
    get_skill_resolution_service,
)
from app.core.skills.discovery import SkillDiscoveryService
from app.core.skills.fetch import SkillFetchService
from app.core.skills.registry import SkillRegistryService
from app.core.skills.resolution import SkillResolutionService
from app.observability.readiness import ReadinessService
from app.service_container import ServiceContainer


@pytest.mark.unit
def test_dependency_getters_read_services_from_typed_container() -> None:
    services = ServiceContainer(
        auth_service=cast(AuthService, object()),
        readiness_service=cast(ReadinessService, object()),
        skill_registry_service=cast(SkillRegistryService, object()),
        skill_discovery_service=cast(SkillDiscoveryService, object()),
        skill_fetch_service=cast(SkillFetchService, object()),
        skill_resolution_service=cast(SkillResolutionService, object()),
    )
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(services=services)))

    assert get_auth_service(request) is services.auth_service
    assert get_readiness_service(request) is services.readiness_service
    assert get_skill_fetch_service(request) is services.skill_fetch_service
    assert get_skill_resolution_service(request) is services.skill_resolution_service


@pytest.mark.unit
def test_dependency_getters_fail_when_service_container_is_missing() -> None:
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    with pytest.raises(RuntimeError, match="Service container is not initialized."):
        get_readiness_service(request)
