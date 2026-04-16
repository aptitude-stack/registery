# API Contract

> Status: canonical public HTTP contract for `Aptitude Registry`.

## Boundary

This API stays registry-first.

- Server-owned: immutable publish, candidate discovery, exact dependency reads, exact immutable fetch, lifecycle governance, and audit.
- Client-owned: prompt interpretation, reranking, final selection, dependency solving, lock generation, and execution planning.

Public routes:

- `GET /healthz`
- `GET /readyz`
- `GET /metrics`
- `POST /skills/{slug}`
- `POST /discovery`
- `GET /skills/{slug}`
- `GET /resolution/{slug}/{version}`
- `GET /skills/{slug}/{version}`
- `GET /skills/{slug}/{version}/content`
- `PATCH /skills/{slug}/{version}/status`

## Freeze Rule

- Identity reads stay on `GET /skills/{slug}`.
- Exact coordinate reads stay on:
  - `GET /skills/{slug}/{version}`
  - `GET /skills/{slug}/{version}/content`
- Discovery returns candidate slugs only.
- Resolution returns direct authored `depends_on` only.
- Exact fetch returns immutable metadata or the exact immutable bundle artifact for one coordinate.

## Publish

`POST /skills/{slug}` now uses `multipart/form-data`.

Required parts:

| Part | Content Type | Meaning |
| --- | --- | --- |
| `metadata` | `application/json` | Queryable metadata, governance, and relationships |
| `bundle` | `application/zstd` | Immutable `.tar.zst` skill artifact stored without unpacking |

The server validates the uploaded zip structure at publish time and then stores one immutable digest-addressed bundle per version.

Current enforced bundle limits:

- maximum upload size: `5 MiB`
- maximum archive file count: `200`
- maximum archive path length: `240` bytes

## Exact Metadata

Publish and exact metadata fetch return the same structured response shape:

```json
{
  "slug": "python.lint",
  "version": "1.2.3",
  "install_count": 42,
  "version_checksum": {"algorithm": "sha256", "digest": "..."},
  "content": {
    "checksum": {"algorithm": "sha256", "digest": "..."},
    "media_type": "application/zstd",
    "size_bytes": 1234
  },
  "metadata": {
    "name": "Python Lint",
    "description": "Linting skill",
    "tags": ["python", "lint"]
  },
  "lifecycle_status": "published",
  "trust_tier": "internal",
  "published_at": "2026-03-10T08:30:00Z"
}
```

`provenance` remains advisory publish-time metadata and stays queryable outside the bundle.

Checksum semantics:

- `content.checksum.digest` is the persisted `sha256` digest of the exact stored artifact bytes.
- `version_checksum.digest` is the persisted `sha256` digest of the canonical version payload, which includes the content digest plus metadata, governance, and authored relationships.

## Exact Content

`GET /skills/{slug}/{version}/content` returns the immutable stored artifact for one exact coordinate.

- Response media type: `application/zstd`
- Success headers:
  - `ETag`
  - `Cache-Control: public, immutable`
  - `Content-Length`

Rules:

- Exact read only, not search.
- Missing coordinates return `404`.
- Read policy matches the exact metadata route.
- Consumers must not assume markdown text from this route anymore.
- `ETag` mirrors the stored content checksum digest for the immutable artifact.

## Endpoint Summary

| Method | Path | Scope | Success | Notes |
| --- | --- | --- | --- | --- |
| `GET` | `/healthz` | none | `200` | Liveness probe |
| `GET` | `/readyz` | none | `200` or `503` | Dependency readiness probe |
| `GET` | `/metrics` | none | `200` | Prometheus-compatible operational metrics |
| `POST` | `/skills/{slug}` | `publish` | `201` | Publish one immutable `slug@version` via `multipart/form-data` |
| `POST` | `/discovery` | `read` | `200` | Returns ordered candidate `slug` values only |
| `GET` | `/skills/{slug}` | `read` | `200` | Returns visible immutable versions for one skill identity |
| `GET` | `/resolution/{slug}/{version}` | `read` | `200` | Returns direct authored `depends_on` only |
| `GET` | `/skills/{slug}/{version}` | `read` | `200` | Returns immutable metadata for one exact coordinate |
| `GET` | `/skills/{slug}/{version}/content` | `read` | `200` | Returns immutable `application/zstd` artifact with cache headers |
| `PATCH` | `/skills/{slug}/{version}/status` | `admin` | `200` | Transitions lifecycle state |
