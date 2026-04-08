# Publish Failures

## Symptoms

- `POST /skills/{slug}` returns `4xx` or `5xx`
- `aptitude_registry_operation_total{surface="publish",outcome!="success"}` increases

## Checks

1. Inspect app logs for the request's `X-Request-ID`.
2. Check `skill.version_publish_denied` or `skill.version_published` audit rows for the same `request_id`.
3. Confirm PostgreSQL readiness through `/readyz` and `aptitude_readiness_status`.

## Actions

1. For `401` or `403`, verify the caller token scopes and trust-tier policy requirements.
2. For `409`, verify whether the `slug@version` was already published.
3. For `500`, inspect database health, recent migrations, and persistence errors in logs.
