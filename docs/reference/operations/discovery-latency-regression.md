# Discovery Latency Regression

## Symptoms

- p95 discovery latency exceeds the 250ms target

## Checks

1. Review the discovery latency panel in Grafana Cloud (Mimir data source).
2. Check `aptitude_registry_operation_duration_seconds{surface="discovery"}` and `aptitude_http_request_duration_seconds{route="/discovery"}` series.
3. Correlate slow requests with Loki logs using `request_id`, or pivot to Tempo via the `trace_id` field auto-injected by the OpenTelemetry logging instrumentation.

## Actions

1. Confirm PostgreSQL readiness and query performance.
2. Inspect recent index or query-plan changes — SQLAlchemy spans in Tempo include the executed statement.
3. Reduce concurrent load or revert the recent change if latency regressed after a deployment.
