# Plan 11 - Operability and Release Readiness

## Goal
Harden `aptitude-server` for repeatable deployment and reliable operation after the hard-cut read contract, PostgreSQL storage model, and governance behavior are finalized.

## Stack Alignment
- Runtime: Python 3.12+
- API and contracts: FastAPI + Pydantic v2
- Data layer: SQLAlchemy 2.0 + Alembic
- Observability foundation: Prometheus-compatible metrics and Grafana-consumable dashboards/rules kept optional at deployment time
- Quality gates: pytest, ruff, mypy, coverage thresholds

## Scope
- Add structured logs, correlation IDs, and audit trace stitching across:
  - publish
  - `POST /discovery`
  - `GET /resolution/{slug}/{version}`
  - `GET /skills/{slug}/versions/{version}`
  - `GET /skills/{slug}/versions/{version}/content`
  - lifecycle and governance paths
- Add metrics, dashboards, alerts, and SLO instrumentation for the final route set and PostgreSQL-only storage model.
- Make the observability foundation Prometheus-friendly without making Prometheus or Grafana mandatory release dependencies:
  - expose a scrape-friendly metrics endpoint for the finalized route set
  - use stable metric names, bounded labels, and histogram buckets that support SLO and alert-rule composition
  - define dashboards and alerts as code in a form Grafana can consume later, even if a Grafana deployment is not part of this milestone
- Add Docker packaging, startup/run instructions, and CI quality gates.
- Add runbooks for incidents on publish, discovery, resolution, exact metadata fetch, exact content fetch, lifecycle, and governance operations.
- Keep operability work internal to instrumentation, packaging, and runbooks; do not add new public registry-business endpoints, debug routes, or alternate discovery/resolution/fetch variants.
- Validate performance and reliability against the finalized API and storage shape from Plans 08-10 rather than against deleted routes or transitional storage semantics.

## Architecture Impact
- Adds deployment and observability infrastructure without reopening contract or storage decisions.
- Makes the final registry behavior measurable and supportable.
- Establishes a vendor-neutral observability contract that can plug into Prometheus/Grafana later without reworking core instrumentation.
- Prevents hardening work from preserving removed routes indirectly through dashboards, alerts, or runbooks.

## Deliverables
- Structured logging conventions and correlation ID propagation.
- Metrics endpoint plus counters, timers, and error-rate tracking for final registry operations.
- Dashboards and alerts for discovery, resolution, metadata fetch, content fetch, publish, and governance flows.
- Prometheus-compatible metric naming, label, and bucket conventions suitable for later recording rules and alert rules.
- Dashboard and alert definitions stored as code and shaped for later Grafana import/consumption, while remaining optional for this milestone's rollout.
- Dockerfile and local/prod run instructions.
- CI pipeline stages for unit, integration, lint, type-check, and coverage gates.
- Operational runbooks aligned to the hard-cut public contract and PostgreSQL-only runtime architecture.

## Acceptance Criteria
- End-to-end registry flows are observable through logs, metrics, and audit trace data.
- CI blocks merges on failing quality gates.
- Containerized startup and migration flow work against the final service shape.
- Discovery and immutable fetch SLO instrumentation align with the KPIs in `docs/prd.md`.
- Resolution and exact content fetch reliability instrumentation exist for the final contract.
- Metrics can be scraped by Prometheus-compatible collectors, and dashboard/alert artifacts are ready for optional Grafana adoption without changing application instrumentation.
- Operability work does not add public business-endpoint variants to support diagnostics or release operations.
- Runbooks and alerts assume PostgreSQL-only storage and never reference deleted route families or non-PostgreSQL artifact backends.
- Release readiness does not require a production Grafana or Prometheus deployment, but the instrumentation and artifacts must make that adoption low-friction later.

## Test Plan
- End-to-end integration test covering publish -> discovery -> resolution -> exact metadata fetch -> exact content fetch -> lifecycle update.
- CI smoke test in a containerized environment.
- Audit/log correlation test for a complete registry request path.
- Performance/load validation for discovery, resolution, and exact fetch on the finalized route set.
- Alerting and metrics sanity test for publish failures, exact-read failures, resolution failures, and discovery latency regression.
- Metrics exposition compatibility test validating scrapeability, stable label sets, and bucket coverage needed for Prometheus/Grafana-style alerting and dashboards.

## Plan 15 Follow-On Note (2026-03-19)
- Release-readiness acceptance in this milestone is still based on the lexical
  PostgreSQL discovery baseline finalized in Plans 08-10.
- Hybrid semantic retrieval, embedding-index lag monitoring, query-embedding
  latency budgets, and co-usage aggregate health are post-launch extensions
  owned by Plan 15 rather than additional release gates for this milestone.
- If Plan 15 is implemented later, its metrics, alerts, dashboards, and runbook
  additions should extend this observability foundation without changing the
  frozen public route set or reopening lexical-baseline release criteria.
- If Prometheus/Grafana are adopted later, Plan 15 should reuse the metric and
  dashboard contracts defined here instead of introducing a parallel
  observability vocabulary.

## Plan 11 Loki Addendum (2026-03-21)
- This milestone now explicitly includes Grafana Loki log tracking alongside
  Prometheus-compatible metrics and Grafana-consumable dashboards/alerts.
- Grafana remains the dashboard and query surface; Grafana Loki is the optional
  log storage/query backend for structured application and audit-log tracking.
- Loki adoption remains optional for release readiness. The application-side
  contract is still structured logs, correlation IDs, audit trace stitching,
  and bounded fields/labels that can be shipped into Grafana Loki later
  without changing core logging behavior.
- Scope is extended to define Loki-ready log schema, stream/label conventions,
  and optional log-exploration assets for publish, discovery, resolution,
  immutable metadata fetch, immutable content fetch, lifecycle, and governance
  paths.
- Deliverables now also include Grafana Loki ingestion/query conventions and
  any optional provisioning artifacts needed to make local or later production
  adoption low-friction without making Loki a mandatory runtime dependency.
- Acceptance for this milestone now includes end-to-end registry logs carrying
  stable correlation data and bounded structured fields suitable for Grafana
  Loki queries, while still forbidding observability-only public business
  endpoints.
- Test planning now also includes log-shape validation for structured JSON
  output, correlation propagation, bounded log labels/fields, and Grafana Loki
  ingestion compatibility assumptions.
- If Plan 15 is implemented later, its semantic-discovery observability should
  reuse the log schema and Grafana Loki conventions introduced here instead of
  creating a parallel logging vocabulary.

## Plan Numbering Clarification (2026-04-25)
- The semantic-discovery work referenced in the historical Plan 15 follow-on
  notes is now tracked by Plan 18 after later roadmap reorganization.
- The enterprise control-plane direction formerly held in standalone Plan 15 is
  now embedded directly in `roadmap.md` as a strategic anchor, not as an
  implementation plan.
