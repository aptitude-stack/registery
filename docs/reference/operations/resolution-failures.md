# Resolution Failures

## Symptoms

- `GET /resolution/{slug}/{version}` returns unexpected `404`, `403`, or `5xx`
- resolution client-error or server-error counters rise

## Checks

1. Inspect logs by `request_id`.
2. Check audit rows for `skill.version_resolution_read` or `skill.version_exact_read_denied`.
3. Confirm the target coordinate exists and lifecycle policy allows the read.

## Actions

1. If `404`, validate the exact `slug@version`.
2. If `403`, confirm lifecycle state and caller scopes.
3. If `5xx`, inspect persistence errors and database health.
