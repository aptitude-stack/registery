# Development Setup

> This is the canonical local setup guide. The root `README.md` stays short and links here for the full workflow.

This guide shows the simplest way to run `Aptitude Registry` locally for development.

## Prerequisites

- Python `3.12+`
- [uv](https://docs.astral.sh/uv/)
- Docker

## 1. Install Dependencies

```bash
uv sync --extra dev
```

The app settings layer loads `.env` by default for local process runs. If you need a different dotenv file for app startup or test runs, point `APP_SETTINGS_ENV_FILE` at it before starting the process.

If `uv` cannot write to its default global cache in your environment, keep the cache inside
the repo:

```bash
UV_CACHE_DIR=.uv-cache uv sync --extra dev
```

Recommended local dotenv layout:

- `.env`: local-only Compose/default app baseline created from `.env.example`
- `.env.example`: checked-in template only

Create the local dotenv file first:

```bash
cp .env.example .env
```

## 2. Run The Supported Stacks

Use the public `make` surface only:

```bash
make run-dev
make run-prod
```

`make run-dev` starts PostgreSQL, applies migrations, runs the API with `APP_ENV=dev`, seeds the demo profile, and starts observability.

`make run-prod` starts the same Compose stack with `APP_ENV=prod` and skips demo seeding.

If you need the precise split between app runtime profiles, Docker Compose profiles, and test-only env vars, use [`../reference/runtime-profiles.md`](../reference/runtime-profiles.md).
If you need the auth token shape, scope rules, or current dev fixture tokens, use [`../reference/service-token-governance.md`](../reference/service-token-governance.md).

Local URLs:

- API: `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`
- Metrics: shipped through OpenTelemetry when `OTEL_ENABLED=true`; no local `/metrics` HTTP route exists.

Integration tests still use the dedicated PostgreSQL container on `127.0.0.1:5433`, but that lifecycle is intentionally behind the public `make test` entrypoint.

## 2a. Run Only The FastAPI Process

Use this path when you want to debug app startup, settings, or FastAPI wiring without
bringing up the full Docker stack.

1. Leave any unrelated active virtualenv first.

```bash
deactivate
```

If `deactivate` is not defined, open a fresh shell in this repo instead. The goal is simple:
do not run the registry project while still activated inside another repo's `.venv`.

2. Start from the registry root and sync dependencies.

```bash
cd /Users/yonatan/Dev/Aptitude/registry
cp .env.example .env
uv sync --extra dev
```

3. Pick the app runtime profile explicitly.

- Use `APP_ENV=dev` for local debugging with docs enabled.
- Use `APP_ENV=prod` for production-like startup with docs and host validation enabled.

4. Start the ASGI server with the correct runtime posture.

```bash
APP_ENV=dev uv run uvicorn app.main:app --reload
APP_ENV=prod uv run uvicorn app.main:app
```

Use the `app.main:app` import string so the same application factory path is exercised
locally and in deployment.

5. If you need a different dotenv file than `.env`, set it explicitly.

```bash
APP_ENV=prod APP_SETTINGS_ENV_FILE=.env.local-prod uv run uvicorn app.main:app
```

6. Verify the app surface that matches the chosen profile.

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/docs
```

Expected results:

- in `APP_ENV=dev`, `/healthz` and `/docs` should both respond
- in `APP_ENV=prod`, `/healthz` and `/docs` should both respond when the host is allowed

If you are validating protected routes, remember that Plan 14 keeps auth requirements aligned
across both profiles. `dev` is not an auth bypass.

## 3. Common Commands

```bash
make quality
make test
make format
make build
```

Current behavior:

- `make quality` runs format-check, lint, and type-check gates.
- `make test` manages the dedicated `test-db` lifecycle and then runs the full pytest suite.
- `make format` applies Ruff formatting.
- `make build` pushes the configured multi-platform image with `docker buildx`; it is a distribution command, not a local smoke-check command.

## Quick Check

```bash
curl http://127.0.0.1:8000/healthz
```

For protected routes, use one of the dev-only fixture bearer tokens from `AUTH_SERVICE_TOKENS_JSON`:

```bash
Authorization: Bearer reader-token.dev-reader-secret
```

For telemetry validation, enable OTLP export and use the Grafana Cloud reference instead of probing a local `/metrics` route:

```bash
OTEL_ENABLED=true \
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-<region>.grafana.net/otlp \
uv run uvicorn app.main:app --reload
```

See [`../reference/observability-grafana-cloud.md`](../reference/observability-grafana-cloud.md) for the full setup.

Clients may also send an `X-Request-ID` header. The API echoes it on every response so logs, metrics, and audit rows can be correlated.

## Troubleshooting Startup Problems

### Problem: `VIRTUAL_ENV=... does not match the project environment path .venv`

Cause: your shell is still activated inside a different repo's virtualenv.

Fix:

1. Run `deactivate`, or open a new shell.
2. `cd /Users/yonatan/Dev/Aptitude/registry`
3. Run `uv sync --extra dev`
4. Start the command again with `uv run ...`

This is usually a warning, not the root failure. It means `uv` ignored the already-active
virtualenv and targeted the registry project environment instead.

### Problem: `To use the fastapi command, please install "fastapi[standard]"`

Cause: the project installs FastAPI as the web framework and `uvicorn[standard]` as the
runtime server. It does not install the optional FastAPI CLI package.

Fix:

1. Use `uvicorn app.main:app --reload` for local reload mode.
2. Use `uvicorn app.main:app` for production-style mode.
3. Set `APP_ENV` to the runtime profile you actually want.

```bash
APP_ENV=dev uv run uvicorn app.main:app --reload
APP_ENV=prod uv run uvicorn app.main:app
```

Do not switch production to the FastAPI CLI just to satisfy this error; that adds an
unused optional CLI dependency around an already installed ASGI server.

### Problem: `uv` fails to initialize its cache

Cause: the default home-directory cache is not writable in the current environment.

Fix:

```bash
UV_CACHE_DIR=.uv-cache uv sync --extra dev
UV_CACHE_DIR=.uv-cache APP_ENV=dev uv run uvicorn app.main:app --reload
```

This keeps the cache inside the repo and avoids permission errors on the global cache path.

### Problem: the app starts but exits on settings validation

Cause: the ASGI server started, but required app settings are missing or inconsistent for the
selected runtime profile.

Common examples:

- missing `DATABASE_URL`
- missing `ALLOWED_HOSTS_JSON` while `APP_ENV=prod`
- missing or malformed `AUTH_SERVICE_TOKENS_JSON` when you later hit protected routes

Fix:

1. Check which dotenv file the process is loading.
2. Set `APP_SETTINGS_ENV_FILE` if you are not using `.env`.
3. For `APP_ENV=prod`, provide `ALLOWED_HOSTS_JSON`.
4. Restart the process after changing env files.

Use the runtime and auth references for the exact settings contract:

- [`../reference/runtime-profiles.md`](../reference/runtime-profiles.md)
- [`../reference/service-token-governance.md`](../reference/service-token-governance.md)

## Observability

The local Grafana/Loki/Prometheus stack has been removed. Telemetry now flows
exclusively to Grafana Cloud over OTLP/HTTP from the running FastAPI process.
Set `OTEL_ENABLED=true` plus the `OTEL_EXPORTER_OTLP_*` env vars in your local
dotenv to ship local traces, logs, and metrics into the same Grafana Cloud
stack used in production (tag with `deployment.environment.name=dev` via
`OTEL_RESOURCE_ATTRIBUTES`).

See [`../reference/observability-grafana-cloud.md`](../reference/observability-grafana-cloud.md)
for the full env-var reference, Access Policy token scopes, and free-tier
limits.

When `OTEL_ENABLED=false` (the default), the process simply emits structured
JSON logs to stdout. That is sufficient for most app-level development.

## Optional Demo Profile

The demo profile is a one-shot Compose service that seeds a rich multi-version catalog after migrations. Use it when you want meaningful discovery, exact fetch, lifecycle, and dependency-resolution behavior without hand-publishing skills. `make run-dev` is the public entrypoint that turns it on.

Bring up the dev stack with demo data:

```bash
make run-dev
```

The `demo` profile remains opt-in. `make run-prod` stays bootstrap-only, while `make run-dev` adds the rich local catalog and switches the app runtime to `dev`.

Shut the stack down with:

```bash
docker compose down -v
```
