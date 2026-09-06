"""Unit coverage for the public assessment metadata contract."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.core.ports import GovernanceRecordInput, MetadataRecordInput
from app.core.skills.models import SkillAssessmentData
from app.core.skills.registry import _version_checksum_digest
from app.interface.dto.skills_publish import SkillVersionCreateRequest
from app.interface.dto.skills_shared import SkillAssessment


def _assessment() -> dict[str, object]:
    return {
        "schema_version": 1,
        "assessed_at": "2026-09-06T00:00:00Z",
        "maturity": {
            "validation_passed": True,
            "validation_score": 0.8,
            "upskill_score": None,
            "upskill_status": "unavailable",
            "test_case_count": 0,
            "models_tested": [],
            "baseline_success_rate": None,
            "skilled_success_rate": None,
            "warnings": ["Missing examples"],
            "warnings_omitted": 0,
            "models_omitted": 0,
        },
        "security": {
            "scanned": True,
            "decision": "review_required",
            "checks_run": ["llm_guard:Secrets"],
            "checks_omitted": 0,
            "findings": [
                {
                    "check": "llm_guard:Secrets",
                    "severity": "medium",
                    "explanation": "Review the skill package for a possible secret.",
                }
            ],
            "findings_omitted": 0,
        },
    }


@pytest.mark.unit
def test_assessment_is_strict_and_round_trips_json() -> None:
    assessment = SkillAssessment.model_validate(_assessment())

    assert assessment.model_dump(mode="json")["assessed_at"] == "2026-09-06T00:00:00Z"
    assert assessment.security.findings[0].severity == "medium"


@pytest.mark.unit
@pytest.mark.parametrize(
    "change",
    [
        {"extra": True},
        {"maturity": {"validation_passed": "yes"}},
        {"maturity": {"validation_score": "0.8"}},
        {"security": {"scanned": 1}},
        {"security": {"decision": "safe"}},
    ],
)
def test_assessment_rejects_unknown_or_wrongly_typed_fields(
    change: dict[str, object],
) -> None:
    payload = _assessment()
    for key, value in change.items():
        if key in {"maturity", "security"}:
            nested = dict(payload[key])  # type: ignore[arg-type]
            nested.update(value)  # type: ignore[arg-type]
            payload[key] = nested
        else:
            payload[key] = value

    with pytest.raises(ValidationError):
        SkillAssessment.model_validate(payload)


@pytest.mark.unit
def test_assessment_rejects_oversized_lists_and_scores() -> None:
    payload = _assessment()
    maturity = dict(payload["maturity"])  # type: ignore[arg-type]
    maturity["warnings"] = ["warning"] * 101
    payload["maturity"] = maturity

    with pytest.raises(ValidationError):
        SkillAssessment.model_validate(payload)

    maturity["warnings"] = []
    maturity["validation_score"] = 1.1
    with pytest.raises(ValidationError):
        SkillAssessment.model_validate(payload)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), True),
        (("schema_version",), 1.0),
        (("schema_version",), 2),
        (("assessed_at",), 1_788_652_800),
        (("assessed_at",), "2026-09-06T00:00:00+01:00"),
        (("maturity", "test_case_count"), -1),
        (("maturity", "warnings_omitted"), -1),
        (("maturity", "models_omitted"), -1),
        (("security", "checks_omitted"), -1),
        (("security", "findings_omitted"), -1),
    ],
)
def test_assessment_rejects_invalid_versions_timestamps_and_counts(
    path: tuple[str, ...], value: object
) -> None:
    payload = deepcopy(_assessment())
    target: dict[str, object] = payload
    for key in path[:-1]:
        target = target[key]  # type: ignore[assignment]
    target[path[-1]] = value

    with pytest.raises(ValidationError):
        SkillAssessment.model_validate(payload)


@pytest.mark.unit
def test_assessment_rejects_non_finite_scores_and_oversized_text() -> None:
    for score in (float("nan"), float("inf"), float("-inf")):
        payload = deepcopy(_assessment())
        payload["maturity"]["validation_score"] = score  # type: ignore[index]
        with pytest.raises(ValidationError):
            SkillAssessment.model_validate(payload)

    oversized_values = (
        ("upskill_status", "x" * 1001),
        ("models_tested", ["x" * 1001]),
        ("warnings", ["x" * 1001]),
    )
    for key, value in oversized_values:
        payload = deepcopy(_assessment())
        payload["maturity"][key] = value  # type: ignore[index]
        with pytest.raises(ValidationError):
            SkillAssessment.model_validate(payload)

    payload = deepcopy(_assessment())
    payload["security"]["checks_run"] = ["x" * 1001]  # type: ignore[index]
    with pytest.raises(ValidationError):
        SkillAssessment.model_validate(payload)

    for key in ("check", "explanation"):
        payload = deepcopy(_assessment())
        payload["security"]["findings"][0][key] = "x" * 1001  # type: ignore[index]
        with pytest.raises(ValidationError):
            SkillAssessment.model_validate(payload)


@pytest.mark.unit
def test_assessment_rejects_unknown_nested_fields() -> None:
    payload = deepcopy(_assessment())
    payload["maturity"]["unexpected"] = True  # type: ignore[index]
    with pytest.raises(ValidationError):
        SkillAssessment.model_validate(payload)

    payload = deepcopy(_assessment())
    payload["security"]["findings"][0]["evidence"] = "raw evidence"  # type: ignore[index]
    with pytest.raises(ValidationError):
        SkillAssessment.model_validate(payload)


@pytest.mark.unit
def test_publish_request_accepts_nullable_assessment_metadata() -> None:
    request = SkillVersionCreateRequest.model_validate(
        {
            "intent": "create_skill",
            "version": "1.0.0",
            "metadata": {
                "name": "Assessment fixture",
                "description": None,
                "tags": [],
                "assessment": _assessment(),
            },
        }
    )

    assert request.metadata.assessment is not None
    assert request.metadata.assessment.maturity.validation_score == 0.8


def _checksum_metadata(assessment: SkillAssessmentData | None) -> MetadataRecordInput:
    return MetadataRecordInput(
        name="Assessment fixture",
        description="Description",
        tags=("quality",),
        token_estimate=42,
        maturity_score=0.8,
        security_score=0.9,
        overall_score=0.85,
        assessment=assessment,
    )


def _checksum_governance() -> GovernanceRecordInput:
    return GovernanceRecordInput(
        trust_tier="community",
        provenance=None,
        namespace="public",
        artifact_origin="publisher",
        review_state="approved",
        promotion_channel="prod",
        policy_pack_slug=None,
    )


@pytest.mark.unit
def test_legacy_version_checksum_omits_null_assessment() -> None:
    common = {
        "slug": "assessment-fixture",
        "version": "1.0.0",
        "content_checksum_digest": "a" * 64,
        "governance": _checksum_governance(),
        "relationships": (),
    }
    digest = _version_checksum_digest(
        metadata=_checksum_metadata(None),
        **common,
    )
    legacy_digest = _version_checksum_digest(
        metadata=_checksum_metadata(None),
        **common,
    )
    legacy_payload = {
        "slug": "assessment-fixture",
        "version": "1.0.0",
        "content_checksum_digest": "a" * 64,
        "metadata": {
            "name": "Assessment fixture",
            "description": "Description",
            "tags": ["quality"],
            "token_estimate": 42,
            "maturity_score": 0.8,
            "security_score": 0.9,
            "overall_score": 0.85,
        },
        "governance": {
            "trust_tier": "community",
            "provenance": None,
        },
        "relationships": {
            "depends_on": [],
            "extends": [],
            "conflicts_with": [],
            "overlaps_with": [],
        },
    }
    expected_legacy_digest = hashlib.sha256(
        json.dumps(
            legacy_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()

    assert digest == legacy_digest == expected_legacy_digest


@pytest.mark.unit
def test_version_checksum_changes_when_assessment_changes() -> None:
    first = SkillAssessment.model_validate(_assessment()).model_dump(mode="json")
    changed = deepcopy(first)
    changed["maturity"]["validation_score"] = 0.9  # type: ignore[index]
    common = {
        "slug": "assessment-fixture",
        "version": "1.0.0",
        "content_checksum_digest": "a" * 64,
        "governance": _checksum_governance(),
        "relationships": (),
    }

    first_digest = _version_checksum_digest(
        metadata=_checksum_metadata(first),
        **common,
    )
    changed_digest = _version_checksum_digest(
        metadata=_checksum_metadata(changed),
        **common,
    )

    assert first_digest != changed_digest
