# Metadata and Content Fetch Failures

## Symptoms

- `GET /skills/{slug}`, `GET /skills/{slug}/{version}`, or `.../content` fails
- fetch latency/error panels spike

## Checks

1. Inspect the request's `X-Request-ID` in logs.
2. Compare metadata and content fetch counters and duration histograms.
3. Verify `ETag`, `Cache-Control`, and `Content-Length` behavior for successful reads.

## Actions

1. For `404`, confirm the immutable coordinate exists.
2. For `403`, check lifecycle visibility and caller scope.
3. For `5xx`, inspect content-row integrity and database availability.
