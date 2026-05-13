# Observability via Grafana Cloud (OTLP/HTTP)

Canonical reference for shipping traces, logs, and metrics from the Aptitude
Registry FastAPI service to Grafana Cloud over OTLP/HTTP.

## Architecture

```text
                 +-------------------------+
                 |   FastAPI on Render     |
                 |   (uv sync --extra otel)|
                 |                         |
                 |  configure_otel(...)    |
                 |    TracerProvider ---> |---+
                 |    LoggerProvider ---> |   | OTLP/HTTP
                 |    MeterProvider  ---> |   | (auth: Basic <base64(id:token)>)
                 +-------------------------+   |
                                               v
                              +----------------------------+
                              |  Grafana Cloud OTLP gateway |
                              |  https://otlp-gateway-      |
                              |  <region>.grafana.net/otlp  |
                              +-------------+--------------+
                                            |
                          +-----------------+-------------------+
                          |                 |                   |
                          v                 v                   v
                       Tempo             Loki                Mimir
                      (traces)          (logs)             (metrics)
```

The Render service uses Render's native Python runtime; there is no
in-cluster collector. Neon Postgres surfaces its own per-database metrics in
the Neon Console (separate UI, not unified with Grafana Cloud on the free
tier). Database-level visibility from the application side comes from
SQLAlchemy and psycopg auto-instrumentation, which include
`db.statement`, span timings, and the `application_name` set on each Neon
connection.

## Environment variables

The application reads `OTEL_ENABLED` and `OTEL_SDK_DISABLED` directly. All other
knobs are standard OpenTelemetry env vars consumed by the SDK.

| Variable | Purpose |
| --- | --- |
| `OTEL_ENABLED` | Aptitude-specific gate. When `false` (default), OTel is a no-op and the process logs to stdout only. |
| `OTEL_SDK_DISABLED` | Standard OTel env var. When `true`, the SDK skips initialization even if `OTEL_ENABLED=true`. Useful for emergency disable without redeploy. |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | Always `http/protobuf` for the Grafana Cloud OTLP gateway. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Grafana Cloud OTLP gateway URL for the stack region, e.g. `https://otlp-gateway-prod-eu-west-2.grafana.net/otlp`. |
| `OTEL_EXPORTER_OTLP_HEADERS` | `Authorization=Basic <base64(instance_id:access_policy_token)>`. URL-encode the space (`%20`). |
| `OTEL_RESOURCE_ATTRIBUTES` | Comma-separated `key=value` pairs added to every signal. Recommended: `service.namespace=aptitude,deployment.environment.name=prod`. |
| `OTEL_TRACES_SAMPLER` | Recommended `parentbased_traceidratio` to keep span volume inside the free-tier 50 GB/month trace cap. |
| `OTEL_TRACES_SAMPLER_ARG` | Sampling ratio. `0.1` (10%) is a safe production starting point. Local/staging can use `1.0`. |
| `OTEL_LOG_LEVEL` | Controls the OTel SDK's own internal log noise; leave unset unless debugging. |

`service.name` and `service.version` are set programmatically from
`Settings.app_name` and the installed package version, so do not pass them
through `OTEL_RESOURCE_ATTRIBUTES`.

## Grafana Cloud Access Policy token scopes

Create a single Access Policy token (Grafana Cloud → Access Policies → Create
Access Policy) with these scopes and use it everywhere `OTEL_EXPORTER_OTLP_HEADERS`
is referenced:

- `metrics:write`
- `logs:write`
- `traces:write`

`metrics:read` / `logs:read` / `traces:read` are not needed by the app; they
belong on the dashboards/alerts user, not on the export token.

The "Send Data → OpenTelemetry → Configure with token" panel in Grafana Cloud
emits both the OTLP endpoint URL and the pre-encoded `Authorization` header
for you. Treat the resulting header as a secret; rotate it via Grafana Cloud
without code changes (the new header takes effect at next process boot).

## Free-tier limits worth tracking

The Pro Free plan caps:

- 10,000 active metric series
- 50 GB of logs ingest per month
- 50 GB of traces ingest per month
- 14 days of retention across logs, traces, and metrics

Sampling settings in this repo are tuned to stay comfortably inside those
limits at expected production traffic. If sustained traffic increases, lower
`OTEL_TRACES_SAMPLER_ARG` or move to a paid plan rather than dropping
instrumentation.

## How signals are produced

`app/observability/telemetry.py::configure_otel` is the single entry point.
It is called from `app/main.py` lifespan startup, after settings are loaded
and logging is configured.

| Signal | Source | Notes |
| --- | --- | --- |
| Traces | `FastAPIInstrumentor.instrument_app(app, excluded_urls="/healthz,/readyz")`, plus `SQLAlchemyInstrumentor` (with `enable_commenter=True`) and `PsycopgInstrumentor` | Probe routes are excluded so the trace volume reflects real user traffic. The SQL commenter injects `traceparent` into emitted SQL, which surfaces in PostgreSQL server logs and lets you correlate slow queries to traces. |
| Logs | `LoggingInstrumentor().instrument(set_logging_format=False)` plus a global `LoggerProvider` with `BatchLogRecordProcessor(OTLPLogExporter())` | Application logs continue to write structured JSON to stdout (which Render captures) and additionally export to Loki. `trace_id` and `span_id` are auto-injected onto log records. |
| Metrics | OpenTelemetry Meter API instruments declared in `app/observability/metrics.py` (`aptitude_http_requests_total`, `aptitude_http_request_duration_seconds`, `aptitude_registry_operation_total`, `aptitude_registry_operation_duration_seconds`, `aptitude_readiness_status`, `aptitude_semantic_discovery_failures_total`) | Recorded by FastAPI request middleware, readiness probes, and semantic discovery fallback handling. Exported every minute via `PeriodicExportingMetricReader`. |
| Semantic fallback | `aptitude_semantic_discovery_failures_total` | Counts provider or repository failures that degraded semantic discovery to lexical fallback. Alert on sustained non-zero values before moving from `shadow` to `hybrid`. |

The legacy Prometheus `/metrics` exposition endpoint and `prometheus-client`
dependency were removed when this migration landed; metric names and label
shapes were preserved so existing Grafana panels keep working.

## Adding a new instrument

```python
from opentelemetry import metrics as otel_metrics

_meter = otel_metrics.get_meter("aptitude.registry")

PUBLISH_BUNDLE_BYTES = _meter.create_histogram(
    name="aptitude_publish_bundle_bytes",
    unit="By",
    description="Size of stored skill bundles in bytes.",
    explicit_bucket_boundaries_advisory=[1_024, 16_384, 262_144, 4_194_304],
)

def record_bundle_size(*, byte_count: int) -> None:
    PUBLISH_BUNDLE_BYTES.record(byte_count, attributes={"surface": "publish"})
```

Keep the `aptitude_*` prefix and reuse existing label keys (`surface`,
`route`, `outcome`, `status_class`) so existing dashboards keep being useful.

## Local development

`OTEL_ENABLED=false` (the default) keeps the local stack lean: structured
JSON logs to stdout, no OTLP traffic. To exercise the same Grafana Cloud
path locally, copy the production env vars into your local dotenv and
set `OTEL_RESOURCE_ATTRIBUTES=deployment.environment.name=dev` so the
signals stay distinguishable from production.

The previous `grafana/otel-lgtm` Docker stack and `ops/monitoring/`
provisioning assets have been removed. There is no longer a local Grafana,
Prometheus, or Loki to scrape.

## Troubleshooting

| Symptom | First check |
| --- | --- |
| Service refuses to boot with `ValueError: OTEL_ENABLED=true requires OTEL_EXPORTER_OTLP_ENDPOINT` | Settings validator caught a missing endpoint in prod. Either set the endpoint or unset `OTEL_ENABLED`. |
| No traces in Tempo, but `/healthz` looks fine | Hit a non-probe route. `/healthz` and `/readyz` are excluded from FastAPI auto-instrumentation. |
| No logs in Loki, but logs appear in Render | The Access Policy token may be missing `logs:write`. Recreate the token with all three write scopes. |
| `Transient error ... Connection refused` warnings on shutdown | Normal in tests with no real OTLP receiver. In production, check that the OTLP endpoint URL and auth header are correct. |
| Spans appear but database queries do not | `SQLAlchemyInstrumentor.instrument(engine=...)` runs from `service_container.build_service_container`. Confirm `OTEL_ENABLED=true` was set at process boot, not after. |
| Logs in Loki are missing `trace_id` | `LoggingInstrumentor` was not loaded. Confirm `--extra otel` is in the Render Build Command. |
