# Aptitude Registry

![Python](https://img.shields.io/badge/python-3-12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
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
[![DeepWiki](https://img.shields.io/badge/Ask-DeepWiki-0A66C2?style=for-the-badge&logo=data%3Aimage%2Fpng%3Bbase64%2CiVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAMAAABEpIrGAAAAsVBMVEVHcEwmWMYZy38Akt0gwZoSaFIbYssUmr4gwJkBlN4WbNE4acofwZkBj9k4aMkBk94WgM0bsIM4aMkewJc2ZMM3Z8cbvIwYpHsewJYAftgBkt0fvpgBkt0cv44cv5wzYckAjtsCk90pasUboXsgwJkfwpYfwJg4aMoct44yXswAkd0BkN84Z8cBktwduZIjcO85lM4hwZo5acoBleA6a88iyaABmOQ8b9QhxZ0CnOoizaOW4DOvAAAAMHRSTlMAKCfW%2FAgWA%2F7%2FDfvMc9j7MU%2Frj3XBcRW%2FJMbe7kUxjI%2FlUzzz6tPQkJ%2BjVmW1oeulmmslAAAByUlEQVQ4y32Tia6jIBSGUVFcqliXtlq73rm3d50ERNC%2B%2F4PNQetoptMeE0PgC%2F9%2FFhCaBSH9Hz2J%2BONgPDl2DolSUWY%2FPL8oEQRCfPxHpFc3Ah5wHoiI6I05NXgjAOgQF3Jn1Dlo4XMPDDes09UE2d%2BREvl3lijBg4CrHNmrbcM2u9u5nwsRcAFfFHFY5sZ607Yua3GqpQiKE6G9cZHZThblZ4T2mLnMxde3ATASMUj72o0Pbs1fADDcLHqAjEDugJ3lC%2BztMGYTADcoLaFyH%2B02DP9%2BWS4ahrXE4laALFKcq8vZfscNY8312mxfr27bLJZjnsYhSDIHmUxLu9h9N%2Fep%2B7pazwoZQw%2B1Nwi33epu7c2p8RooeqCdAHMGoOJIq3CUwIMEniRIaHVe3ZVnO2Vgsh1MstEkQUXVUc%2BjXfk3zbemxS6%2BpQmlPtUeALJ8VKj4JHvAelBqFFdSS3h1SPzQKr%2F%2BaRa0%2B0cCIWtJLauG5U%2FfbgyG01uiNqQhyzA8ddKj1OvK28AsZyN3DKE4X6AEWrU1jJx9N7RFpdPxpHU%2FtMOQG9SjfTp3Yz8KgRVKpfx88Dqhpseq606h%2F%2Bzxfh6LJ8eEDKWbxx9XEDwqzP1SVgAAAABJRU5ErkJggg%3D%3D)](https://deepwiki.com/y0ncha/aptitude-server)
![Last Commit](https://img.shields.io/github/last-commit/y0ncha/aptitude-server?style=for-the-badge)

`Aptitude Registry` is the registry backend in the Aptitude ecosystem. It stores immutable skill metadata, digest-addressed bundle artifacts, lifecycle state, provenance snapshots, and audit data in PostgreSQL so callers can publish exact versions, discover candidate slugs, read direct authored dependencies, and fetch immutable metadata or the exact stored artifact without crawling the full catalog.

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

The registry is organized as a small layered service around PostgreSQL. The interface layer exposes publish, discovery, resolution, exact fetch, and operational endpoints. Those requests flow into core services that implement immutable catalog behavior, lifecycle governance, dependency declaration reads, and audit recording. Persistence and audit adapters translate the core contracts into relational reads and writes over the registry store, which holds versions, normalized metadata, immutable bundle artifacts, search-facing projections, and audit history.

The main boundary is between authoritative registry data and downstream execution decisions. The registry publishes and serves immutable skill records and authored dependency selectors, while resolver or client components remain responsible for interpreting intent, selecting candidates, solving full dependency graphs, and producing execution plans.

- Interface layer: FastAPI endpoints for publish, discovery, exact reads, lifecycle updates, health, readiness, and metrics.
- Core services: skill-domain workflows for registry writes, discovery candidate generation, exact metadata/content access, dependency reads, and governance.
- Persistence and storage: PostgreSQL-backed adapters and models for immutable artifacts, provenance snapshots, search projections, and audit trails.
- Operations: observability components expose service health, structured logs, metrics, and readiness signals.

Canonical contract and boundary details live in [`docs/reference/api-contract.md`](docs/reference/api-contract.md) and [`docs/architecture/server-resolver-boundary.md`](docs/architecture/server-resolver-boundary.md).

## Route Surface

The current public HTTP baseline is:

- `GET /healthz`
- `GET /readyz`
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
uv sync --extra dev
make run-dev
```

`make run-dev` bootstraps the Docker stack with `APP_ENV=dev` and seeds demo data. Use `make run-prod` for the production-like variant with `APP_ENV=prod` and no demo seed. Telemetry is shipped to Grafana Cloud over OTLP/HTTP when `OTEL_ENABLED=true`; see [`docs/reference/observability-grafana-cloud.md`](docs/reference/observability-grafana-cloud.md).

Integration tests use a separate PostgreSQL container on `127.0.0.1:5433` so the test cycle never resets the local app database on `127.0.0.1:5432`. The default test URL is `postgresql+psycopg://postgres:postgres@127.0.0.1:5433/aptitude_test`.

```bash
make test
```

Docker quick start:

- `server` waits for `migrate`, so every stack run applies the latest Alembic schema before the API starts.

### Dev Run

Run the registry server with `APP_ENV=dev` and demo data.

```bash
make run-dev
```

### Prod Run

Run the production-like stack with no demo seed.

```bash
make run-prod
```

Teardown:

```bash
docker compose down
```

Other public commands:

```bash
make quality
make format
make build
```

Local URLs:

- API: `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`
- Grafana dashboard: `http://127.0.0.1:3000`

For the full setup flow, verification commands, and troubleshooting entrypoints, use [`docs/contributors/development-setup.md`](docs/contributors/development-setup.md) and [`docs/reference/operations/README.md`](docs/reference/operations/README.md).

## Documentation

- [`docs/README.md`](docs/README.md): documentation index and reading routes
- [`docs/architecture/README.md`](docs/architecture/README.md): canonical architecture reading order
- [`docs/reference/api-contract.md`](docs/reference/api-contract.md): canonical HTTP contract
- [`docs/architecture/server-resolver-boundary.md`](docs/architecture/server-resolver-boundary.md): registry vs resolver boundary
- [`docs/contributors/README.md`](docs/contributors/README.md): contributor workflow docs
- [`docs/reference/README.md`](docs/reference/README.md): stable technical reference
- [`docs/roadmap/README.md`](docs/roadmap/README.md): forward-looking technical direction
- [`.agents/README.md`](.agents/README.md): agent-facing operating context

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/y0ncha/aptitude-server)

Development database storage uses the external volume `aptitude-local_aptitude-postgres-data`, which Compose shutdown preserves. `make run-dev` and `make run-prod` create it if missing; direct Compose startup requires provisioning it first. Tests use the separate `aptitude-tests` project in `docker-compose.test.yml` with disposable PostgreSQL data in tmpfs. `make _test-db-down` cleans up only that test project.
