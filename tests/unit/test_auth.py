"""Unit tests for governed service-token authentication."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.auth import AuthError, AuthorizationError, AuthService, InMemoryServiceTokenLookup
from app.core.ports import ServiceTokenRecord


def _service(*, expires_at: datetime | None = None, active: bool = True) -> AuthService:
    return AuthService(
        token_lookup=InMemoryServiceTokenLookup(
            records=(
                ServiceTokenRecord(
                    token_id="reader-token",
                    secret_digest="5f2a948f1a0f51d636721e4381eaf64fc8032a03b540a12da0645e0edc564084",
                    scopes=frozenset({"read"}),
                    active=active,
                    expires_at=expires_at,
                ),
            )
        ),
        now_provider=lambda: datetime(2026, 4, 18, tzinfo=UTC),
    )


@pytest.mark.unit
def test_authenticate_valid_service_token() -> None:
    caller = _service().authenticate(
        scheme="Bearer",
        credentials="reader-token.dev-reader-secret",
    )

    assert caller.token_id == "reader-token"
    assert caller.scopes == frozenset({"read"})


@pytest.mark.unit
def test_authenticate_requires_credentials() -> None:
    with pytest.raises(AuthError) as exc_info:
        _service().authenticate(scheme=None, credentials=None)

    assert exc_info.value.code == "AUTHENTICATION_REQUIRED"


@pytest.mark.unit
def test_authenticate_rejects_wrong_scheme() -> None:
    with pytest.raises(AuthError) as exc_info:
        _service().authenticate(
            scheme="Basic",
            credentials="reader-token.dev-reader-secret",
        )

    assert exc_info.value.code == "MALFORMED_AUTH_TOKEN"


@pytest.mark.unit
def test_authenticate_rejects_malformed_token() -> None:
    with pytest.raises(AuthError) as exc_info:
        _service().authenticate(scheme="Bearer", credentials="reader-token")

    assert exc_info.value.code == "MALFORMED_AUTH_TOKEN"


@pytest.mark.unit
def test_authenticate_rejects_unknown_token_id() -> None:
    with pytest.raises(AuthError) as exc_info:
        _service().authenticate(
            scheme="Bearer",
            credentials="unknown-token.dev-reader-secret",
        )

    assert exc_info.value.code == "INVALID_AUTH_TOKEN"


@pytest.mark.unit
def test_authenticate_rejects_wrong_secret() -> None:
    with pytest.raises(AuthError) as exc_info:
        _service().authenticate(
            scheme="Bearer",
            credentials="reader-token.wrong-secret",
        )

    assert exc_info.value.code == "INVALID_AUTH_TOKEN"


@pytest.mark.unit
def test_authenticate_rejects_inactive_token() -> None:
    with pytest.raises(AuthError) as exc_info:
        _service(active=False).authenticate(
            scheme="Bearer",
            credentials="reader-token.dev-reader-secret",
        )

    assert exc_info.value.code == "INACTIVE_AUTH_TOKEN"


@pytest.mark.unit
def test_authenticate_rejects_expired_token() -> None:
    with pytest.raises(AuthError) as exc_info:
        _service(expires_at=datetime(2026, 4, 17, tzinfo=UTC)).authenticate(
            scheme="Bearer",
            credentials="reader-token.dev-reader-secret",
        )

    assert exc_info.value.code == "EXPIRED_AUTH_TOKEN"


@pytest.mark.unit
def test_require_scope_rejects_missing_scope() -> None:
    caller = _service().authenticate(
        scheme="Bearer",
        credentials="reader-token.dev-reader-secret",
    )

    with pytest.raises(AuthorizationError) as exc_info:
        _service().require_scope(caller=caller, scope="publish")

    assert exc_info.value.required_scope == "publish"


@pytest.mark.unit
def test_authenticate_accepts_future_expiry() -> None:
    caller = _service(
        expires_at=datetime(2026, 4, 18, tzinfo=UTC) + timedelta(days=1)
    ).authenticate(
        scheme="Bearer",
        credentials="reader-token.dev-reader-secret",
    )

    assert caller.token_id == "reader-token"
