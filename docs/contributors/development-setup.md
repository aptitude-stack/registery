# Development Setup

> This is the canonical local setup guide. The root `README.md` stays short and links here for the full workflow.

This guide shows the simplest way to run `Aptitude Registry` locally for development.

## Prerequisites

- Python `3.12+`
- [uv](https://docs.astral.sh/uv/)
- Docker

## 1. Start PostgreSQL

```bash
make db
```

This starts PostgreSQL on `127.0.0.1:5432` with:

- database: `aptitude`
- user: `postgres`
- password: `postgres`

Integration tests should use the dedicated test database instead of the app database:

```bash
make db-test
```

This starts PostgreSQL on `127.0.0.1:5433` with:

- database: `aptitude_test`
- user: `postgres`
- password: `postgres`

## 2. Install Dependencies

```bash
uv venv
source .venv/bin/activate
uv sync --extra dev
```

## 3. Configure Environment

```bash
export DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude"
export TEST_DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5433/aptitude_test"
export AUTH_TOKENS_JSON='{"reader-token":["read"],"publisher-token":["read","publish"],"admin-token":["read","publish","admin"]}'
```

Optional:

```bash
export LOG_LEVEL="INFO"
export LOG_FORMAT="auto"
```

`LOG_FILE_PATH` is optional and only used by the Docker-based local observability profile.

## 4. Run Migrations

```bash
uv run alembic upgrade head
```

## 5. Start The API

```bash
uv run python -m app.main
```

Local URLs:

- API: `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`
- Metrics: `http://127.0.0.1:8000/metrics`

## 6. Common Commands

```bash
uv run --extra dev python -m pytest
make tests
make tests-unit
make tests-integration-container
uv run --extra dev ruff check .
uv run --extra dev ruff format .
uv run --extra dev python -m mypy app
uv run alembic downgrade -1
make stack
make stack-demo
make stack-observability
make stack-down
```

Dedicated integration database flows:

```bash
make tests-integration-container
make db-test
make tests-integration
make db-down
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
make stack-observability
```

This starts the API plus:

- Prometheus at `http://127.0.0.1:9090`
- Loki at `http://127.0.0.1:3100`
- OTLP gRPC at `http://127.0.0.1:4317`
- OTLP HTTP at `http://127.0.0.1:4318`
- Grafana at `http://127.0.0.1:3000`

`server` depends on `migrate`, so Compose applies the latest Alembic schema before the API starts.

## Optional Demo Profile

The demo profile is a one-shot Compose service that seeds a rich multi-version catalog after migrations. Use it when you want meaningful discovery, exact fetch, lifecycle, and dependency-resolution behavior without hand-publishing skills.

Seed the running stack in place:

```bash
make stack-demo
```

Bring up the full observability stack with demo data already loaded:

```bash
make stack-observability-demo
```

The `demo` profile is opt-in. Normal `make stack` and `make stack-observability` flows stay bootstrap-only, while `make stack-demo` or `make stack-observability-demo` add the rich local catalog only when you ask for it.

Shut the stack down with:

```bash
make stack-down
```

### Verify Log Flow

```bash
curl -H 'X-Request-ID: setup-dev-loki-check' http://127.0.0.1:8000/healthz
```

Then open Grafana and search for `setup-dev-loki-check` in the `Aptitude Registry Logs` dashboard.
