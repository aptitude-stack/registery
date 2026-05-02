"""Typed application settings loaded from environment."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.governance import (
    ALL_NAMESPACE_ROLES,
    CallerScope,
    LifecycleStatus,
    NamespaceGrant,
    NamespaceRole,
    PolicyProfile,
    PromotionChannel,
    PublishRule,
    TrustTier,
    build_default_policy_profile,
)
from app.core.ports import ServiceTokenRecord


class PublishRuleSettings(BaseModel):
    """Serializable publish-rule configuration for one trust tier."""

    required_scope: CallerScope
    provenance_required: bool = False


SETTINGS_ENV_FILE_ENV_VAR = "APP_SETTINGS_ENV_FILE"
MIGRATION_DATABASE_URL_ENV_VAR = "MIGRATION_DATABASE_URL"
OTEL_OTLP_ENDPOINT_ENV_VAR = "OTEL_EXPORTER_OTLP_ENDPOINT"
AppEnv = Literal["dev", "prod"]


def _default_publish_rules() -> dict[TrustTier, PublishRuleSettings]:
    default_policy = build_default_policy_profile()
    return {
        tier: PublishRuleSettings(
            required_scope=rule.required_scope,
            provenance_required=rule.provenance_required,
        )
        for tier, rule in default_policy.publish_rules.items()
    }


def _default_lifecycle_transitions() -> dict[LifecycleStatus, tuple[LifecycleStatus, ...]]:
    return dict(build_default_policy_profile().lifecycle_transitions)


class PolicyProfileSettings(BaseModel):
    """Serializable policy-profile configuration loaded from settings."""

    publish_rules: dict[TrustTier, PublishRuleSettings] = Field(
        default_factory=_default_publish_rules
    )
    lifecycle_transitions: dict[LifecycleStatus, tuple[LifecycleStatus, ...]] = Field(
        default_factory=_default_lifecycle_transitions
    )
    discovery_default_statuses: tuple[LifecycleStatus, ...] = (
        build_default_policy_profile().discovery_default_statuses
    )
    discovery_read_statuses: tuple[LifecycleStatus, ...] = (
        build_default_policy_profile().discovery_read_statuses
    )
    discovery_admin_statuses: tuple[LifecycleStatus, ...] = (
        build_default_policy_profile().discovery_admin_statuses
    )
    exact_read_statuses: tuple[LifecycleStatus, ...] = (
        build_default_policy_profile().exact_read_statuses
    )


class ServiceTokenSettings(BaseModel):
    """One governed service-token record loaded from settings."""

    token_id: str
    secret_digest: str
    scopes: tuple[CallerScope, ...]
    active: bool = True
    namespace_grants: tuple[ServiceTokenNamespaceGrantSettings, ...] = ()
    expires_at: datetime | None = None

    @field_validator("token_id")
    @classmethod
    def validate_token_id(cls, value: str) -> str:
        token_id = value.strip()
        if not token_id:
            raise ValueError("token_id must not be blank.")
        if "." in token_id:
            raise ValueError("token_id must not contain `.`.")
        return token_id

    @field_validator("secret_digest")
    @classmethod
    def validate_secret_digest(cls, value: str) -> str:
        secret_digest = value.strip().lower()
        if len(secret_digest) != 64 or any(
            char not in "0123456789abcdef" for char in secret_digest
        ):
            raise ValueError("secret_digest must be a 64-character lowercase sha256 hex digest.")
        return secret_digest

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("expires_at must include a timezone offset.")
        return value.astimezone(UTC)

    def to_record(self) -> ServiceTokenRecord:
        """Return the normalized service-token record used by the auth service."""
        grants = (
            tuple(grant.to_domain() for grant in self.namespace_grants)
            if self.namespace_grants
            else _default_namespace_grants(self.scopes)
        )
        return ServiceTokenRecord(
            token_id=self.token_id,
            secret_digest=self.secret_digest,
            scopes=frozenset(self.scopes),
            active=self.active,
            namespace_grants=grants,
            expires_at=self.expires_at,
        )


class ServiceTokenNamespaceGrantSettings(BaseModel):
    """One namespace grant loaded from a governed service-token setting."""

    namespace: str
    roles: tuple[NamespaceRole, ...]
    promotion_channels: tuple[PromotionChannel | Literal["*"], ...]

    @field_validator("namespace")
    @classmethod
    def validate_namespace(cls, value: str) -> str:
        namespace = value.strip()
        if not namespace:
            raise ValueError("namespace must not be blank.")
        if namespace != "*" and len(namespace) > 128:
            raise ValueError("namespace must be at most 128 characters.")
        return namespace

    def to_domain(self) -> NamespaceGrant:
        """Return the immutable namespace grant used by auth and governance."""
        return NamespaceGrant(
            namespace=self.namespace,
            roles=frozenset(self.roles),
            promotion_channels=frozenset(self.promotion_channels),
        )


def _default_namespace_grants(scopes: tuple[CallerScope, ...]) -> tuple[NamespaceGrant, ...]:
    """Return backward-compatible namespace grants for existing token settings."""
    if "admin" in scopes:
        return (
            NamespaceGrant(
                namespace="*",
                roles=frozenset(ALL_NAMESPACE_ROLES),
                promotion_channels=frozenset({"*"}),
            ),
        )
    roles = frozenset(scope for scope in scopes if scope in ALL_NAMESPACE_ROLES)
    if not roles:
        return ()
    return (
        NamespaceGrant(
            namespace="public",
            roles=roles,
            promotion_channels=frozenset({"prod"}),
        ),
    )


class Settings(BaseSettings):
    """Application configuration values."""

    database_url: str = Field(alias="DATABASE_URL")
    migration_database_url: str | None = Field(default=None, alias="MIGRATION_DATABASE_URL")
    app_env: AppEnv = Field(default="dev", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: Literal["auto", "json", "pretty"] = Field(default="auto", alias="LOG_FORMAT")
    app_name: str = Field(default="aptitude-registry", alias="APP_NAME")
    auth_service_tokens: tuple[ServiceTokenSettings, ...] = Field(
        default_factory=tuple,
        alias="AUTH_SERVICE_TOKENS_JSON",
    )
    allowed_hosts: tuple[str, ...] = Field(default_factory=tuple, alias="ALLOWED_HOSTS_JSON")
    policy_profiles: dict[str, PolicyProfileSettings] = Field(
        default_factory=dict,
        alias="POLICY_PROFILES_JSON",
    )
    active_policy_profile: str = Field(default="default", alias="ACTIVE_POLICY_PROFILE")
    otel_enabled: bool = Field(default=False, alias="OTEL_ENABLED")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @model_validator(mode="after")
    def validate_active_policy_profile(self) -> Settings:
        if self.active_policy_profile not in self.effective_policy_profiles:
            raise ValueError(
                f"Unknown active policy profile: {self.active_policy_profile!r}. "
                "Define it in POLICY_PROFILES_JSON or use 'default'."
            )
        if self.app_env == "prod" and not self.allowed_hosts:
            raise ValueError("ALLOWED_HOSTS_JSON must define at least one host when APP_ENV=prod.")
        if (
            self.otel_enabled
            and self.app_env == "prod"
            and not os.getenv(OTEL_OTLP_ENDPOINT_ENV_VAR)
        ):
            raise ValueError(
                "OTEL_ENABLED=true requires OTEL_EXPORTER_OTLP_ENDPOINT when APP_ENV=prod."
            )
        token_ids = [token.token_id for token in self.auth_service_tokens]
        duplicate_token_ids = {token_id for token_id in token_ids if token_ids.count(token_id) > 1}
        if duplicate_token_ids:
            duplicates = ", ".join(sorted(duplicate_token_ids))
            raise ValueError(
                f"AUTH_SERVICE_TOKENS_JSON contains duplicate token ids: {duplicates}."
            )
        return self

    @field_validator("allowed_hosts")
    @classmethod
    def normalize_allowed_hosts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(host.strip() for host in value if host.strip())
        return tuple(dict.fromkeys(normalized))

    @property
    def effective_policy_profiles(self) -> dict[str, PolicyProfileSettings]:
        """Return built-in and settings-supplied policy profiles."""
        return {"default": PolicyProfileSettings(), **self.policy_profiles}

    @property
    def active_policy(self) -> PolicyProfile:
        """Return the configured active policy profile as a core domain object."""
        configured = self.effective_policy_profiles[self.active_policy_profile]
        default_rules = _default_publish_rules()
        merged_rules: dict[TrustTier, PublishRuleSettings] = {
            **default_rules,
            **configured.publish_rules,
        }
        return PolicyProfile(
            name=self.active_policy_profile,
            publish_rules={
                tier: PublishRule(
                    required_scope=rule.required_scope,
                    provenance_required=rule.provenance_required,
                )
                for tier, rule in merged_rules.items()
            },
            lifecycle_transitions=configured.lifecycle_transitions,
            discovery_default_statuses=configured.discovery_default_statuses,
            discovery_read_statuses=configured.discovery_read_statuses,
            discovery_admin_statuses=configured.discovery_admin_statuses,
            exact_read_statuses=configured.exact_read_statuses,
        )

    @property
    def service_token_records(self) -> tuple[ServiceTokenRecord, ...]:
        """Return normalized governed service-token records."""
        return tuple(token.to_record() for token in self.auth_service_tokens)


@lru_cache
def get_settings() -> Settings:
    """Return memoized settings for the running process."""
    return load_settings()


def load_settings() -> Settings:
    """Return a fresh settings instance from the active environment and dotenv file."""
    return Settings(_env_file=os.getenv(SETTINGS_ENV_FILE_ENV_VAR, ".env"))  # type: ignore[call-arg]


def reset_settings_cache() -> None:
    """Clear cached settings; mainly used by tests and startup wiring."""
    get_settings.cache_clear()
