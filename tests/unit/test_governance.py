"""Unit tests for governance policy and settings behavior."""

from __future__ import annotations

import pytest

from app.core.governance import (
    CallerIdentity,
    GovernancePolicy,
    NamespaceGrant,
    PolicyViolation,
    ProvenanceMetadata,
    SkillGovernanceInput,
)
from app.core.settings import Settings
from tests.conftest import DEFAULT_AUTH_SERVICE_TOKENS

DATABASE_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude"


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, DATABASE_URL=DATABASE_URL, **overrides)


@pytest.mark.unit
def test_settings_parse_service_tokens_and_policy_profiles_from_json() -> None:
    settings = _settings(
        AUTH_SERVICE_TOKENS_JSON=DEFAULT_AUTH_SERVICE_TOKENS,
        POLICY_PROFILES_JSON={
            "strict": {
                "publish_rules": {
                    "untrusted": {"required_scope": "admin", "provenance_required": True},
                    "internal": {"required_scope": "admin", "provenance_required": True},
                    "verified": {"required_scope": "admin", "provenance_required": True},
                }
            }
        },
        ACTIVE_POLICY_PROFILE="strict",
    )

    assert settings.service_token_records[0].token_id == "reader-token"
    assert settings.active_policy_profile == "strict"
    assert (
        settings.effective_policy_profiles["strict"].publish_rules["untrusted"].required_scope
        == "admin"
    )


@pytest.mark.unit
def test_settings_parse_service_token_namespace_grants() -> None:
    settings = _settings(
        AUTH_SERVICE_TOKENS_JSON=[
            {
                "token_id": "reviewer-token",
                "secret_digest": (
                    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
                ),
                "scopes": ["read", "review"],
                "active": True,
                "namespace_grants": [
                    {
                        "namespace": "acme.private",
                        "roles": ["read", "review"],
                        "promotion_channels": ["dev", "staging"],
                    }
                ],
            }
        ],
    )

    record = settings.service_token_records[0]

    assert record.scopes == frozenset({"read", "review"})
    assert record.namespace_grants == (
        NamespaceGrant(
            namespace="acme.private",
            roles=frozenset({"read", "review"}),
            promotion_channels=frozenset({"dev", "staging"}),
        ),
    )


@pytest.mark.unit
def test_governance_policy_blocks_missing_provenance_for_internal_publish() -> None:
    policy = GovernancePolicy(profile=_settings().active_policy)

    with pytest.raises(PolicyViolation) as exc_info:
        policy.evaluate_publish(
            caller=CallerIdentity(token_id="publisher", scopes=frozenset({"publish"})),
            governance=SkillGovernanceInput(trust_tier="internal"),
        )

    assert exc_info.value.code == "POLICY_PROVENANCE_REQUIRED"


@pytest.mark.unit
def test_governance_policy_blocks_publish_without_namespace_grant() -> None:
    policy = GovernancePolicy(profile=_settings().active_policy)

    with pytest.raises(PolicyViolation) as exc_info:
        policy.prepare_publish_governance(
            caller=CallerIdentity(
                token_id="publisher",
                scopes=frozenset({"publish"}),
                namespace_grants=(
                    NamespaceGrant(
                        namespace="public",
                        roles=frozenset({"publish"}),
                        promotion_channels=frozenset({"prod"}),
                    ),
                ),
            ),
            governance=SkillGovernanceInput(namespace="acme.private"),
        )

    assert exc_info.value.code == "POLICY_NAMESPACE_FORBIDDEN"


@pytest.mark.unit
def test_governance_policy_hides_pending_imports_from_prod_reader() -> None:
    policy = GovernancePolicy(profile=_settings().active_policy)

    with pytest.raises(PolicyViolation) as exc_info:
        policy.ensure_exact_read_allowed(
            caller=CallerIdentity(
                token_id="reader",
                scopes=frozenset({"read"}),
                namespace_grants=(
                    NamespaceGrant(
                        namespace="acme.private",
                        roles=frozenset({"read"}),
                        promotion_channels=frozenset({"prod"}),
                    ),
                ),
            ),
            lifecycle_status="published",
            namespace="acme.private",
            review_state="pending_review",
            promotion_channel="dev",
            trust_tier="untrusted",
            policy_pack=None,
        )

    assert exc_info.value.code == "POLICY_REVIEW_STATE_FORBIDDEN"


@pytest.mark.unit
def test_governance_policy_rejects_archived_to_published_transition() -> None:
    policy = GovernancePolicy(profile=_settings().active_policy)

    with pytest.raises(PolicyViolation) as exc_info:
        policy.evaluate_transition(
            caller=CallerIdentity(token_id="admin", scopes=frozenset({"admin"})),
            current_status="archived",
            next_status="published",
        )

    assert exc_info.value.code == "POLICY_STATUS_TRANSITION_FORBIDDEN"


@pytest.mark.unit
def test_prepare_publish_governance_normalizes_provenance_and_attaches_policy_profile() -> None:
    policy = GovernancePolicy(profile=_settings().active_policy)

    governance = policy.prepare_publish_governance(
        caller=CallerIdentity(token_id="publisher", scopes=frozenset({"publish"})),
        governance=SkillGovernanceInput(
            trust_tier="internal",
            provenance=ProvenanceMetadata(
                repo_url="  https://github.com/acme/python-lint  ",
                commit_sha="AABBCCDDEEFF00112233445566778899AABBCCDD",
                tree_path="  skills/python/lint  ",
                publisher_identity="  ci/acme-release  ",
            ),
        ),
    )

    assert governance.provenance is not None
    assert governance.provenance.repo_url == "https://github.com/acme/python-lint"
    assert governance.provenance.commit_sha == "aabbccddeeff00112233445566778899aabbccdd"
    assert governance.provenance.tree_path == "skills/python/lint"
    assert governance.provenance.publisher_identity == "ci/acme-release"
    assert governance.provenance.policy_profile == "default"


@pytest.mark.unit
def test_prepare_publish_governance_rejects_blank_trimmed_provenance_fields() -> None:
    policy = GovernancePolicy(profile=_settings().active_policy)

    with pytest.raises(PolicyViolation) as exc_info:
        policy.prepare_publish_governance(
            caller=CallerIdentity(token_id="publisher", scopes=frozenset({"publish"})),
            governance=SkillGovernanceInput(
                trust_tier="internal",
                provenance=ProvenanceMetadata(
                    repo_url="https://github.com/acme/python-lint",
                    commit_sha="0123456789abcdef",
                    publisher_identity="   ",
                ),
            ),
        )

    assert exc_info.value.code == "POLICY_PROVENANCE_INVALID"
