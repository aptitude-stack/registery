# API Contract

> Status: canonical public HTTP contract for `Aptitude Registry`.
> For the broader docs map, use [docs/README.md](../README.md).

Human-readable summary of the public HTTP API implemented by `Aptitude Registry`.
For interactive local API docs, use `http://127.0.0.1:8000/docs`.

## Boundary

This API is intentionally registry-first.

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

This route set is the current public registry baseline.

- `GET /metrics` is an operational endpoint for Prometheus-compatible scraping and does not widen the frozen registry-business route families.
- Resolution remains a first-class public exact-read surface.
- Identity reads stay on `GET /skills/{slug}`, while exact coordinate reads stay on:
  - `GET /skills/{slug}/{version}`
  - `GET /skills/{slug}/{version}/content`
- Later milestones may refine payload fields, headers, and policy behavior inside this route set, but they should not reintroduce deleted route aliases.
- The server remains execution-agnostic: discovery returns candidate slugs, resolution returns direct authored `depends_on`, and exact fetch returns immutable metadata or markdown for one coordinate.

## Auth, Headers, And Errors

- `GET /healthz`, `GET /readyz`, and `GET /metrics` are unauthenticated.
- All other routes require `Authorization: Bearer <token>`.
- Clients may send `X-Request-ID` on any request.
- The server echoes `X-Request-ID` on every response so logs, metrics, and audit rows can be stitched together operationally.
- Required scopes:
  - `read`: discovery, resolution, fetch
  - `publish`: immutable publish
  - `admin`: lifecycle updates and admin-only governance behavior

All JSON errors use:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Request validation failed.",
    "details": {
      "errors": []
    }
  }
}
```

Common codes:

- `AUTHENTICATION_REQUIRED`
- `INVALID_AUTH_TOKEN`
- `INSUFFICIENT_SCOPE`
- `SKILL_ALREADY_EXISTS`
- `SKILL_NOT_FOUND`
- `SKILL_VERSION_NOT_FOUND`
- `POLICY_*`

## Core Shapes

Exact immutable coordinates use:

```json
{
  "slug": "python.lint",
  "version": "1.2.3"
}
```

Publish and exact metadata fetch return the same exact metadata response shape:

```json
{
  "slug": "python.lint",
  "version": "1.2.3",
  "install_count": 42,
  "version_checksum": {"algorithm": "sha256", "digest": "..."},
  "content": {
    "checksum": {"algorithm": "sha256", "digest": "..."},
    "size_bytes": 123
  },
  "metadata": {
    "name": "Python Lint",
    "description": "Linting skill",
    "tags": ["python", "lint"]
  },
  "lifecycle_status": "published",
  "trust_tier": "internal",
  "provenance": {
    "repo_url": "https://github.com/example/skills",
    "commit_sha": "aabbccddeeff00112233445566778899aabbccdd",
    "tree_path": "skills/python.lint",
    "publisher_identity": "ci/acme-release",
    "trust_context": {
      "trust_tier": "internal",
      "policy_profile": "default"
    }
  },
  "published_at": "2026-03-10T08:30:00Z"
}
```

`provenance` is advisory publish-time metadata only. `aptitude-publisher` or CI may
collect repository and publisher fields, while the server validates them,
persists them immutably, and derives `trust_context` from server-owned policy.
Discovery, resolution, and raw content reads do not depend on provenance.
`install_count` is a mutable aggregate per skill slug and is not part of the
immutable authored metadata block. The server increments it on successful exact
content fetches and mirrors the same value into discovery ranking.

## Endpoint Summary

| Method | Path | Scope | Success | Notes |
| --- | --- | --- | --- | --- |
| `GET` | `/healthz` | none | `200` | Liveness probe |
| `GET` | `/readyz` | none | `200` or `503` | Dependency readiness probe |
| `GET` | `/metrics` | none | `200` | Prometheus-compatible operational metrics |
| `POST` | `/skills/{slug}` | `publish` | `201` | Publish one immutable `slug@version` |
| `POST` | `/discovery` | `read` | `200` | Returns ordered candidate `slug` values only |
| `GET` | `/skills/{slug}` | `read` | `200` | Returns visible immutable versions for one skill identity |
| `GET` | `/resolution/{slug}/{version}` | `read` | `200` | Returns direct authored `depends_on` only |
| `GET` | `/skills/{slug}/{version}` | `read` | `200` | Returns immutable metadata for one exact coordinate |
| `GET` | `/skills/{slug}/{version}/content` | `read` | `200` | Returns immutable markdown with cache headers |
| `PATCH` | `/skills/{slug}/{version}/status` | `admin` | `200` | Transitions lifecycle state |

## Route Semantics

### `POST /discovery`

Request:

```json
{
  "name": "Python Lint",
  "description": "Lint Python files consistently",
  "tags": ["python", "lint"]
}
```

Response:

```json
{
  "candidates": ["python.lint", "python.format"]
}
```

Rules:

- Discovery is candidate generation only.
- It returns ordered `slug` values, not cards or versions.
- It does not choose a final candidate.
- It does not solve dependencies.
- Default governance visibility is `published` only.

### `GET /resolution/{slug}/{version}`

Response:

```json
{
  "slug": "python.lint",
  "version": "1.2.3",
  "depends_on": [
    {
      "slug": "python.base",
      "version_constraint": ">=1.0.0,<2.0.0",
      "optional": true,
      "markers": ["linux", "gpu"]
    }
  ]
}
```

Rules:

- Exact read only, not search.
- Returns direct authored `depends_on` selectors only.
- No recursion, solving, or transitive expansion.
- No `extends`, `conflicts_with`, or `overlaps_with` in the response.

### `GET /skills/{slug}`

Returns the visible immutable versions for one skill identity.

Response:

```json
{
  "slug": "python.lint",
  "versions": [
    {
      "version": "2.0.0",
      "lifecycle_status": "published",
      "trust_tier": "internal",
      "published_at": "2026-03-10T08:30:00Z",
      "is_current_default": true
    }
  ]
}
```

Rules:

- Identity read only; it does not inline full metadata or markdown.
- Missing slugs, or slugs with no versions visible to the caller, return `404`.
- Read policy matches exact fetch visibility: `published` and `deprecated` are readable with `read`; `archived` is admin-only.
- The server derives `is_current_default`; clients do not set it during publish.
- Default/list ordering is deterministic: `published` before `deprecated` before `archived`, then newer `published_at`, then lexicographically smaller `version` as the final tie-break.
- The first visible `published` or `deprecated` version is marked `is_current_default`.

### `GET /skills/{slug}/{version}`

Returns the exact metadata response for one exact coordinate.

Rules:

- Exact read only, not search.
- Returns the same metadata response shape as publish.
- Missing coordinates return `404`.
- Advisory provenance may be returned when it was captured at publish time.
- Read policy matches exact resolution rules: `published` and `deprecated` are readable with `read`; `archived` is admin-only.

### `GET /skills/{slug}/{version}/content`

Returns the immutable markdown body for one exact coordinate as
`text/markdown; charset=utf-8`.

Success headers include:

- `ETag`
- `Cache-Control: public, immutable`
- `Content-Length`

Rules:

- Exact read only, not search.
- Missing coordinates return `404`.
- The body is the raw stored markdown; metadata stays on the metadata route.
- Read policy matches the metadata exact-read route.

### `GET /metrics`

Returns Prometheus-compatible text exposition for operational scraping.

Rules:

- Operational endpoint only; not part of the registry-business route families.
- Unauthenticated in-app; protect exposure with deployment and network controls.
- Includes bounded HTTP and registry-operation metrics plus readiness gauges.

### `POST /skills/{slug}`

Publishes one immutable `slug@version` with:

- required `intent`
- markdown content
- structured metadata
- governance metadata
- authored relationships

Notes:

- `intent` must be one of:
  - `create_skill`: the slug must not exist yet or the server returns `409 SKILL_ALREADY_EXISTS`
  - `publish_version`: the slug must already exist or the server returns `404 SKILL_NOT_FOUND`
- `depends_on` items must provide exactly one of `version` or `version_constraint`.
- The `slug` comes from the path; the JSON body carries versioned content and metadata only.
- `internal` publish requires provenance.
- `verified` publish requires provenance and `admin`.
- Provenance is collected by the publisher client, validated and persisted by the server, and returned as advisory metadata only.
- `trust_context` is server-derived and must not be supplied by clients.
- Success returns metadata only, not embedded markdown or relationship graphs.

### `PATCH /skills/{slug}/{version}/status`

Transitions one immutable version between `published`, `deprecated`, and
`archived`.

Notes:

- Requires `admin`.
- Read callers can read `published` and `deprecated`.
- `archived` exact reads are admin-only.

## Discovery, Resolution, And Fetch On The Server

The implementation is split into a thin FastAPI interface layer, small core
services, and one SQLAlchemy repository adapter backed by PostgreSQL.

### Startup Wiring

At startup, [`app/main.py`](../../app/main.py) creates a single
`SQLAlchemySkillRegistryRepository`, a shared `GovernancePolicy`, and three
read-side services:

- `SkillDiscoveryService`
- `SkillResolutionService`
- `SkillFetchService`

Those are stored in `app.state` and injected into route handlers through
[`app/core/dependencies.py`](../../app/core/dependencies.py). The same dependency
module also authenticates Bearer tokens and turns them into `CallerIdentity`
objects with `read`, `publish`, or `admin` scopes.

### Discovery Flow

1. [`app/interface/api/discovery.py`](../../app/interface/api/discovery.py) validates the request DTO and requires a `read` caller.
2. The route calls [`app/core/skills/discovery.py`](../../app/core/skills/discovery.py), which converts `{name, description, tags}` into a search query.
3. Discovery reuses [`app/core/skills/search.py`](../../app/core/skills/search.py):
   - normalizes text and tags
   - resolves lifecycle/trust-tier filters through [`app/core/governance.py`](../../app/core/governance.py)
   - records an audit event
4. The repository executes ranked SQL against the denormalized
   `skill_search_documents` table via
   [`app/persistence/skill_registry_repository.py`](../../app/persistence/skill_registry_repository.py)
   and
   [`app/persistence/skill_registry_repository_support.py`](../../app/persistence/skill_registry_repository_support.py).

In practice, discovery is an indexed search path over normalized slug, name,
description, tags, lifecycle status, trust tier, publication time, and content
size. Ranking prefers exact slug match, then exact name match, then text rank,
tag overlap, usage count, freshness, and smaller content. The SQL also collapses
multiple versions down to the best candidate per slug before the API returns
only the ordered slug list.

### Resolution Flow

1. [`app/interface/api/resolution.py`](../../app/interface/api/resolution.py) validates `slug` and `version` path params and requires `read`.
2. [`app/core/skills/resolution.py`](../../app/core/skills/resolution.py) performs one exact lookup through the repository's relationship-read port.
3. The core service enforces exact-read governance for the stored lifecycle status and audits both allowed and denied exact reads.
4. The response is built by filtering the stored relationship selectors down to
   `depends_on` only.

Resolution is deliberately not a solver. The server does not recurse into
dependencies, choose versions, or expand transitive graphs. It returns the
authored first-degree selectors exactly enough for a client-side solver to make
the next decision.

### Fetch Flow

1. [`app/interface/api/fetch.py`](../../app/interface/api/fetch.py) validates `slug` and `version` path params and requires `read`.
2. [`app/core/skills/fetch.py`](../../app/core/skills/fetch.py) performs one exact repository lookup for metadata or content.
3. The core service checks exact-read governance on the stored lifecycle status and audits both allowed and denied exact reads.
4. Missing coordinates raise `SKILL_VERSION_NOT_FOUND`.
5. The route serializes:
   - metadata as the immutable JSON envelope
   - content as raw markdown bytes with immutable cache headers

## Governance Defaults

The built-in default profile currently does this:

- publish:
  - `untrusted`: `publish`
  - `internal`: `publish` plus provenance
  - `verified`: `admin` plus provenance
- discovery visibility:
  - default behavior: `published`
  - `read` callers may explicitly search `published` and `deprecated`
  - `admin` may also search `archived`
- exact reads:
  - `published`: `read`
  - `deprecated`: `read`
  - `archived`: `admin`

## Canonical Sources

Use these as implementation truth:

- [`app/main.py`](../../app/main.py)
- [`app/interface/api/README.md`](../../app/interface/api/README.md)
- [`app/interface/dto/skills.py`](../../app/interface/dto/skills.py)
- [`app/interface/dto/examples.py`](../../app/interface/dto/examples.py)
- Swagger UI: `http://127.0.0.1:8000/docs`
