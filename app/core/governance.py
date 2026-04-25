"""Governance models and policy evaluation for registry operations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

CallerScope = Literal["read", "publish", "review", "admin"]
NamespaceRole = Literal["read", "publish", "review", "admin"]
LifecycleStatus = Literal["published", "deprecated", "archived"]
TrustTier = Literal["untrusted", "internal", "verified"]
ArtifactOrigin = Literal["internal", "imported", "verified", "restricted"]
ReviewState = Literal["pending_review", "approved", "rejected"]
PromotionChannel = Literal["dev", "staging", "prod"]

ALL_CALLER_SCOPES: tuple[CallerScope, ...] = ("read", "publish", "review", "admin")
ALL_NAMESPACE_ROLES: tuple[NamespaceRole, ...] = ("read", "publish", "review", "admin")
ALL_LIFECYCLE_STATUSES: tuple[LifecycleStatus, ...] = ("published", "deprecated", "archived")
ALL_TRUST_TIERS: tuple[TrustTier, ...] = ("untrusted", "internal", "verified")
ALL_ARTIFACT_ORIGINS: tuple[ArtifactOrigin, ...] = (
    "internal",
    "imported",
    "verified",
    "restricted",
)
ALL_REVIEW_STATES: tuple[ReviewState, ...] = ("pending_review", "approved", "rejected")
ALL_PROMOTION_CHANNELS: tuple[PromotionChannel, ...] = ("dev", "staging", "prod")
DEFAULT_NAMESPACE = "public"
GLOBAL_NAMESPACE = "*"


@dataclass(frozen=True, slots=True)
class NamespaceGrant:
    """Namespace-scoped capability attached to a service token."""

    namespace: str
    roles: frozenset[NamespaceRole]
    promotion_channels: frozenset[PromotionChannel | Literal["*"]]

    def matches(
        self,
        *,
        namespace: str,
        role: NamespaceRole,
        promotion_channel: PromotionChannel | None = None,
    ) -> bool:
        """Return whether this grant allows one namespace-scoped operation."""
        if self.namespace not in {GLOBAL_NAMESPACE, namespace}:
            return False
        if "admin" not in self.roles and role not in self.roles:
            return False
        return (
            promotion_channel is None
            or GLOBAL_NAMESPACE in self.promotion_channels
            or promotion_channel in self.promotion_channels
        )


@dataclass(frozen=True, slots=True)
class PolicyPack:
    """Registry-enforced policy-pack rules attached to a version."""

    slug: str
    rules: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CallerIdentity:
    """Authenticated caller context available to the interface and core layers."""

    token_id: str
    scopes: frozenset[CallerScope]
    namespace_grants: tuple[NamespaceGrant, ...] = ()

    def has_scope(self, scope: CallerScope) -> bool:
        """Return whether the caller can perform an operation requiring ``scope``."""
        return "admin" in self.scopes or scope in self.scopes

    def has_namespace_grant(
        self,
        *,
        namespace: str,
        role: NamespaceRole,
        promotion_channel: PromotionChannel | None = None,
    ) -> bool:
        """Return whether the caller may act in a namespace and promotion channel."""
        if not self.namespace_grants and "admin" in self.scopes:
            return True
        if not self.namespace_grants:
            return (
                namespace == DEFAULT_NAMESPACE
                and self.has_scope(role)
                and (promotion_channel is None or promotion_channel == "prod")
            )
        return any(
            grant.matches(
                namespace=namespace,
                role=role,
                promotion_channel=promotion_channel,
            )
            for grant in self.namespace_grants
        )

    def allowed_namespaces(self, *, role: NamespaceRole) -> tuple[str, ...] | None:
        """Return namespace filters for repository queries, or ``None`` for global."""
        if not self.namespace_grants and "admin" in self.scopes:
            return None
        if not self.namespace_grants:
            return (DEFAULT_NAMESPACE,) if self.has_scope(role) else ()
        namespaces = tuple(
            sorted(
                grant.namespace
                for grant in self.namespace_grants
                if GLOBAL_NAMESPACE in {grant.namespace}
                or "admin" in grant.roles
                or role in grant.roles
            )
        )
        if GLOBAL_NAMESPACE in namespaces:
            return None
        return namespaces

    def allowed_promotion_channels(
        self,
        *,
        role: NamespaceRole,
    ) -> tuple[PromotionChannel, ...] | None:
        """Return channel filters for repository queries, or ``None`` for global."""
        if not self.namespace_grants and "admin" in self.scopes:
            return None
        if not self.namespace_grants:
            return ("prod",) if self.has_scope(role) else ()
        channels: set[PromotionChannel] = set()
        for grant in self.namespace_grants:
            if "admin" not in grant.roles and role not in grant.roles:
                continue
            if GLOBAL_NAMESPACE in grant.promotion_channels:
                return None
            channels.update(
                channel for channel in grant.promotion_channels if channel in ALL_PROMOTION_CHANNELS
            )
        return tuple(sorted(channels))


@dataclass(frozen=True, slots=True)
class ProvenanceMetadata:
    """Minimal publish-time provenance captured alongside immutable versions."""

    repo_url: str
    commit_sha: str
    tree_path: str | None = None
    publisher_identity: str | None = None
    policy_profile: str | None = None


@dataclass(frozen=True, slots=True)
class SkillGovernanceInput:
    """Publish-time governance input owned by the core layer."""

    trust_tier: TrustTier = "untrusted"
    provenance: ProvenanceMetadata | None = None
    namespace: str = DEFAULT_NAMESPACE
    artifact_origin: ArtifactOrigin = "internal"
    review_state: ReviewState | None = None
    promotion_channel: PromotionChannel | None = None
    policy_pack_slug: str | None = None


@dataclass(frozen=True, slots=True)
class PublishRule:
    """Trust-tier-specific publish requirements."""

    required_scope: CallerScope
    provenance_required: bool = False


@dataclass(frozen=True, slots=True)
class PolicyProfile:
    """Named policy profile resolved from settings."""

    name: str
    publish_rules: dict[TrustTier, PublishRule]
    lifecycle_transitions: dict[LifecycleStatus, tuple[LifecycleStatus, ...]]
    discovery_default_statuses: tuple[LifecycleStatus, ...]
    discovery_read_statuses: tuple[LifecycleStatus, ...]
    discovery_admin_statuses: tuple[LifecycleStatus, ...]
    exact_read_statuses: tuple[LifecycleStatus, ...]


class GovernanceError(RuntimeError):
    """Base governance-domain error."""


class PolicyViolation(GovernanceError):
    """Raised when policy blocks an otherwise valid request."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


class GovernancePolicy:
    """Evaluate registry governance rules for publish, read, and lifecycle operations."""

    def __init__(self, *, profile: PolicyProfile) -> None:
        self._profile = profile
        # Validate that the profile defines publish rules for all trust tiers up-front
        missing_tiers = [tier for tier in ALL_TRUST_TIERS if tier not in profile.publish_rules]
        if missing_tiers:
            raise PolicyViolation(
                code="POLICY_PROFILE_INVALID",
                message="Policy profile is missing publish rules for some trust tiers.",
                details={
                    "profile": profile.name,
                    "missing_trust_tiers": tuple(missing_tiers),
                },
            )

    @property
    def profile_name(self) -> str:
        """Return the active policy profile name."""
        return self._profile.name

    def evaluate_publish(
        self,
        *,
        caller: CallerIdentity,
        governance: SkillGovernanceInput,
    ) -> None:
        """Validate publish permissions for the requested trust tier."""
        rule = self._profile.publish_rules[governance.trust_tier]
        if not caller.has_scope(rule.required_scope):
            raise PolicyViolation(
                code="POLICY_PUBLISH_FORBIDDEN",
                message="Caller is not allowed to publish with the requested trust tier.",
                details={
                    "required_scope": rule.required_scope,
                    "trust_tier": governance.trust_tier,
                },
            )
        self._ensure_namespace_allowed(
            caller=caller,
            namespace=governance.namespace,
            role="publish",
            promotion_channel=governance.promotion_channel
            or _default_promotion_channel(governance.artifact_origin),
            code="POLICY_NAMESPACE_FORBIDDEN",
            message="Caller is not allowed to publish in the requested namespace.",
        )
        if rule.provenance_required and governance.provenance is None:
            raise PolicyViolation(
                code="POLICY_PROVENANCE_REQUIRED",
                message="Provenance metadata is required for the requested trust tier.",
                details={"trust_tier": governance.trust_tier},
            )

    def prepare_publish_governance(
        self,
        *,
        caller: CallerIdentity,
        governance: SkillGovernanceInput,
    ) -> SkillGovernanceInput:
        """Normalize publish-time governance input and validate policy requirements."""
        normalized = SkillGovernanceInput(
            trust_tier=governance.trust_tier,
            provenance=self._normalize_provenance(governance.provenance),
            namespace=_normalize_namespace(governance.namespace),
            artifact_origin=governance.artifact_origin,
            review_state=governance.review_state
            or _default_review_state(governance.artifact_origin),
            promotion_channel=governance.promotion_channel
            or _default_promotion_channel(governance.artifact_origin),
            policy_pack_slug=_normalize_optional_text(
                governance.policy_pack_slug,
                field_name="policy_pack_slug",
            ),
        )
        self.evaluate_publish(caller=caller, governance=normalized)
        return normalized

    def evaluate_transition(
        self,
        *,
        caller: CallerIdentity,
        current_status: LifecycleStatus,
        next_status: LifecycleStatus,
        namespace: str = DEFAULT_NAMESPACE,
    ) -> None:
        """Validate lifecycle transitions for status updates."""
        if not caller.has_scope("admin"):
            raise PolicyViolation(
                code="POLICY_STATUS_TRANSITION_FORBIDDEN",
                message="Caller is not allowed to update lifecycle status.",
                details={"required_scope": "admin"},
            )
        self._ensure_namespace_allowed(
            caller=caller,
            namespace=namespace,
            role="admin",
            promotion_channel=None,
            code="POLICY_NAMESPACE_FORBIDDEN",
            message="Caller is not allowed to administer this namespace.",
        )

        allowed_targets = self._profile.lifecycle_transitions.get(current_status, ())
        if next_status not in allowed_targets:
            raise PolicyViolation(
                code="POLICY_STATUS_TRANSITION_FORBIDDEN",
                message="The requested lifecycle transition is not allowed.",
                details={
                    "current_status": current_status,
                    "next_status": next_status,
                    "allowed_targets": list(allowed_targets),
                },
            )

    def ensure_exact_read_allowed(
        self,
        *,
        caller: CallerIdentity,
        lifecycle_status: LifecycleStatus,
        namespace: str = DEFAULT_NAMESPACE,
        review_state: ReviewState = "approved",
        promotion_channel: PromotionChannel = "prod",
        trust_tier: TrustTier = "untrusted",
        policy_pack: PolicyPack | None = None,
    ) -> None:
        """Validate exact-read visibility for one stored version."""
        if lifecycle_status in self._profile.exact_read_statuses and caller.has_scope("read"):
            self._ensure_namespace_allowed(
                caller=caller,
                namespace=namespace,
                role="read",
                promotion_channel=None,
                code="POLICY_NAMESPACE_FORBIDDEN",
                message="Caller is not allowed to read this namespace.",
            )
            if review_state != "approved" and not caller.has_namespace_grant(
                namespace=namespace,
                role="review",
                promotion_channel=None,
            ):
                raise PolicyViolation(
                    code="POLICY_REVIEW_STATE_FORBIDDEN",
                    message="Caller is not allowed to read this review state.",
                    details={"review_state": review_state},
                )
            self._ensure_namespace_allowed(
                caller=caller,
                namespace=namespace,
                role="read",
                promotion_channel=promotion_channel,
                code="POLICY_NAMESPACE_FORBIDDEN",
                message="Caller is not allowed to read this promotion channel.",
            )
            self._ensure_policy_pack_allows_read(
                caller=caller,
                namespace=namespace,
                trust_tier=trust_tier,
                policy_pack=policy_pack,
            )
            return
        if lifecycle_status == "archived" and caller.has_scope("admin"):
            return
        raise PolicyViolation(
            code="POLICY_EXACT_READ_FORBIDDEN",
            message="Caller is not allowed to read this lifecycle state.",
            details={"lifecycle_status": lifecycle_status},
        )

    def is_visible_in_list(
        self,
        *,
        caller: CallerIdentity,
        lifecycle_status: LifecycleStatus,
        namespace: str = DEFAULT_NAMESPACE,
        review_state: ReviewState = "approved",
        promotion_channel: PromotionChannel = "prod",
        trust_tier: TrustTier = "untrusted",
        policy_pack: PolicyPack | None = None,
    ) -> bool:
        """Return whether a version is visible in identity/list responses."""
        try:
            self.ensure_exact_read_allowed(
                caller=caller,
                lifecycle_status=lifecycle_status,
                namespace=namespace,
                review_state=review_state,
                promotion_channel=promotion_channel,
                trust_tier=trust_tier,
                policy_pack=policy_pack,
            )
        except PolicyViolation:
            return False
        return True

    def resolve_discovery_statuses(
        self,
        *,
        caller: CallerIdentity,
        requested_statuses: tuple[LifecycleStatus, ...],
    ) -> tuple[LifecycleStatus, ...]:
        """Return effective lifecycle filters for discovery."""
        if not requested_statuses:
            return self._profile.discovery_default_statuses

        allowed_statuses = (
            self._profile.discovery_admin_statuses
            if caller.has_scope("admin")
            else self._profile.discovery_read_statuses
        )
        forbidden = [status for status in requested_statuses if status not in allowed_statuses]
        if forbidden:
            raise PolicyViolation(
                code="POLICY_DISCOVERY_FORBIDDEN",
                message="Caller is not allowed to search the requested lifecycle states.",
                details={"requested_statuses": forbidden},
            )
        return requested_statuses

    def resolve_discovery_trust_tiers(
        self,
        *,
        requested_trust_tiers: tuple[TrustTier, ...],
    ) -> tuple[TrustTier, ...]:
        """Return effective trust-tier filters for discovery."""
        return requested_trust_tiers or ALL_TRUST_TIERS

    def resolve_discovery_namespaces(
        self,
        *,
        caller: CallerIdentity,
    ) -> tuple[str, ...] | None:
        """Return namespace filters for discovery, or ``None`` for unrestricted callers."""
        return caller.allowed_namespaces(role="read")

    def resolve_discovery_promotion_channels(
        self,
        *,
        caller: CallerIdentity,
    ) -> tuple[PromotionChannel, ...] | None:
        """Return promotion-channel filters for discovery, or ``None`` for unrestricted callers."""
        return caller.allowed_promotion_channels(role="read")

    def _ensure_namespace_allowed(
        self,
        *,
        caller: CallerIdentity,
        namespace: str,
        role: NamespaceRole,
        promotion_channel: PromotionChannel | None,
        code: str,
        message: str,
    ) -> None:
        if caller.has_namespace_grant(
            namespace=namespace,
            role=role,
            promotion_channel=promotion_channel,
        ):
            return
        raise PolicyViolation(
            code=code,
            message=message,
            details={
                "namespace": namespace,
                "required_role": role,
                "promotion_channel": promotion_channel,
            },
        )

    def _ensure_policy_pack_allows_read(
        self,
        *,
        caller: CallerIdentity,
        namespace: str,
        trust_tier: TrustTier,
        policy_pack: PolicyPack | None,
    ) -> None:
        if policy_pack is None:
            return
        visibility = str(policy_pack.rules.get("visibility", "public"))
        if (
            policy_pack.rules.get("requires_verified_publisher") is True
            and trust_tier != "verified"
        ):
            raise PolicyViolation(
                code="POLICY_PACK_FORBIDDEN",
                message="Policy pack requires a verified publisher.",
                details={"policy_pack": policy_pack.slug, "trust_tier": trust_tier},
            )
        allowed_token_ids = _string_set(policy_pack.rules.get("allowed_token_ids"))
        allowed_namespaces = _string_set(policy_pack.rules.get("allowed_namespaces"))
        if visibility == "restricted" and (
            caller.token_id not in allowed_token_ids and namespace not in allowed_namespaces
        ):
            raise PolicyViolation(
                code="POLICY_PACK_FORBIDDEN",
                message="Caller is not allowed by the attached policy pack.",
                details={"policy_pack": policy_pack.slug, "namespace": namespace},
            )

    def _normalize_provenance(
        self,
        provenance: ProvenanceMetadata | None,
    ) -> ProvenanceMetadata | None:
        if provenance is None:
            return None

        repo_url = _normalize_required_text(provenance.repo_url, field_name="repo_url")
        commit_sha = _normalize_commit_sha(provenance.commit_sha)
        tree_path = _normalize_optional_text(provenance.tree_path, field_name="tree_path")
        publisher_identity = _normalize_optional_text(
            provenance.publisher_identity,
            field_name="publisher_identity",
        )

        return ProvenanceMetadata(
            repo_url=repo_url,
            commit_sha=commit_sha,
            tree_path=tree_path,
            publisher_identity=publisher_identity,
            policy_profile=self.profile_name,
        )


def build_default_policy_profile() -> PolicyProfile:
    """Return the built-in default policy profile."""
    return PolicyProfile(
        name="default",
        publish_rules={
            "untrusted": PublishRule(required_scope="publish", provenance_required=False),
            "internal": PublishRule(required_scope="publish", provenance_required=True),
            "verified": PublishRule(required_scope="admin", provenance_required=True),
        },
        lifecycle_transitions={
            "published": ("deprecated", "archived"),
            "deprecated": ("published", "archived"),
            "archived": (),
        },
        discovery_default_statuses=("published",),
        discovery_read_statuses=("published", "deprecated"),
        discovery_admin_statuses=("published", "deprecated", "archived"),
        exact_read_statuses=("published", "deprecated"),
    )


def _normalize_required_text(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise PolicyViolation(
            code="POLICY_PROVENANCE_INVALID",
            message="Provenance metadata contains invalid values.",
            details={"field": field_name},
        )
    return normalized


def _normalize_optional_text(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise PolicyViolation(
            code="POLICY_PROVENANCE_INVALID",
            message="Provenance metadata contains invalid values.",
            details={"field": field_name},
        )
    return normalized


def _normalize_commit_sha(value: str) -> str:
    normalized = _normalize_required_text(value, field_name="commit_sha").lower()
    if (
        len(normalized) < 7
        or len(normalized) > 64
        or re.fullmatch(r"[0-9a-f]+", normalized) is None
    ):
        raise PolicyViolation(
            code="POLICY_PROVENANCE_INVALID",
            message="Provenance metadata contains invalid values.",
            details={"field": "commit_sha"},
        )
    return normalized


def _normalize_namespace(value: str) -> str:
    normalized = _normalize_required_text(value, field_name="namespace")
    if (
        len(normalized) > 128
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", normalized) is None
    ):
        raise PolicyViolation(
            code="POLICY_NAMESPACE_INVALID",
            message="Namespace must be a non-empty registry namespace slug.",
            details={"namespace": value},
        )
    return normalized


def _default_review_state(artifact_origin: ArtifactOrigin) -> ReviewState:
    return "pending_review" if artifact_origin == "imported" else "approved"


def _default_promotion_channel(artifact_origin: ArtifactOrigin) -> PromotionChannel:
    return "dev" if artifact_origin == "imported" else "prod"


def _string_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}
