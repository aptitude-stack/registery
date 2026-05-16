"""Generate a governed service token and matching settings digest record."""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys

DEFAULT_TOKEN_ID = "telemetry_prod"
DEFAULT_SCOPES = ("telemetry",)
DEFAULT_SECRET_BYTES = 32


def main() -> int:
    args = _parse_args()
    if "." in args.token_id:
        print("token id must not contain `.`", file=sys.stderr)
        return 2
    if args.secret_bytes < 1:
        print("secret bytes must be at least 1", file=sys.stderr)
        return 2

    secret = args.secret or secrets.token_urlsafe(args.secret_bytes)
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    bearer_token = f"{args.token_id}.{secret}"
    record = {
        "token_id": args.token_id,
        "secret_digest": digest,
        "scopes": args.scope,
        "namespace_grants": [],
        "active": True,
    }

    if args.json:
        print(json.dumps({"token": bearer_token, "record": record}, sort_keys=True))
        return 0

    print(f"Bearer token:\n{bearer_token}\n")
    print(f"Secret digest:\n{digest}\n")
    print("AUTH_SERVICE_TOKENS_JSON record:")
    print(json.dumps(record, separators=(",", ":"), sort_keys=True))
    print("\nWebsite env:")
    print(f"REGISTRY_TELEMETRY_TOKEN={bearer_token}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--token-id",
        default=DEFAULT_TOKEN_ID,
        help=f"service token id in token-name_prod form; defaults to {DEFAULT_TOKEN_ID}",
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
    if args.scope is None:
        args.scope = list(DEFAULT_SCOPES)
    return args


if __name__ == "__main__":
    raise SystemExit(main())
