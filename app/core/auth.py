"""Governed service-token authentication and authorization helpers."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from app.core.governance import CallerIdentity, CallerScope
from app.core.ports import ServiceTokenLookupPort, ServiceTokenRecord

AuthErrorCode = Literal[
    "AUTHENTICATION_REQUIRED",
    "MALFORMED_AUTH_TOKEN",
    "INVALID_AUTH_TOKEN",
    "INACTIVE_AUTH_TOKEN",
    "EXPIRED_AUTH_TOKEN",
]


class AuthError(RuntimeError):
    """Raised when bearer authentication fails."""

    def __init__(self, *, code: AuthErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AuthorizationError(RuntimeError):
    """Raised when an authenticated caller lacks a required scope."""

    def __init__(self, *, required_scope: CallerScope) -> None:
        super().__init__("Caller lacks the required scope.")
        self.required_scope = required_scope


@dataclass(frozen=True, slots=True)
class ParsedServiceToken:
    """One parsed bearer token in `<token_id>.<token_secret>` format."""

    token_id: str
    token_secret: str


class InMemoryServiceTokenLookup(ServiceTokenLookupPort):
    """Simple in-memory lookup used by the settings-backed auth adapter."""

    def __init__(self, *, records: Iterable[ServiceTokenRecord]) -> None:
        self._records = {record.token_id: record for record in records}

    def get_token(self, *, token_id: str) -> ServiceTokenRecord | None:
        return self._records.get(token_id)


class AuthService:
    """Authenticate and authorize governed service tokens."""

    def __init__(
        self,
        *,
        token_lookup: ServiceTokenLookupPort,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._token_lookup = token_lookup
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    def authenticate(
        self,
        *,
        scheme: str | None,
        credentials: str | None,
    ) -> CallerIdentity:
        """Return the authenticated caller for one bearer credential pair."""
        if credentials is None:
            raise AuthError(
                code="AUTHENTICATION_REQUIRED",
                message="Bearer token is required.",
            )
        if scheme is None or scheme.lower() != "bearer":
            raise AuthError(
                code="MALFORMED_AUTH_TOKEN",
                message="Authorization header must use the Bearer scheme.",
            )

        presented = _parse_service_token(credentials)
        record = self._token_lookup.get_token(token_id=presented.token_id)
        if record is None:
            raise AuthError(
                code="INVALID_AUTH_TOKEN",
                message="Bearer token is not recognized.",
            )
        if not _secret_matches(record=record, token_secret=presented.token_secret):
            raise AuthError(
                code="INVALID_AUTH_TOKEN",
                message="Bearer token is not recognized.",
            )
        if not record.active:
            raise AuthError(
                code="INACTIVE_AUTH_TOKEN",
                message="Bearer token is inactive.",
            )
        if _is_expired(record=record, now=self._now_provider()):
            raise AuthError(
                code="EXPIRED_AUTH_TOKEN",
                message="Bearer token is expired.",
            )
        return CallerIdentity(
            token_id=record.token_id,
            scopes=record.scopes,
            namespace_grants=record.namespace_grants,
        )

    def require_scope(self, *, caller: CallerIdentity, scope: CallerScope) -> CallerIdentity:
        """Return the caller when the required scope is available."""
        if not caller.has_scope(scope):
            raise AuthorizationError(required_scope=scope)
        return caller


def _parse_service_token(token: str) -> ParsedServiceToken:
    token_id, separator, token_secret = token.partition(".")
    if separator != "." or not token_id or not token_secret:
        raise AuthError(
            code="MALFORMED_AUTH_TOKEN",
            message="Bearer token must use the `<token_id>.<token_secret>` format.",
        )
    return ParsedServiceToken(token_id=token_id, token_secret=token_secret)


def _secret_matches(*, record: ServiceTokenRecord, token_secret: str) -> bool:
    presented_digest = hashlib.sha256(token_secret.encode("utf-8")).hexdigest()
    return hmac.compare_digest(record.secret_digest, presented_digest)


def _is_expired(*, record: ServiceTokenRecord, now: datetime) -> bool:
    if record.expires_at is None:
        return False
    return record.expires_at <= now.astimezone(UTC)
