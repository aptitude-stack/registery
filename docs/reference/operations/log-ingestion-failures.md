# Log Ingestion Failures

## Symptoms

- Grafana logs panels are empty
- Loki is reachable but queries return no application logs
- The embedded OpenTelemetry Collector is down or not ingesting the app log file
- A known `X-Request-ID` does not appear in Loki after a request
- Grafana shows raw JSON blobs or duplicated request lines instead of one compact app log per request

## Checks

1. Confirm the observability profile is running with `docker compose --profile observability ps`.
2. Probe Loki directly: `curl http://127.0.0.1:3100/ready`.
3. Probe Prometheus targets and confirm `otelcol` and `loki` are up: `curl http://127.0.0.1:9090/api/v1/targets`.
4. Hit the API with a known request ID:

   ```bash
   curl -H 'X-Request-ID: runbook-loki-check' http://127.0.0.1:8000/healthz
   ```

5. Query Loki for that value:

   ```bash
   curl --get \
     --data-urlencode 'query={service_name="Aptitude Registry"} |= "runbook-loki-check"' \
     http://127.0.0.1:3100/loki/api/v1/query
   ```

## Actions

1. If the collector is not healthy, restart the observability stack and re-check the shared `aptitude-logs` volume mounts on `server` and `observability`.
2. If Loki is down, restart the single `observability` container and verify the bundled LGTM services are healthy.
3. If the API is healthy but no logs arrive, confirm `LOG_FILE_PATH=/var/log/aptitude/app.jsonl` is set on the `server` container.
4. If Loki shows duplicate request lines, confirm the dashboard is rendering the structured `app.main` log rather than a mixed access-log view and that `uvicorn.access` is not being written into the JSON file sink.
5. If the file sink exists but Loki queries stay empty, inspect the collector configuration mounted at `ops/monitoring/otel-lgtm/otelcol-config.yaml` and verify the app log file is readable inside the `observability` container.
6. Use the same `X-Request-ID` across API probes, Grafana searches, and audit lookups to confirm whether the failure is in logging, shipping, or persistence correlation.
