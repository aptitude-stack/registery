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
    "namespace_grants": [
      {
        "namespace": "public",
        "roles": ["read"],
        "promotion_channels": ["prod"]
      }
    ],
    "expires_at": null
  }
]
```

Rules:

- `token_id` is the stable public identifier and must not contain `.`
- `secret_digest` is the lowercase `sha256` hex digest of the raw secret only
- `namespace_grants` grants namespace roles plus allowed promotion channels
- `active=false` revokes the token without deleting its record
- `expires_at` is optional and must include a timezone offset when present

`ALLOWED_HOSTS_JSON` defines the required host allowlist in `APP_ENV=prod`.
The deployed registry API host is `api.aptitude-registry.dev`, so production env must include it.
During initial Render rollout, also include the Render `onrender.com` service host until custom-domain verification and health checks are stable.

## Scopes

- `read`: discovery, exact metadata/content fetch, resolution, and version listing
- `publish`: immutable version publication
- `review`: review, promotion, trust-tier, policy-pack, and trust-evidence workflow operations
- `admin`: lifecycle updates and enterprise bootstrap routes

`admin` still implies the lower scopes in the runtime policy.

## Namespace Grants

Every protected registry operation requires both the route-level scope and the namespace grant for the affected namespace.

```json
{
  "namespace": "payments",
  "roles": ["read", "publish", "review"],
  "promotion_channels": ["dev", "staging"]
}
```

Grant rules:

- `namespace` is a registry namespace slug, or `*` for global bootstrap/admin tokens only.
- `roles` accepts `read`, `publish`, `review`, and `admin`.
- `promotion_channels` accepts `dev`, `staging`, `prod`, or `*`.
- `read` grants limit discovery, version listing, exact metadata, exact content, and resolution.
- `publish` grants limit which namespace/channel a token can publish into.
- `review` grants limit review, promotion, trust-tier, policy-pack, and trust-evidence updates.
- `*` grants should be reserved for global admin/bootstrap tokens.

Older token records without explicit `namespace_grants` are treated as public-catalog records:

- non-admin tokens receive grants for `public` and `prod` based on their route scopes
- admin tokens receive a global `*` grant

## Error Codes

Authentication and authorization failures use stable API error codes:

- `AUTHENTICATION_REQUIRED`
- `MALFORMED_AUTH_TOKEN`
- `INVALID_AUTH_TOKEN`
- `INACTIVE_AUTH_TOKEN`
- `EXPIRED_AUTH_TOKEN`
- `INSUFFICIENT_SCOPE`
- `POLICY_NAMESPACE_FORBIDDEN`

## Prod Posture

- `/docs`, `/redoc`, and `/openapi.json` are enabled in `prod`; admin and HTML
  helper routes are excluded from the public schema
- `TrustedHostMiddleware` enforces `ALLOWED_HOSTS_JSON` in `prod`
- forwarded proxy headers remain untrusted by default at the app boundary
- operational telemetry is shipped via OTLP/HTTP to Grafana Cloud rather than scraped from the app, so the public surface no longer exposes a metrics endpoint at all

## Dev Fixtures

The checked-in local stack uses explicit dev-only example tokens:

- `reader-token.dev-reader-secret`
- `publisher-token.dev-publisher-secret`
- `admin-token.dev-admin-secret`

These are local bootstrap credentials only. Non-local deployments should inject their own governed token records.
