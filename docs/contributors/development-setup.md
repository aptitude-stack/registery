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

## 2. Run The Supported Stacks

Use the public `make` surface only:

```bash
make run-dev
make run-prod
```

`make run-dev` starts PostgreSQL, applies migrations, runs the API with `APP_ENV=dev`, seeds the demo profile, and starts observability.

`make run-prod` starts the same Compose stack with `APP_ENV=prod` and skips demo seeding.

If you need the precise split between app runtime profiles, Docker Compose profiles, and test-only env vars, use [`../reference/runtime-profiles.md`](../reference/runtime-profiles.md).

Local URLs:

- API: `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`
- Metrics: `http://127.0.0.1:8000/metrics`

Integration tests still use the dedicated PostgreSQL container on `127.0.0.1:5433`, but that lifecycle is intentionally behind the public `make test` entrypoint.

## 3. Common Commands

```bash
make quality
make test
make format
make build
```

## Quick Check

```bash
curl http://127.0.0.1:8000/healthz
```

For authenticated routes, send one of the tokens from `AUTH_TOKENS_JSON` as:

```bash
Authorization: Bearer reader-token
```

Clients may also send an `X-Request-ID` header. The API echoes it on every response so logs, metrics, and audit rows can be correlated.

## Optional Local Observability Profile

```bash
make run-prod
```

This starts the API plus:

- Prometheus at `http://127.0.0.1:9090`
- Loki at `http://127.0.0.1:3100`
- OTLP gRPC at `http://127.0.0.1:4317`
- OTLP HTTP at `http://127.0.0.1:4318`
- Grafana at `http://127.0.0.1:3000`

`server` depends on `migrate`, so Compose applies the latest Alembic schema before the API starts.

## Optional Demo Profile

The demo profile is a one-shot Compose service that seeds a rich multi-version catalog after migrations. Use it when you want meaningful discovery, exact fetch, lifecycle, and dependency-resolution behavior without hand-publishing skills. `make run-dev` is the public entrypoint that turns it on.

Bring up the dev stack with demo data and observability:

```bash
make run-dev
```

The `demo` profile remains opt-in. `make run-prod` stays bootstrap-only, while `make run-dev` adds the rich local catalog and switches the app runtime to `dev`.

Shut the stack down with:

```bash
docker compose --profile observability down -v
```

### Verify Log Flow

```bash
curl -H 'X-Request-ID: setup-dev-loki-check' http://127.0.0.1:8000/healthz
```

Then open Grafana and search for `setup-dev-loki-check` in the `Aptitude Registry Logs` dashboard.
