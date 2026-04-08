# Development Setup

> This is the canonical local setup guide. The root `README.md` stays short and links here for the full workflow.

This guide shows the simplest way to run `Aptitude Registry` locally for development.

## Prerequisites

- Python `3.12+`
- [uv](https://docs.astral.sh/uv/)
- Docker

## 1. Start PostgreSQL

```bash
docker compose up -d db
```

This starts PostgreSQL on `127.0.0.1:5432` with:

- database: `aptitude`
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
uv run --extra dev ruff check .
uv run --extra dev ruff format .
uv run --extra dev python -m mypy app
uv run alembic downgrade -1
docker compose down -v
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
docker compose --profile observability up -d server observability
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
docker compose --profile demo run --rm demo-seed
```

Bring up the full observability stack with demo data already loaded:

```bash
docker compose up -d server
docker compose --profile demo run --rm demo-seed
docker compose --profile observability up -d server observability
```

The `demo` profile is opt-in. Normal `docker compose up -d server` and `docker compose --profile observability up -d server observability` flows stay bootstrap-only, while `docker compose --profile demo run --rm demo-seed` adds the rich local catalog only when you ask for it.

Shut the stack down with:

```bash
docker compose down -v
```

### Verify Log Flow

```bash
curl -H 'X-Request-ID: setup-dev-loki-check' http://127.0.0.1:8000/healthz
```

Then open Grafana and search for `setup-dev-loki-check` in the `Aptitude Registry Logs` dashboard.
