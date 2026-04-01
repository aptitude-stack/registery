# Development Setup

> This is the canonical local setup guide. The root `README.md` stays short and links here for the full workflow.

This guide shows the simplest way to run `Aptitude Registry` locally for development.

## Prerequisites

- Python `3.12+`
- [`uv`](https://docs.astral.sh/uv/)
- Docker

## 1. Start PostgreSQL

```bash
make db-up
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
make migrate-up
```

## 5. Start The API

```bash
make run
```

Local URLs:

- API: `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`
- Metrics: `http://127.0.0.1:8000/metrics`

## 6. Common Commands

```bash
make test
make lint
make format
make typecheck
make migrate-down
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
make observability-up
```

This starts the API plus:

- Prometheus at `http://127.0.0.1:9090`
- Loki at `http://127.0.0.1:3100`
- OTLP gRPC at `http://127.0.0.1:4317`
- OTLP HTTP at `http://127.0.0.1:4318`
- Grafana at `http://127.0.0.1:3000`

Shut the stack down with:

```bash
make observability-down
```

### Verify Log Flow

```bash
curl -H 'X-Request-ID: setup-dev-loki-check' http://127.0.0.1:8000/healthz
```

Then open Grafana and search for `setup-dev-loki-check` in the `Aptitude Registry Logs` dashboard.
