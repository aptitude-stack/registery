# Metrics and Scrape Failures

## Symptoms

- `/metrics` is unreachable
- Prometheus target is down
- Grafana panels show no data
- Baseline HTTP panels are empty even though the local stack is healthy
- Dependency readiness stays blank after the observability profile starts

## Checks

1. Probe `GET /metrics` directly from the server container or host.
2. Probe `GET /readyz` and confirm it returns `200`; the local observability profile uses readiness, not liveness, to initialize the readiness gauge.
3. Validate Prometheus config with `promtool check config`.
4. Confirm Prometheus can resolve `server:8000` inside the compose network.

## Actions

1. Restart the server container if `/metrics` is failing due to startup or readiness issues.
2. Fix broken scrape config, alert rules, or dashboard provisioning files.
3. Confirm the observability profile is running with `docker compose --profile observability ps`.
4. If only route-specific registry panels are empty, exercise the matching publish, discovery, resolution, metadata, content, or lifecycle route before treating it as a scrape failure.
