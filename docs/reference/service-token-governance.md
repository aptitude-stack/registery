# Service Token Governance

Canonical auth boundary for `Aptitude Registry`.

## Scope

The registry uses machine-to-machine bearer tokens only.

- no user accounts
- no browser sessions
- no OAuth2 or JWT flows
- no token introspection or rotation endpoints

Protected routes accept exactly:

```text
Authorization: Bearer <token_id>.<token_secret>
```

## Settings

`AUTH_SERVICE_TOKENS_JSON` is the governed token registry loaded at startup.
For local development, define it in your local `.env` created from `.env.example`.
For non-local deployments, inject it through deployment environment variables or secrets management.

```json
[
  {
    "token_id": "reader-token",
    "secret_digest": "sha256-hex-of-secret",
    "scopes": ["read"],
    "active": true,
    "expires_at": null
  }
]
```

Rules:

- `token_id` is the stable public identifier and must not contain `.`
- `secret_digest` is the lowercase `sha256` hex digest of the raw secret only
- `active=false` revokes the token without deleting its record
- `expires_at` is optional and must include a timezone offset when present

`ALLOWED_HOSTS_JSON` defines the required host allowlist in `APP_ENV=prod`.

## Scopes

- `read`: discovery, exact metadata/content fetch, resolution, and version listing
- `publish`: immutable version publication
- `admin`: lifecycle updates and `/metrics`

`admin` still implies the lower scopes in the runtime policy.

## Error Codes

Authentication and authorization failures use stable API error codes:

- `AUTHENTICATION_REQUIRED`
- `MALFORMED_AUTH_TOKEN`
- `INVALID_AUTH_TOKEN`
- `INACTIVE_AUTH_TOKEN`
- `EXPIRED_AUTH_TOKEN`
- `INSUFFICIENT_SCOPE`

## Prod Posture

- `/docs`, `/redoc`, and `/openapi.json` are disabled in `prod`
- `TrustedHostMiddleware` enforces `ALLOWED_HOSTS_JSON` in `prod`
- forwarded proxy headers remain untrusted by default at the app boundary
- `/metrics` is protected in-app with `admin` scope, including local observability

## Dev Fixtures

The checked-in local stack uses explicit dev-only example tokens:

- `reader-token.dev-reader-secret`
- `publisher-token.dev-publisher-secret`
- `admin-token.dev-admin-secret`

These are local bootstrap credentials only. Non-local deployments should inject their own governed token records.
