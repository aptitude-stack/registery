"""Generate a governed service token and matching settings digest record."""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
from dataclasses import dataclass

DEFAULT_SCOPES = ("telemetry",)
DEFAULT_SECRET_BYTES = 32
NAMESPACE_GRANT_PROD = ("prod",)
NAMESPACE_GRANT_ALL_CHANNELS = ("*",)


@dataclass(frozen=True)
class TokenSpec:
    """Production token shape emitted for Render and website configuration."""

    env_name: str
    token_id: str
    scopes: tuple[str, ...]
    namespace_grants: tuple[dict[str, object], ...]


PRODUCTION_TOKEN_SPECS = (
    TokenSpec(
        env_name="READ_TOKEN",
        token_id="reader-prod",
        scopes=("read",),
        namespace_grants=(
            {
                "namespace": "public",
                "roles": ["read"],
                "promotion_channels": list(NAMESPACE_GRANT_PROD),
            },
        ),
    ),
    TokenSpec(
        env_name="TELEMETRY_TOKEN",
        token_id="telemetry_prod",
        scopes=("telemetry",),
        namespace_grants=(),
    ),
    TokenSpec(
        env_name="PUBLISH_TOKEN",
        token_id="publisher-prod",
        scopes=("read", "publish"),
        namespace_grants=(
            {
                "namespace": "public",
                "roles": ["read", "publish"],
                "promotion_channels": list(NAMESPACE_GRANT_PROD),
            },
        ),
    ),
    TokenSpec(
        env_name="ADMIN_TOKEN",
        token_id="admin-prod",
        scopes=("read", "publish", "review", "admin"),
        namespace_grants=(
            {
                "namespace": "*",
                "roles": ["read", "publish", "review", "admin"],
                "promotion_channels": list(NAMESPACE_GRANT_ALL_CHANNELS),
            },
        ),
    ),
)


def main() -> int:
    args = _parse_args()
    if args.secret_bytes < 1:
        print("secret bytes must be at least 1", file=sys.stderr)
        return 2

    if args.token_id is not None or args.scope is not None:
        return _emit_single_token(args)

    generated_tokens = tuple(_generate_token(spec, args=args) for spec in PRODUCTION_TOKEN_SPECS)
    records = [token["record"] for token in generated_tokens]
    bearer_tokens = {token["env_name"]: token["bearer_token"] for token in generated_tokens}

    if args.json:
        print(
            json.dumps(
                {
                    "tokens": bearer_tokens,
                    "auth_service_tokens_json": records,
                },
                sort_keys=True,
            )
        )
        return 0

    print(f"AUTH_SERVICE_TOKENS_JSON={json.dumps(records, separators=(',', ':'), sort_keys=True)}")
    print("\nBearer tokens:")
    for env_name, bearer_token in bearer_tokens.items():
        print(f"{env_name}={bearer_token}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--token-id",
        default=None,
        help=(
            "generate one custom service-token record for this token id; "
            "omit to generate the full production token set"
        ),
    )
    parser.add_argument(
        "--scope",
        action="append",
        choices=("read", "publish", "review", "admin", "telemetry"),
        default=None,
        help=(
            "scope to include in the settings record; repeat for multiple scopes; "
            "defaults to telemetry"
        ),
    )
    parser.add_argument(
        "--secret",
        help="existing token secret to digest; omitted generates a fresh random secret",
    )
    parser.add_argument(
        "--secret-bytes",
        type=int,
        default=DEFAULT_SECRET_BYTES,
        help=f"number of random bytes before urlsafe encoding; defaults to {DEFAULT_SECRET_BYTES}",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print one machine-readable JSON object instead of env snippets",
    )
    args = parser.parse_args()
    if args.token_id is not None and "." in args.token_id:
        print("token id must not contain `.`", file=sys.stderr)
        raise SystemExit(2)
    if args.token_id is not None and args.scope is None:
        args.scope = list(DEFAULT_SCOPES)
    return args


def _emit_single_token(args: argparse.Namespace) -> int:
    token_id = args.token_id or "telemetry_prod"
    scopes = args.scope or list(DEFAULT_SCOPES)
    token = _build_token(
        env_name="SERVICE_TOKEN",
        token_id=token_id,
        scopes=scopes,
        namespace_grants=(),
        secret=args.secret or secrets.token_urlsafe(args.secret_bytes),
    )
    record = token["record"]
    bearer_token = token["bearer_token"]

    if args.json:
        print(json.dumps({"token": bearer_token, "record": record}, sort_keys=True))
        return 0

    print(f"Bearer token:\n{bearer_token}\n")
    print(f"Secret digest:\n{record['secret_digest']}\n")
    print("AUTH_SERVICE_TOKENS_JSON record:")
    print(json.dumps(record, separators=(",", ":"), sort_keys=True))
    print("\nAUTH_SERVICE_TOKENS_JSON single-token value:")
    print(json.dumps([record], separators=(",", ":"), sort_keys=True))
    return 0


def _generate_token(spec: TokenSpec, *, args: argparse.Namespace) -> dict[str, object]:
    return _build_token(
        env_name=spec.env_name,
        token_id=spec.token_id,
        scopes=spec.scopes,
        namespace_grants=spec.namespace_grants,
        secret=args.secret or secrets.token_urlsafe(args.secret_bytes),
    )


def _build_token(
    *,
    env_name: str,
    token_id: str,
    scopes: list[str] | tuple[str, ...],
    namespace_grants: tuple[dict[str, object], ...],
    secret: str,
) -> dict[str, object]:
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    return {
        "env_name": env_name,
        "bearer_token": f"{token_id}.{secret}",
        "record": {
            "token_id": token_id,
            "secret_digest": digest,
            "scopes": list(scopes),
            "namespace_grants": list(namespace_grants),
            "active": True,
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
