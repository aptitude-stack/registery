# Milestone 11 Changelog - Operability and Release Readiness

> **Superseded.** The local `grafana/otel-lgtm` stack, the `ops/monitoring/`
> assets, the optional file log sink, and the `GET /metrics` endpoint
> documented below have been removed. Telemetry now flows directly from the
> running FastAPI process to Grafana Cloud over OTLP/HTTP. See
> [`docs/reference/observability-grafana-cloud.md`](../reference/observability-grafana-cloud.md)
> for the current shape. This file is kept as a historical record of how
> milestone 11 originally landed.

This changelog documents implementation of [.agents/plans/11-operability-and-release-readiness.md](../../.agents/plans/11-operability-and-release-readiness.md).

The milestone hardens the frozen registry surface with request-scoped observability, Prometheus-compatible metrics, optional local Prometheus/Grafana/Loki assets, containerized smoke paths, and incident runbooks. It does that without reopening the public registry-business route families finalized in Plans 09-10; the only new route is operational-only [`GET /metrics`](../project/api-contract.md).

This branch also folds the skill-catalog domain services that emit those observability signals under [`app/core/skills/`](../../app/core/skills/README.md). That is a packaging and boundary cleanup, not a new runtime capability: route behavior, metrics names, and release-readiness expectations stay the same, but the milestone docs now point at the current bounded-context layout instead of the retired flat `app.core.skill_*` modules.

## Scope Delivered

- Request correlation now starts in shared HTTP middleware, propagates through response headers, structured logs, and audit payloads, and is exercised by explicit operability tests: [app/main.py](../../app/main.py), [app/observability/context.py](../../app/observability/context.py), [app/observability/logging.py](../../app/observability/logging.py), [app/core/audit_events.py](../../app/core/audit_events.py), [tests/integration/test_operability.py](../../tests/integration/test_operability.py), [tests/unit/test_audit_events.py](../../tests/unit/test_audit_events.py), [tests/unit/test_logging.py](../../tests/unit/test_logging.py).
- The service now exposes bounded Prometheus-compatible HTTP, registry-surface, and readiness metrics, with readiness updates wired into `/readyz` and operational exposition wired into `/metrics`: [app/observability/metrics.py](../../app/observability/metrics.py), [app/interface/api/health.py](../../app/interface/api/health.py), [app/interface/api/operability.py](../../app/interface/api/operability.py), [app/main.py](../../app/main.py), [pyproject.toml](../../pyproject.toml), [tests/unit/test_observability.py](../../tests/unit/test_observability.py), [tests/integration/test_operability.py](../../tests/integration/test_operability.py).
- Prometheus scrape config, alert rules, Grafana provisioning, and a checked-in dashboard now exist as code, while remaining optional deployment-time assets rather than runtime requirements of the API itself: [ops/monitoring/prometheus/prometheus.yml](../../ops/monitoring/prometheus/prometheus.yml), [ops/monitoring/prometheus/alerts.yml](../../ops/monitoring/prometheus/alerts.yml), [ops/monitoring/grafana/provisioning/datasources/prometheus.yml](../../ops/monitoring/grafana/provisioning/datasources/prometheus.yml), [ops/monitoring/grafana/provisioning/dashboards/dashboards.yml](../../ops/monitoring/grafana/provisioning/dashboards/dashboards.yml), [ops/monitoring/grafana/dashboards/aptitude-server-operability.json](../../ops/monitoring/grafana/dashboards/aptitude-server-operability.json), [tests/unit/test_operability_assets.py](../../tests/unit/test_operability_assets.py).
- Local log shipping is now part of the checked-in observability stack: the API can duplicate structured JSON logs to an optional file sink, the `grafana/otel-lgtm` container's embedded OpenTelemetry Collector tails the shared volume, Loki stores the logs, and Grafana gets a dedicated logs dashboard plus a provisioned Loki datasource: [app/observability/logging.py](../../app/observability/logging.py), [app/main.py](../../app/main.py), [docker-compose.yml](../../docker-compose.yml), [ops/monitoring/otel-lgtm/otelcol-config.yaml](../../ops/monitoring/otel-lgtm/otelcol-config.yaml), [ops/monitoring/grafana/provisioning/datasources/loki.yml](../../ops/monitoring/grafana/provisioning/datasources/loki.yml), [ops/monitoring/grafana/dashboards/aptitude-server-logs.json](../../ops/monitoring/grafana/dashboards/aptitude-server-logs.json), [tests/unit/test_logging.py](../../tests/unit/test_logging.py), [tests/unit/test_operability_assets.py](../../tests/unit/test_operability_assets.py).
- Local release-readiness paths now include explicit compose targets for database, one-shot migration, app, Prometheus, and Grafana startup plus container smoke commands documented for developers: [docker-compose.yml](../../docker-compose.yml), [Makefile](../../Makefile), [README.md](../../README.md), [docs/guides/setup-dev.md](../../docs/guides/setup-dev.md).
- CI now treats operability as part of the release gate by running lint, format, mypy, unit tests, integration tests, Prometheus config validation, compose validation, and Docker smoke flows on both `dev` and `master` pull requests: [.github/workflows/dev-ci.yml](../../.github/workflows/dev-ci.yml), [.github/workflows/main-ci.yml](../../.github/workflows/main-ci.yml), [docker-compose.yml](../../docker-compose.yml), [Makefile](../../Makefile).
- Contract docs and runbooks are now aligned to the frozen route set and the new observability vocabulary so operators troubleshoot the real API shape rather than deleted transition routes: [docs/project/api-contract.md](../project/api-contract.md), [docs/runbooks/README.md](../runbooks/README.md), [docs/runbooks/publish-failures.md](../runbooks/publish-failures.md), [docs/runbooks/discovery-latency-regression.md](../runbooks/discovery-latency-regression.md), [docs/runbooks/resolution-failures.md](../runbooks/resolution-failures.md), [docs/runbooks/fetch-failures.md](../runbooks/fetch-failures.md), [docs/runbooks/governance-denials.md](../runbooks/governance-denials.md), [docs/runbooks/metrics-scrape-failures.md](../runbooks/metrics-scrape-failures.md), [tests/unit/test_public_contract_docs.py](../../tests/unit/test_public_contract_docs.py), [tests/unit/test_registry_api_boundary.py](../../tests/unit/test_registry_api_boundary.py).
- The core skill-domain services that sit behind publish, discovery, resolution, and exact fetch are now grouped under one internal package, with dependency wiring, interface imports, persistence adapters, and architecture docs updated to reference the same bounded context consistently: [app/core/skills/README.md](../../app/core/skills/README.md), [app/core/dependencies.py](../../app/core/dependencies.py), [app/service_container.py](../../app/service_container.py), [app/interface/api/discovery.py](../../app/interface/api/discovery.py), [app/interface/api/fetch.py](../../app/interface/api/fetch.py), [app/interface/api/resolution.py](../../app/interface/api/resolution.py), [app/interface/api/skills.py](../../app/interface/api/skills.py), [app/persistence/skill_registry_repository_writes.py](../../app/persistence/skill_registry_repository_writes.py), [docs/project/api-contract.md](../project/api-contract.md).

## Architecture Snapshot

```mermaid
flowchart LR
    Client["Client / Probe / Operator"] --> Middleware["FastAPI observability middleware"]
    Middleware --> Routes["Frozen API routes + GET /metrics"]
    Routes --> Services["app.core.skills package"]
    Services --> Repo["SQLAlchemy repositories + audit recorder"]
    Repo --> PG["PostgreSQL"]

    Middleware --> Context["RequestContext"]
    Context --> Logs["Structured logs"]
    Logs --> FileSink["Optional JSON file sink"]
    Context --> Audit["Audit payload request_id"]
    Middleware --> Metrics["Prometheus registry"]
    Routes --> Metrics
    FileSink --> OTelCol["otel-lgtm OpenTelemetry Collector"]
    OTelCol --> Loki["otel-lgtm Loki"]
    Prom["otel-lgtm Prometheus"] -->|scrapes /metrics| Metrics
    Prom["otel-lgtm Prometheus"] -->|scrapes self-metrics| Loki
    Prom["otel-lgtm Prometheus"] -->|scrapes self-metrics| OTelCol
    Prom --> Alerts["Alert rules"]
    Prom --> Grafana["otel-lgtm Grafana dashboards"]
    Loki --> Grafana
```

Why this shape:
- Observability stays as shared middleware and a small runtime context object instead of being duplicated across route handlers, which keeps the frozen publish/discovery/resolution/fetch/lifecycle surfaces instrumented consistently: [app/main.py](../../app/main.py), [app/observability/context.py](../../app/observability/context.py).
- Prometheus and Grafana remain optional consumers of the in-process metrics contract, so the application can expose stable telemetry without taking a hard runtime dependency on either tool: [app/observability/metrics.py](../../app/observability/metrics.py), [app/interface/api/operability.py](../../app/interface/api/operability.py), [ops/monitoring/prometheus/prometheus.yml](../../ops/monitoring/prometheus/prometheus.yml), [ops/monitoring/grafana/dashboards/aptitude-server-operability.json](../../ops/monitoring/grafana/dashboards/aptitude-server-operability.json).
- The skill-domain regrouping stays inside `app.core` rather than creating a new architecture layer. That keeps the layering contract unchanged while making the publish/discovery/fetch/resolution cluster easier to reason about as one bounded context: [app/README.md](../../app/README.md), [app/core/README.md](../../app/core/README.md), [app/core/skills/README.md](../../app/core/skills/README.md), [app/interface/README.md](../../app/interface/README.md), [app/persistence/README.md](../../app/persistence/README.md).

## Runtime Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant A as FastAPI middleware
    participant S as Route + app.core.skills service
    participant R as Repository / audit
    participant M as Metrics registry

    C->>A: Request (+ optional X-Request-ID)
    A->>A: Set request context and start timer
    A->>S: Dispatch route
    S->>R: Registry work + audit event build
    R-->>S: Result
    S-->>A: Response
    A->>M: observe_http_request()
    A->>A: Emit structured log with request context
    A-->>C: Response + X-Request-ID
```

## Design Notes

- `GET /metrics` is deliberately documented as an operational endpoint, not a new registry-business route family. That is the right boundary: scraping is necessary for operability, but it should not reopen product-contract churn around publish, discovery, resolution, or exact fetch: [docs/project/api-contract.md](../project/api-contract.md), [app/interface/api/operability.py](../../app/interface/api/operability.py).
- Metric labels are intentionally bounded to route templates, HTTP status classes, and named registry surfaces. That avoids the usual high-cardinality mistake of emitting raw slugs, versions, or request identifiers into Prometheus series: [app/observability/metrics.py](../../app/observability/metrics.py), [ops/monitoring/prometheus/alerts.yml](../../ops/monitoring/prometheus/alerts.yml).
- The branch chooses request correlation over a heavier tracing system. `X-Request-ID` is enough here because the service is still a single-process boundary with one primary datastore; logs, metrics, and audit rows can be stitched together without introducing tracing infrastructure theater: [app/main.py](../../app/main.py), [app/observability/logging.py](../../app/observability/logging.py), [app/core/audit_events.py](../../app/core/audit_events.py).
- Logging stays deterministic across app, uvicorn, SQLAlchemy, and psycopg, with `LOG_FORMAT=auto` selecting pretty local logs but JSON in containers and non-interactive environments. That keeps local development readable without sacrificing machine-readable production logs: [app/observability/logging.py](../../app/observability/logging.py), [app/core/settings.py](../../app/core/settings.py), [tests/unit/test_logging.py](../../tests/unit/test_logging.py).
- The Loki path stays local-only and file-based on purpose. Sharing one JSON log volume between the API and the `otel-lgtm` collector is less brittle than Docker-daemon scraping, and it keeps production logging choices open for later GCP deployment work: [app/observability/logging.py](../../app/observability/logging.py), [docker-compose.yml](../../docker-compose.yml), [ops/monitoring/otel-lgtm/otelcol-config.yaml](../../ops/monitoring/otel-lgtm/otelcol-config.yaml), [docs/runbooks/log-ingestion-failures.md](../runbooks/log-ingestion-failures.md).
- Compose-based release-readiness keeps migrations explicit through the one-shot `migrate` service instead of burying schema changes inside API startup. That is safer operationally and easier to reason about in CI and local smoke tests: [docker-compose.yml](../../docker-compose.yml), [Makefile](../../Makefile), [.github/workflows/dev-ci.yml](../../.github/workflows/dev-ci.yml), [.github/workflows/main-ci.yml](../../.github/workflows/main-ci.yml).
- Grouping skill-domain services under `app/core/skills` is the correct cleanup because the code was already behaving like one bounded context. The alternative, leaving flat `app.core.skill_*` modules scattered around, keeps import churn and docs drift alive without buying any runtime simplicity: [app/core/skills/discovery.py](../../app/core/skills/discovery.py), [app/core/skills/fetch.py](../../app/core/skills/fetch.py), [app/core/skills/registry.py](../../app/core/skills/registry.py), [app/core/skills/resolution.py](../../app/core/skills/resolution.py), [app/core/skills/search.py](../../app/core/skills/search.py), [app/core/skills/exact_read.py](../../app/core/skills/exact_read.py).
- No SQL tables or Alembic migrations were added in this milestone. The important contract change is operational vocabulary and support assets, not persistence shape; pretending otherwise would misstate what the branch actually delivers: [app/observability/metrics.py](../../app/observability/metrics.py), [docs/runbooks/README.md](../runbooks/README.md).

## Schema Reference

Source: [app/observability/metrics.py](../../app/observability/metrics.py), [app/observability/context.py](../../app/observability/context.py), [ops/monitoring/prometheus/alerts.yml](../../ops/monitoring/prometheus/alerts.yml).

### `Prometheus Metric Surface`

| Series | Type | Labels / Dimensions | Role |
| --- | --- | --- | --- |
| `aptitude_http_requests_total` | `Counter` | `method`, `route`, `status_class` | Counts bounded HTTP traffic by route template and coarse status family so alert math and traffic baselines stay stable across concrete slugs and versions. |
| `aptitude_http_request_duration_seconds` | `Histogram` | `method`, `route` | Records route-level latency with fixed buckets suitable for SLO-style p95 calculations without per-request cardinality blowups. |
| `aptitude_registry_operation_total` | `Counter` | `surface`, `outcome` | Tracks outcome rates for the business surfaces that matter operationally: publish, discovery, resolution, metadata, content, and lifecycle. |
| `aptitude_registry_operation_duration_seconds` | `Histogram` | `surface` | Measures latency at the named registry-surface layer so dashboards and alerts can speak in domain terms rather than only raw routes. |
| `aptitude_readiness_status` | `Gauge` | `dependency` | Publishes readiness of critical dependencies, currently the PostgreSQL database, so `/readyz` state is externally observable and alertable. |

### `Request Correlation Context`

| Field | Type | Propagation Point | Role |
| --- | --- | --- | --- |
| `request_id` | `str \| None` | Middleware, response headers, logs, audit payloads | Serves as the stitch key between client-visible responses, structured logs, and persisted audit rows. |
| `http_method` | `str \| None` | Middleware -> log context | Captures the normalized request verb for readable logs and bounded HTTP metric dimensions. |
| `http_route` | `str \| None` | Route template resolution | Stores the template path rather than the concrete URL so observability data stays aggregation-friendly. |
| `status_code` | `int \| None` | Response / exception handling | Carries final response outcome into logs and supports mapping to success, client-error, and server-error metrics. |
| `duration_ms` | `float \| None` | Middleware timer | Adds human-readable request latency to logs while the histogram stores the same timing in Prometheus-native seconds. |

### `Local Log Pipeline`

| Component | Interface | Role |
| --- | --- | --- |
| `LOG_FILE_PATH` | Optional env var on `server` | Enables JSON log duplication to `/var/log/aptitude/app.jsonl` without changing stdout logging behavior. |
| Shared `aptitude-logs` volume | Docker named volume | Carries the log file from the API container to the local shipper without depending on Docker daemon log internals. |
| `otel-lgtm` OpenTelemetry Collector | `ops/monitoring/otel-lgtm/otelcol-config.yaml` | Tails only the app log file and forwards it into the bundled Loki instance without requiring a separate shipper container. |
| `otel-lgtm` Loki | Bundled service in `grafana/otel-lgtm` | Stores local log streams for Grafana queries and smoke-test verification. |
| Grafana Loki datasource + logs dashboard | Provisioned datasource/dashboard | Gives operators a direct way to inspect recent logs, failure logs, and `request_id`-based traces alongside the metrics dashboard. |

### `Core Skill-Domain Package Surface`

| Module | Responsibility | Role |
| --- | --- | --- |
| `discovery.py` | Body-based candidate discovery facade | Keeps the public discovery route thin while routing search-backed candidate generation through the same bounded core package that operability instrumentation already measures. |
| `search.py` | Advisory search query/result modeling and execution | Owns the search-shaped read surface that feeds discovery metrics and audit events without pushing ranking behavior into routers. |
| `fetch.py` | Exact immutable metadata and markdown reads | Preserves the exact-read path whose latency, status, and audit stitching are part of the release-readiness contract. |
| `resolution.py` | Direct authored dependency reads | Keeps dependency metadata reads separate from resolver-side solving while still participating in shared observability and governance hooks. |
| `registry.py` | Immutable publish and lifecycle mutation orchestration | Holds the write path that emits transactional audit events and registry-operation metrics for publish and status changes. |
| `exact_read.py` | Shared exact-read governance and audit helper | Centralizes the exact-read enforcement used by fetch and resolution so logs, metrics-adjacent audit data, and policy behavior stay consistent. |
| `models.py` / `projections.py` | Shared skill-domain types and stored-to-domain projections | Provide one stable import surface for interface, persistence, and tests after the package regrouping, which reduces path drift without changing behavior. |

## Verification Notes

- Unit coverage now verifies request-context helpers, logging format selection and enrichment, audit-event request ID stitching, metrics asset presence, contract-doc freeze rules, and route exposure for `/metrics`: [tests/unit/test_observability.py](../../tests/unit/test_observability.py), [tests/unit/test_logging.py](../../tests/unit/test_logging.py), [tests/unit/test_audit_events.py](../../tests/unit/test_audit_events.py), [tests/unit/test_operability_assets.py](../../tests/unit/test_operability_assets.py), [tests/unit/test_public_contract_docs.py](../../tests/unit/test_public_contract_docs.py), [tests/unit/test_registry_api_boundary.py](../../tests/unit/test_registry_api_boundary.py), [tests/unit/test_main.py](../../tests/unit/test_main.py), [tests/unit/test_settings.py](../../tests/unit/test_settings.py).
- Integration coverage exercises the unauthenticated `/metrics` endpoint, response `X-Request-ID` echoing on success and failure paths, and publish-flow correlation into persisted audit rows plus metrics output: [tests/integration/test_operability.py](../../tests/integration/test_operability.py).
- Import-path regression coverage now also asserts that the regrouped `app.core.skills` modules remain importable and that FastAPI dependency wiring still resolves the same service graph through the new package paths: [tests/unit/test_core_skills_package.py](../../tests/unit/test_core_skills_package.py), [tests/unit/test_dependencies.py](../../tests/unit/test_dependencies.py), [tests/unit/test_exact_read_support.py](../../tests/unit/test_exact_read_support.py), [tests/unit/test_skill_fetch_service.py](../../tests/unit/test_skill_fetch_service.py), [tests/unit/test_skill_registry_service.py](../../tests/unit/test_skill_registry_service.py), [tests/unit/test_skill_resolution_service.py](../../tests/unit/test_skill_resolution_service.py), [tests/unit/test_skill_version_projections.py](../../tests/unit/test_skill_version_projections.py).
- CI workflow definitions now encode the release gate directly: Ruff lint/format checks, mypy, unit tests, integration tests, Prometheus config validation with `promtool`, compose-profile validation, Docker image build, and container smoke hits against `/healthz`, `/readyz`, `/metrics`, Prometheus targets, Loki readiness, and a real `X-Request-ID` query round-tripped through Loki: [.github/workflows/dev-ci.yml](../../.github/workflows/dev-ci.yml), [.github/workflows/main-ci.yml](../../.github/workflows/main-ci.yml), [Makefile](../../Makefile).
