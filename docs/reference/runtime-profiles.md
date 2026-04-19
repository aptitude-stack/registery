# Runtime Profiles and Environment Variables

This repo has two different kinds of "profiles". They solve different problems and should not be mixed together.

## Runtime Profile: `APP_ENV`

`APP_ENV` is the application's runtime profile. It is validated and accepts only:

- `dev`: local development and fast iteration
- `prod`: deployed or production-like execution

`APP_ENV` changes runtime posture such as logging and future environment-specific wiring. It does not change the public HTTP contract. The same routes, request shapes, and response shapes must exist in both profiles.

Runtime posture changes that do apply today:

- `dev` keeps `/docs`, `/redoc`, and `/openapi.json` enabled.
- `prod` disables `/docs`, `/redoc`, and `/openapi.json`.
- `prod` enforces `ALLOWED_HOSTS_JSON` through trusted-host validation.
- protected routes require the same governed bearer-token auth in both `dev` and `prod`.

There is no `test`, `container`, or `staging` runtime profile in the app.

## FastAPI CLI vs `APP_ENV`

The FastAPI CLI mode and the app runtime profile are separate controls.

- `fastapi dev`: local server mode with reload, bound to `127.0.0.1` by default
- `fastapi run`: production-style server mode without reload
- `APP_ENV=dev|prod`: application runtime posture used by the registry settings layer

Do not assume `fastapi dev` automatically means `APP_ENV=dev`, or that `fastapi run`
automatically means `APP_ENV=prod`. Set `APP_ENV` explicitly when you care about the
app posture.

Recommended app-process commands:

```bash
APP_ENV=dev uv run fastapi dev
APP_ENV=prod uv run fastapi run
```

If the app process should read a dotenv file other than `.env`, point
`APP_SETTINGS_ENV_FILE` at it:

```bash
APP_ENV=prod APP_SETTINGS_ENV_FILE=.env.local-prod uv run fastapi run
```

Plan 14 keeps the route-protection model aligned across both profiles. `dev` does not
add an auth bypass; it mainly keeps local-only conveniences such as docs exposure.

## Recommended Local Env Files

Keep the default local workflow on one dotenv file:

- `.env`: local-only defaults for the checked-in Docker Compose stack and local app-process startup
- `.env.example`: checked-in template only

Create your local file with `cp .env.example .env`.
Use `APP_ENV=dev|prod` on the command line to select the runtime profile.
Only introduce `APP_SETTINGS_ENV_FILE` when you truly need an alternate dotenv file,
for example a one-off local prod-like experiment or a deployment-specific secret set.

## Compose Profiles

Docker Compose also uses profiles, but those are orchestration selectors, not app runtime modes.

Current Compose profiles include:

- `demo`: adds the demo seed job
- `observability`: adds Prometheus, Grafana, Loki, and related tooling
- `test`: adds the dedicated test PostgreSQL container

These Compose profiles decide which containers run. They do not define new FastAPI behaviors or new `APP_ENV` values.

## Test and CI Environments

Tests and CI are execution environments, not runtime profiles.

- Most tests should boot the app with `APP_ENV=prod` when they need production-like behavior.
- Tests should use `APP_ENV=dev` only when they explicitly validate local-development behavior.
- The dedicated test database is selected with `TEST_DATABASE_URL`, not with a special app runtime profile.

## Common Variables

- `APP_ENV`: runtime profile for the app (`dev` or `prod`)
- `DATABASE_URL`: primary application database
- `TEST_DATABASE_URL`: dedicated database used by integration-test flows
- `AUTH_SERVICE_TOKENS_JSON`: governed service-token registry records used by authenticated routes
- `ALLOWED_HOSTS_JSON`: required host allowlist when `APP_ENV=prod`
- `POLICY_PROFILES_JSON`: optional named governance-profile overrides merged over the built-in default profile
- `ACTIVE_POLICY_PROFILE`: selects which policy profile is active at runtime; defaults to `default`
- `LOG_LEVEL`, `LOG_FORMAT`, `LOG_FILE_PATH`: logging configuration
- `APP_SETTINGS_ENV_FILE`: optional alternate dotenv file path for app-process startup; otherwise the app loads `.env`

Service-token settings use this JSON shape:

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

Clients send the raw secret only over HTTP:

```text
Authorization: Bearer reader-token.dev-reader-secret
```

## Practical Defaults

- `make run-dev` starts the checked-in Compose stack with `APP_ENV=dev`, the `demo` profile, and the `observability` profile
- `make run-prod` starts the checked-in Compose stack with `APP_ENV=prod` and the `observability` profile
- raw `docker compose` usage defaults the checked-in app services to `APP_ENV=prod` unless you override `APP_ENV`
- `make test` manages the dedicated `test` profile database container for the full test suite
- `LOG_FORMAT=auto` prefers readable local logs in `dev` and structured JSON logs in `prod`
- app-process startup reads local `.env` unless `APP_SETTINGS_ENV_FILE` points to another dotenv file
- forwarded proxy headers stay untrusted by default; enable them explicitly at the deploy entrypoint behind a trusted proxy
