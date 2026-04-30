# Deployment Changelog - Render and Neon Deployment Readiness

This changelog documents the deployment-readiness work captured in
[docs/reference/render-neon-deployment.md](../reference/render-neon-deployment.md).

The change makes Render plus Neon the documented production deployment path for
the registry API, removes the tracked Vercel serverless deployment surface, and
keeps Vercel scoped to DNS/domain management until a website or docs app exists.

## Scope Delivered

- Added a canonical deployment reference for the production API host
  `https://api.aptitude-registry.dev`, Render Web Service settings, Neon
  database setup, DNS wiring, and endpoint verification:
  [docs/reference/render-neon-deployment.md](../reference/render-neon-deployment.md),
  [docs/reference/README.md](../reference/README.md).
- Updated runtime and auth documentation so `APP_ENV=prod` host allowlisting
  points at the API subdomain and keeps the Render `onrender.com` host during
  rollout:
  [.env.example](../../.env.example),
  [docs/reference/runtime-profiles.md](../reference/runtime-profiles.md),
  [docs/reference/service-token-governance.md](../reference/service-token-governance.md).
- Removed the Vercel Python Function deployment surface because Vercel is no
  longer the app host:
  `api/index.py`,
  `server.py`,
  `vercel.json`,
  `.vercelignore`,
  [tests/unit/test_ci_workflows.py](../../tests/unit/test_ci_workflows.py).
- Removed direct runtime dependencies on deployment/tooling packages that are
  not needed by the Render-hosted app process:
  [pyproject.toml](../../pyproject.toml),
  [uv.lock](../../uv.lock),
  [tests/unit/test_dependency_manifest.py](../../tests/unit/test_dependency_manifest.py).

## Architecture Snapshot

```mermaid
flowchart LR
    Client["Registry client"] --> DNS["api.aptitude-registry.dev"]
    DNS --> Render["Render Web Service<br/>FastAPI app.main:app"]
    Render --> Settings["Runtime env<br/>APP_ENV, ALLOWED_HOSTS_JSON, tokens"]
    Render --> Alembic["Pre-deploy migration<br/>alembic upgrade head"]
    Render --> Neon["Neon Postgres<br/>DATABASE_URL"]
    Vercel["Vercel"] --> DNSMgmt["DNS/domain management only"]
    DNSMgmt --> DNS
```

Why this shape:

- The backend is already a conventional FastAPI service with a stable import
  string and runtime settings layer, so a persistent web service is the lowest
  friction deployment target:
  [app/main.py](../../app/main.py),
  [pyproject.toml](../../pyproject.toml),
  [docs/reference/render-neon-deployment.md](../reference/render-neon-deployment.md).
- Postgres remains external infrastructure. The app reads `DATABASE_URL`,
  Alembic resolves migrations through the same settings path, and readiness
  probes the database at runtime:
  [app/core/settings.py](../../app/core/settings.py),
  [alembic/env.py](../../alembic/env.py),
  [app/interface/api/health.py](../../app/interface/api/health.py).
- Vercel deployment artifacts were removed so the repo cannot accidentally
  redeploy the API through the old serverless path while the domain is being
  moved to Render:
  [tests/unit/test_ci_workflows.py](../../tests/unit/test_ci_workflows.py).

## Runtime Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Render FastAPI service
    participant S as Settings
    participant N as Neon Postgres

    C->>R: GET /healthz with Host api.aptitude-registry.dev
    R->>S: Load APP_ENV and ALLOWED_HOSTS_JSON
    S-->>R: prod posture + trusted hosts
    R-->>C: 200 liveness response
    C->>R: GET /readyz
    R->>N: SELECT 1 readiness probe
    N-->>R: reachable or error
    R-->>C: 200 ready or 503 not_ready
```

## Design Notes

- The production URL is now the API subdomain, not the root domain. That keeps
  `aptitude-registry.dev` available for a future website or redirect and avoids
  mixing API hosting with a frontend that does not exist yet:
  [docs/reference/runtime-profiles.md](../reference/runtime-profiles.md),
  [docs/reference/render-neon-deployment.md](../reference/render-neon-deployment.md).
- Render remains the documented app host because it supports the current
  persistent FastAPI plus Alembic plus Postgres shape without porting the
  request model:
  [docs/reference/render-neon-deployment.md](../reference/render-neon-deployment.md).
- Neon pooling is intentionally deferred. The documented first deployment uses a
  direct Neon connection for both runtime and migrations so Alembic does not run
  through a pooled `-pooler` endpoint:
  [docs/reference/render-neon-deployment.md](../reference/render-neon-deployment.md),
  [alembic/env.py](../../alembic/env.py).
- CORS remains disabled because no browser client exists. The deployment work
  changes host and infrastructure guidance, not the public HTTP route contract:
  [docs/reference/render-neon-deployment.md](../reference/render-neon-deployment.md),
  [docs/reference/api-contract.md](../reference/api-contract.md).
- `fastapi-cloud-cli` is no longer a direct project dependency, but it can still
  appear transitively through `fastapi[standard]`. Removing it fully would
  require a separate dependency/start-command decision:
  [pyproject.toml](../../pyproject.toml),
  [uv.lock](../../uv.lock).

## Schema Reference

Source:
[app/core/settings.py](../../app/core/settings.py),
[docs/reference/render-neon-deployment.md](../reference/render-neon-deployment.md),
[.env.example](../../.env.example).

### Deployment environment contract

| Field | Type | Nullable | Default / Constraint | Role |
| --- | --- | --- | --- | --- |
| `APP_ENV` | `string` | No | `prod` for Render | Enables production posture, including disabled docs and trusted-host enforcement. |
| `DATABASE_URL` | `string` | No | Neon direct connection using `postgresql+psycopg://...` | Gives the app and Alembic the primary PostgreSQL connection string. |
| `AUTH_SERVICE_TOKENS_JSON` | `JSON array` | No | token records with sha256 secret digests | Supplies governed bearer-token records for protected API routes and `/metrics`. |
| `ALLOWED_HOSTS_JSON` | `JSON array[string]` | No in `prod` | includes `api.aptitude-registry.dev` and rollout Render host | Defines accepted `Host` headers for `TrustedHostMiddleware`. |
| `ACTIVE_POLICY_PROFILE` | `string` | No | `default` | Selects the active governance policy profile without changing route shape. |
| `LOG_FORMAT` | `string` | No | `auto` | Keeps Render production logs structured through the existing logging settings. |

### Removed Vercel deployment files

| File | Previous role | Current role |
| --- | --- | --- |
| `api/index.py` | Vercel Python Function import wrapper for `app.main:app`. | Removed so Vercel no longer has an app entrypoint in this repo. |
| `server.py` | Alternate Vercel FastAPI entrypoint. | Removed with the old Vercel hosting path. |
| `vercel.json` | Vercel deployment filter and region configuration. | Removed because Vercel is DNS-only for this project now. |
| `.vercelignore` | Upload filter for Vercel Function deployments. | Removed because no Vercel deployment package is produced. |

## Verification Notes

- Dependency-boundary coverage now asserts `ruff` and `fastapi-cloud-cli` are
  not direct runtime dependencies while `ruff` remains available through the
  dev extra:
  [tests/unit/test_dependency_manifest.py](../../tests/unit/test_dependency_manifest.py).
- CI workflow coverage now asserts Vercel deployment commands stay absent and
  the old serverless deployment files do not exist:
  [tests/unit/test_ci_workflows.py](../../tests/unit/test_ci_workflows.py).
- Local verification for the deployment-prep patch passed:
  `UV_CACHE_DIR=.uv-cache uv run --extra dev ruff check .`,
  `UV_CACHE_DIR=.uv-cache uv run --extra dev ruff format --check .`,
  `UV_CACHE_DIR=.uv-cache uv run --extra dev python -m mypy app`,
  `UV_CACHE_DIR=.uv-cache uv run --extra dev python -m pytest tests/unit -q`,
  and `UV_CACHE_DIR=.uv-cache uv lock --check`.
- No live Render service, Neon database, or DNS record was created by this
  repository change. Those remain external infrastructure steps documented in
  [docs/reference/render-neon-deployment.md](../reference/render-neon-deployment.md).
