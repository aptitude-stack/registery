# Aptitude Registry

![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![uv](https://img.shields.io/badge/uv-managed-6E56CF?style=for-the-badge&logo=uv&logoColor=white)
![FastAPI](https://img.shields.io/badge/fastapi-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Pydantic](https://img.shields.io/badge/pydantic-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/sqlalchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)
![Postgres](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![pytest](https://img.shields.io/badge/pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)
![Ruff](https://img.shields.io/badge/ruff-D7FF64?style=for-the-badge&logo=ruff&logoColor=111111)
![Docker](https://img.shields.io/badge/docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Prometheus](https://img.shields.io/badge/prometheus-E6522C?style=for-the-badge&logo=prometheus&logoColor=white)
![Grafana](https://img.shields.io/badge/grafana-F46800?style=for-the-badge&logo=grafana&logoColor=white)
![Loki](https://img.shields.io/badge/loki-F2CC0C?style=for-the-badge&logo=grafana&logoColor=111111)
![Last Commit](https://img.shields.io/github/last-commit/aptitude-stack/server?style=for-the-badge)

`Aptitude Registry` is the registry backend in the Aptitude ecosystem. It stores immutable skill metadata, digest-addressed markdown content, lifecycle state, provenance snapshots, and audit data in PostgreSQL so callers can publish exact versions, discover candidate slugs, read direct authored dependencies, and fetch immutable metadata/content without crawling the full catalog.

## Overview

- Owns immutable publication, discovery candidate generation, exact dependency reads, exact metadata/content fetch, lifecycle governance, audit, and operational telemetry.
- Does not own prompt interpretation, reranking, final selection, dependency solving, lock generation, or execution planning. Those remain resolver/client concerns.
- Uses PostgreSQL as the only authoritative runtime store, with deliberate separation between discovery-facing metadata/search models and exact-fetch content storage.

## System Design

```mermaid
flowchart LR
    Publisher["Publisher / CI"]
    Resolver["Resolver / MCP / CLI"]
    Ops["Ops / observability"]

    subgraph Registry["Aptitude Registry"]
        direction TB
        Interface["Interface layer<br/>publish, discovery, resolution, fetch"]
        Core["Core services<br/>registry, discovery, fetch, governance"]
        Adapters["Persistence + audit adapters"]
    end

    Storage["Registry storage<br/>versions, metadata, content,<br/>selectors, search, audit"]

    Publisher -->|publish / lifecycle writes| Interface
    Resolver <-->|discovery / resolution / exact fetch| Interface
    Ops <-->|health / metrics / logs / runbooks| Interface
    Interface --> Core
    Core --> Adapters
    Adapters <-->|reads / writes| Storage
```

Design rules:

- Registry owns data-local work; resolver owns decision-local work.
- Discovery returns ordered slug candidates only.
- Resolution returns direct authored `depends_on` selectors only.
- Exact fetch stays coordinate-based and immutable.
- Canonical contract and boundary docs live under [`docs/reference/api-contract.md`](docs/reference/api-contract.md) and [`docs/architecture/server-resolver-boundary.md`](docs/architecture/server-resolver-boundary.md).

## Route Surface

The current public HTTP baseline is:

- `GET /healthz`
- `GET /readyz`
- `GET /metrics`
- `POST /skills/{slug}`
- `POST /discovery`
- `GET /skills/{slug}`
- `GET /resolution/{slug}/{version}`
- `GET /skills/{slug}/{version}`
- `GET /skills/{slug}/{version}/content`
- `PATCH /skills/{slug}/{version}/status`

Use [`docs/reference/api-contract.md`](docs/reference/api-contract.md) as the canonical route and payload contract.

## Quick Start

Requirements:

- Python `3.12+`
- [`uv`](https://docs.astral.sh/uv/)
- Docker

Local development:

```bash
make db-up
uv venv
source .venv/bin/activate
uv sync --extra dev
export DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude"
export AUTH_TOKENS_JSON='{"reader-token":["read"],"publisher-token":["read","publish"],"admin-token":["read","publish","admin"]}'
make migrate-up
make run
```

Local URLs:

- API: `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`
- Metrics: `http://127.0.0.1:8000/metrics`

For the full setup flow, observability profile, verification commands, and troubleshooting entrypoints, use [`docs/contributors/development-setup.md`](docs/contributors/development-setup.md) and [`docs/reference/operations/README.md`](docs/reference/operations/README.md).

## Documentation

- [`docs/README.md`](docs/README.md): documentation index and reading routes
- [`docs/architecture/README.md`](docs/architecture/README.md): canonical architecture reading order
- [`docs/reference/api-contract.md`](docs/reference/api-contract.md): canonical HTTP contract
- [`docs/architecture/server-resolver-boundary.md`](docs/architecture/server-resolver-boundary.md): registry vs resolver boundary
- [`docs/contributors/README.md`](docs/contributors/README.md): contributor workflow docs
- [`docs/reference/README.md`](docs/reference/README.md): stable technical reference
- [`docs/roadmap/README.md`](docs/roadmap/README.md): forward-looking technical direction
- [`.agents/README.md`](.agents/README.md): agent-facing operating context
