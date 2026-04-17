"""Typed application settings loaded from environment."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.governance import (
    CallerScope,
    LifecycleStatus,
    PolicyProfile,
    PublishRule,
    TrustTier,
    build_default_policy_profile,
)


class PublishRuleSettings(BaseModel):
    """Serializable publish-rule configuration for one trust tier."""

    required_scope: CallerScope
    provenance_required: bool = False


SETTINGS_ENV_FILE_ENV_VAR = "APP_SETTINGS_ENV_FILE"
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


class Settings(BaseSettings):
    """Application configuration values."""

    database_url: str = Field(alias="DATABASE_URL")
    app_env: AppEnv = Field(default="dev", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: Literal["auto", "json", "pretty"] = Field(default="auto", alias="LOG_FORMAT")
    log_file_path: str | None = Field(default=None, alias="LOG_FILE_PATH")
    app_name: str = Field(default="aptitude-registry", alias="APP_NAME")
    auth_tokens: dict[str, tuple[CallerScope, ...]] = Field(
        default_factory=dict,
        alias="AUTH_TOKENS_JSON",
    )
    policy_profiles: dict[str, PolicyProfileSettings] = Field(
        default_factory=dict,
        alias="POLICY_PROFILES_JSON",
    )
    active_policy_profile: str = Field(default="default", alias="ACTIVE_POLICY_PROFILE")

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
        return self

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


@lru_cache
def get_settings() -> Settings:
    """Return memoized settings for the running process."""
    return Settings(_env_file=os.getenv(SETTINGS_ENV_FILE_ENV_VAR, ".env"))  # type: ignore[call-arg]


def reset_settings_cache() -> None:
    """Clear cached settings; mainly used by tests and startup wiring."""
    get_settings.cache_clear()
