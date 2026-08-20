"""Validation tests for shared API contract examples."""

from __future__ import annotations

from typing import Any

import pytest

from app.interface.dto.errors import ErrorEnvelope
from app.interface.dto.examples import (
    CONTENT_STORAGE_FAILURE_ERROR_EXAMPLE,
    DISCOVERY_REQUEST_EXAMPLE,
    DISCOVERY_RESPONSE_EXAMPLE,
    DUPLICATE_SKILL_VERSION_ERROR_EXAMPLE,
    INVALID_REQUEST_ERROR_EXAMPLE,
    PUBLISH_REQUEST_EXAMPLE,
    RESOLUTION_RESPONSE_EXAMPLE,
    SKILL_ALREADY_EXISTS_ERROR_EXAMPLE,
    SKILL_NOT_FOUND_ERROR_EXAMPLE,
    SKILL_VERSION_LIST_RESPONSE_EXAMPLE,
    SKILL_VERSION_METADATA_RESPONSE_EXAMPLE,
    SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE,
    SKILL_VERSION_STATUS_RESPONSE_EXAMPLE,
)
from app.interface.dto.skills import (
    SkillDependencyResolutionResponse,
    SkillDiscoveryRequest,
    SkillDiscoveryResponse,
    SkillVersionCreateRequest,
    SkillVersionListResponse,
    SkillVersionMetadataResponse,
    SkillVersionStatusResponse,
)


@pytest.mark.unit
def test_publish_request_example_matches_request_contract() -> None:
    request = SkillVersionCreateRequest.model_validate(PUBLISH_REQUEST_EXAMPLE)

    assert request.intent == "create_skill"
    assert request.version == "1.2.3"
    assert request.relationships.depends_on
    assert "headers" not in request.metadata.model_dump(exclude_none=False)


@pytest.mark.unit
def test_discovery_request_example_matches_request_contract() -> None:
    request = SkillDiscoveryRequest.model_validate(DISCOVERY_REQUEST_EXAMPLE)

    assert request.query == "Python Lint"
    assert request.tags == ["python", "lint"]
    assert request.context_skills[0].model_dump() == {
        "slug": "python-format",
        "version": "1.0.0",
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    ("payload", "model"),
    [
        (SKILL_VERSION_LIST_RESPONSE_EXAMPLE, SkillVersionListResponse),
        (SKILL_VERSION_METADATA_RESPONSE_EXAMPLE, SkillVersionMetadataResponse),
        (DISCOVERY_RESPONSE_EXAMPLE, SkillDiscoveryResponse),
        (RESOLUTION_RESPONSE_EXAMPLE, SkillDependencyResolutionResponse),
        (SKILL_VERSION_STATUS_RESPONSE_EXAMPLE, SkillVersionStatusResponse),
    ],
)
def test_success_examples_match_response_contracts(
    payload: dict[str, object],
    model: type[Any],
) -> None:
    validated = model.model_validate(payload)

    assert validated is not None


@pytest.mark.unit
@pytest.mark.parametrize(
    "payload",
    [
        INVALID_REQUEST_ERROR_EXAMPLE,
        DUPLICATE_SKILL_VERSION_ERROR_EXAMPLE,
        SKILL_ALREADY_EXISTS_ERROR_EXAMPLE,
        SKILL_NOT_FOUND_ERROR_EXAMPLE,
        SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE,
        CONTENT_STORAGE_FAILURE_ERROR_EXAMPLE,
    ],
)
def test_error_examples_match_error_envelope_contract(payload: dict[str, object]) -> None:
    envelope = ErrorEnvelope.model_validate(payload)

    assert envelope.error.code
