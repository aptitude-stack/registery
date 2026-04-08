# Discovery Latency Regression

## Symptoms

- p95 discovery latency exceeds the 250ms target
- `AptitudeServerDiscoveryP95LatencyHigh` alert fires

## Checks

1. Review the Grafana discovery latency panel.
2. Check `aptitude_registry_operation_duration_seconds{surface="discovery"}` and `aptitude_http_request_duration_seconds{route="/discovery"}`.
3. Correlate slow requests with JSON logs using `request_id`.

## Actions

1. Confirm PostgreSQL readiness and query performance.
2. Inspect recent index or query-plan changes.
3. Reduce concurrent load or revert the recent change if latency regressed after a deployment.
