# API Contract

> Status: canonical public HTTP contract for `Aptitude Registry`.

## Boundary

This API stays registry-first.

- Server-owned: immutable publish, candidate discovery, exact dependency reads, exact immutable fetch, lifecycle governance, and audit.
- Client-owned: prompt interpretation, reranking, final selection, dependency solving, lock generation, and execution planning.

Public routes:

- `GET /`
- `GET /healthz`
- `GET /readyz`

Protected routes:

- `POST /skills/{slug}`
- `POST /discovery`
- `GET /catalog/top-skills` - website homepage catalog feed
- `POST /catalog/search` - website search catalog feed
- `GET /skills/{slug}`
- `GET /resolution/{slug}/{version}`
- `GET /skills/{slug}/{version}`
- `GET /skills/{slug}/{version}/content`
- `PATCH /skills/{slug}/{version}/status`
- `POST /admin/organizations`
- `POST /admin/namespaces`
- `PUT /admin/policy-packs/{slug}`
- `PATCH /admin/skills/{slug}/ownership`
- `PATCH /admin/skills/{slug}/{version}/governance`
- `POST /admin/skills/{slug}/{version}/trust-evidence`

## Freeze Rule

- Identity reads stay on `GET /skills/{slug}`.
- Exact coordinate reads stay on:
  - `GET /skills/{slug}/{version}`
  - `GET /skills/{slug}/{version}/content`
- Discovery returns candidate slugs only.
- Catalog search may return card-ready metadata, but it must reuse discovery
  request semantics and remain separate from resolver selection.
- Resolution returns direct authored `depends_on` only.
- Exact fetch returns immutable metadata or the exact immutable bundle artifact for one coordinate.

## Publish

`POST /skills/{slug}` now uses `multipart/form-data`.

Required parts:

| Part | Content Type | Meaning |
| --- | --- | --- |
| `metadata` | `application/json` | Queryable metadata, governance, and relationships |
| `bundle` | `application/zstd` | Immutable `.tar.zst` skill artifact stored without unpacking |

The server validates the uploaded archive structure at publish time and then stores one immutable digest-addressed bundle per version.

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
  "namespace": "public",
  "artifact_origin": "internal",
  "review_state": "approved",
  "promotion_channel": "prod",
  "policy_pack_slug": null,
  "published_at": "2026-03-10T08:30:00Z"
}
```

`provenance` remains advisory publish-time metadata and stays queryable outside the bundle.

## Website Homepage Catalog

`GET /catalog/top-skills?limit=12` is the website-facing homepage catalog
feed. It returns visible current-default versions ordered by aggregate install
count.

```json
{
  "skills": [
    {
      "slug": "python.lint",
      "version": "1.2.3",
      "install_count": 42,
      "metadata": {
        "name": "Python Lint",
        "description": "Linting skill",
        "tags": ["python", "lint"]
      },
      "lifecycle_status": "published",
      "trust_tier": "internal",
      "published_at": "2026-03-10T08:30:00Z"
    }
  ]
}
```

Rules:

- `limit` must be between `1` and `24`.
- Ordering is `install_count DESC`, then `published_at DESC`, then `slug ASC`.
- Visibility follows the same governance filters as version listing.
- Archived, private, or otherwise non-visible versions are not returned.

## Website Catalog Search

`POST /catalog/search?limit=20` is the website-facing search catalog feed. It
accepts the same JSON body as `POST /discovery` and returns visible
current-default metadata in discovery order. It exists for website/card-style
catalog rendering; `POST /discovery` continues to return ordered slug strings
only.

Request:

```json
{
  "name": "python lint",
  "description": "lint FastAPI services",
  "tags": ["python"],
  "context_skills": []
}
```

Response shape:

```json
{
  "skills": [
    {
      "slug": "python.lint",
      "version": "1.2.3",
      "install_count": 42,
      "metadata": {
        "name": "Python Lint",
        "description": "Linting skill",
        "tags": ["python", "lint"]
      },
      "lifecycle_status": "published",
      "trust_tier": "internal",
      "published_at": "2026-03-10T08:30:00Z"
    }
  ]
}
```

Rules:

- `limit` must be between `1` and `20`; default is `20`.
- Ordering matches discovery candidate order.
- Visibility follows the same governance filters as version listing and
  top-skills.

Checksum semantics:

- `content.checksum.digest` is the persisted `sha256` digest of the exact stored artifact bytes.
- `version_checksum.digest` is the persisted `sha256` digest of the canonical version payload, which includes the content digest plus metadata, publish-time trust/provenance inputs, and authored relationships.
- Mutable enterprise workflow state does not rewrite artifact bytes or recompute `version_checksum.digest`; audit rows are the authoritative history for post-publish review, promotion, trust-tier, policy-pack, ownership, and trust-evidence changes.

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

## Authentication And Prod Posture

Protected routes require:

- `Authorization: Bearer <token_id>.<token_secret>`
- governed service-token scopes: `read`, `publish`, `review`, or `admin`
- namespace grants for namespace-scoped registry operations, including allowed promotion channels

Operational rules:

- Operational telemetry (traces, logs, metrics) is exported over OTLP/HTTP to Grafana Cloud when `OTEL_ENABLED=true`. The legacy `/metrics` Prometheus exposition endpoint has been removed.
- publish, read, review, and admin operations require both the route scope and the matching namespace grant.
- review and promotion operations require `review` scope plus a namespace `review` grant, while `admin` tokens may use a global `*` grant for bootstrap/control-plane work.
- `/docs`, `/redoc`, and `/openapi.json` are available in both `dev` and `prod`.
- `prod` rejects unexpected `Host` headers with the configured allowlist.
- Forwarded proxy headers are not trusted by default at the application boundary.

The canonical auth details, scope semantics, and local dev fixture tokens live in [`service-token-governance.md`](service-token-governance.md).

## Cross-Cutting HTTP Rules

Request correlation:

- Clients may send `X-Request-ID` on any route.
- The server echoes `X-Request-ID` on both success and error responses.
- If the client does not send one, the server generates a request id before routing.

Error envelope:

- API errors use a stable JSON shape:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Request validation failed.",
    "details": {}
  }
}
```

- `401` authentication failures use stable codes such as `AUTHENTICATION_REQUIRED`, `MALFORMED_AUTH_TOKEN`, `INVALID_AUTH_TOKEN`, `INACTIVE_AUTH_TOKEN`, and `EXPIRED_AUTH_TOKEN`.
- `403` authorization or governance failures use stable codes such as `INSUFFICIENT_SCOPE`, `POLICY_PUBLISH_FORBIDDEN`, `POLICY_PROVENANCE_REQUIRED`, `POLICY_STATUS_TRANSITION_FORBIDDEN`, and `POLICY_EXACT_READ_FORBIDDEN`.
- Enterprise visibility failures use stable codes such as `POLICY_NAMESPACE_FORBIDDEN`, `POLICY_REVIEW_STATE_FORBIDDEN`, and `POLICY_PACK_FORBIDDEN`.
- `422` request-shape failures use `INVALID_REQUEST`.

## Endpoint Summary

| Method | Path | Scope | Success | Notes |
| --- | --- | --- | --- | --- |
| `GET` | `/` | none | `200` | Work-in-progress default service page |
| `GET` | `/healthz` | none | `200` | Liveness probe |
| `GET` | `/readyz` | none | `200` or `503` | Dependency readiness probe |
| `POST` | `/skills/{slug}` | `publish` | `201` | Publish one immutable `slug@version` via `multipart/form-data` |
| `POST` | `/discovery` | `read` | `200` | Returns ordered candidate `slug` values only |
| `GET` | `/catalog/top-skills` | `read` | `200` | Website homepage feed; returns visible current-default versions ordered by install count |
| `POST` | `/catalog/search` | `read` | `200` | Website search feed; returns visible current-default metadata in discovery order |
| `GET` | `/skills/{slug}` | `read` | `200` | Returns visible immutable versions for one skill identity |
| `GET` | `/resolution/{slug}/{version}` | `read` | `200` | Returns direct authored `depends_on` only |
| `GET` | `/skills/{slug}/{version}` | `read` | `200` | Returns immutable metadata for one exact coordinate |
| `GET` | `/skills/{slug}/{version}/content` | `read` | `200` | Returns immutable `application/zstd` artifact with cache headers |
| `PATCH` | `/skills/{slug}/{version}/status` | `admin` | `200` | Transitions lifecycle state |
| `POST` | `/admin/organizations` | `admin` | `201` | Creates an enterprise organization |
| `POST` | `/admin/namespaces` | `admin` | `201` | Creates a namespace owned by an organization |
| `PUT` | `/admin/policy-packs/{slug}` | `admin` | `200` | Creates or updates a registry-enforced policy-pack reference |
| `PATCH` | `/admin/skills/{slug}/ownership` | `admin` | `200` | Moves a skill identity into a namespace |
| `PATCH` | `/admin/skills/{slug}/{version}/governance` | `review` | `200` | Updates review, promotion, trust-tier, or policy-pack state |
| `POST` | `/admin/skills/{slug}/{version}/trust-evidence` | `review` | `201` | Appends trust evidence without rewriting artifact bytes |

## Enterprise Governance

Enterprise governance state is mutable registry control-plane state. It filters visibility and eligibility but does not rewrite immutable artifact coordinates or content bytes.

- `namespace`: ownership boundary for skill identities, default `public`.
- `artifact_origin`: `internal`, `imported`, `verified`, or `restricted`.
- `review_state`: `pending_review`, `approved`, or `rejected`.
- `promotion_channel`: governance promotion channel `dev`, `staging`, or `prod`; this is not `APP_ENV`.
- `policy_pack_slug`: optional reference to a registry policy pack.

Default publish behavior:

- internal artifacts publish into `public`, `approved`, `prod`.
- imported artifacts publish into `pending_review`, `dev` and are hidden from production readers until reviewed and promoted.

Visibility is enforced consistently for discovery, catalog search, version listing, exact metadata, exact content, and resolution. Discovery still returns candidate slugs only, catalog search returns card-ready metadata only, resolution still returns direct authored `depends_on` selectors only, and exact content still returns the same immutable `.tar.zst` bytes.

Discovery remains lexical-primary. Optional semantic expansion and co-usage
signals are internal ranking inputs inside `POST /discovery`; they do not add
routes or response fields. Semantic expansion embeds description and tags only;
the required discovery `name` remains a lexical identity/search input. The
request may include `context_skills` to identify already selected/installed
skill slugs for bounded co-usage boosts, but those values are not dependency
declarations.

Trust evidence is append-only. Evidence response payloads expose evidence type, subject, digest, URI, and creation time, but not the raw evidence payload.

Detailed state, policy-pack, and audit rules live in [`enterprise-governance.md`](enterprise-governance.md).
