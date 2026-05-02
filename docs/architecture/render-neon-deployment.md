# Render and Neon Deployment Architecture

Canonical deployment document for the production Aptitude Registry API.

This document replaces the former deployment reference and deployment-readiness
changelog. It is current-state architecture first, with the deployment history
kept here only where it explains why the production shape looks this way.

## Deployment Shape

```mermaid
flowchart LR
    Client["Registry client"] --> DNS["api.aptitude-registry.dev"]
    DNS --> Render["Render Web Service<br/>FastAPI app.main:app"]
    Render --> Settings["Runtime settings<br/>APP_ENV, hosts, tokens"]
    Render --> RuntimeDB["Neon pooled URL<br/>DATABASE_URL"]
    Render --> MigrationDB["Neon direct URL<br/>MIGRATION_DATABASE_URL"]
    RuntimeDB --> Neon["Neon Postgres<br/>production branch"]
    MigrationDB --> Neon
    Vercel["Vercel"] --> DNSMgmt["DNS management only"]
    DNSMgmt --> DNS
```

- Render owns the persistent FastAPI web service.
- Neon owns the production PostgreSQL database.
- Vercel may manage DNS for `aptitude-registry.dev`, but must not deploy a
  frontend, docs app, or Python Function for this project yet.
- Production API host: `https://api.aptitude-registry.dev`.
- Render fallback host: `https://aptitude-registry-api.onrender.com`.
- Root domain: leave unused, parked, or redirect later when a website exists.

Deployable backend entrypoint:

| Concern | Current value |
| --- | --- |
| FastAPI import string | `app.main:app` |
| FastAPI CLI entrypoint | `[tool.fastapi] entrypoint = "app.main:app"` in [`pyproject.toml`](../../pyproject.toml) |
| Runtime settings | [`app/core/settings.py`](../../app/core/settings.py) |
| Migration command | `uv run alembic upgrade head` |
| Liveness endpoint | `GET /healthz` |
| Readiness endpoint | `GET /readyz` |

## Current Live Deployment

Status verified from public endpoints on 2026-05-02.

| Resource | Value |
| --- | --- |
| Render service | `aptitude-registry-api` / `srv-d7pqsd7avr4c73bfb8t0` |
| Render primary URL | `https://aptitude-registry-api.onrender.com` |
| Production API URL | `https://api.aptitude-registry.dev` |
| Render region | `virginia`, matching the Neon `aws-us-east-1` project |
| Render branch tracking | Service metadata tracks `master`; target Blueprint state is `checksPass` |
| Neon organization | `Aptitude` / `org-wild-pond-20247201`, managed directly in Neon Console |
| Neon project | `aptitude-registry` / `bitter-night-16887852` |
| Neon branch | `production` / `br-calm-bonus-ambx0ki5` |
| Neon database | `aptitude` |
| Neon role | `aptitude_app` |
| Neon PostgreSQL version | `17` |
| DNS status | `api.aptitude-registry.dev` resolves by CNAME to `aptitude-registry-api.onrender.com` |
| HTTPS status | `/healthz`, `/readyz`, and `/docs` return `200` on both the custom API domain and Render fallback host |

The registry database runs in a standalone Neon Console-managed organization.
The earlier Vercel-managed Neon project was deleted during cutover and is no
longer the production database source.

Trigger a Render deploy after changing production environment variables:

```bash
render deploys create srv-d7pqsd7avr4c73bfb8t0 --wait --confirm --output json
```

## Render Web Service

Create the production app as a Render Web Service from the Git repository using
the native Python runtime. Do not use Docker for the managed production
deployment unless this architecture is intentionally revisited.

Recommended settings:

| Setting | Value |
| --- | --- |
| Service name | `aptitude-registry-api` |
| Runtime | `Python 3` |
| Instance type | `Starter` for production so Render runs the pre-deploy migration hook |
| Branch | `master` |
| Region | Match Neon as closely as possible; current live service uses `virginia` for Neon `aws-us-east-1` |
| Python version env | `PYTHON_VERSION=3.12.13` |
| Build command | `uv sync --frozen --no-dev --extra otel` |
| Pre-deploy command | `uv run alembic upgrade head` |
| Start command | `uv run fastapi run --entrypoint app.main:app --host 0.0.0.0 --port $PORT --no-proxy-headers` |
| Health check path | `/healthz` |

The `--extra otel` flag installs the OpenTelemetry SDK, OTLP/HTTP exporters,
and FastAPI/SQLAlchemy/psycopg/logging instrumentation packages used to ship
traces, logs, and metrics to Grafana Cloud. Without it the app boots in a
no-op telemetry mode, and `OTEL_ENABLED=true` fails at import time.

Required Render environment variables:

```text
APP_ENV=prod
APP_NAME=aptitude-registry
LOG_LEVEL=INFO
LOG_FORMAT=auto
DATABASE_URL=postgresql+psycopg://<neon-role>:<password>@<neon-pooler-host>/<database>?sslmode=require&channel_binding=require
MIGRATION_DATABASE_URL=postgresql+psycopg://<neon-role>:<password>@<direct-neon-host>/<database>?sslmode=require&channel_binding=require
AUTH_SERVICE_TOKENS_JSON=[{"token_id":"reader-token","secret_digest":"<sha256>","scopes":["read"],"active":true},{"token_id":"publisher-token","secret_digest":"<sha256>","scopes":["read","publish"],"active":true},{"token_id":"admin-token","secret_digest":"<sha256>","scopes":["read","publish","admin"],"active":true}]
ALLOWED_HOSTS_JSON=["api.aptitude-registry.dev","aptitude-registry-api.onrender.com"]
ACTIVE_POLICY_PROFILE=default
```

For production runtime, `DATABASE_URL` should use the Neon pooled host
(`-pooler`). `MIGRATION_DATABASE_URL` must use the direct Neon host because
Alembic should not run through PgBouncer.

Keep the Render `onrender.com` host in `ALLOWED_HOSTS_JSON` until custom-domain
verification and health checks are stable. After that, either keep it for
emergency access or disable the Render subdomain and remove it from the
allowlist.

## Neon Database

Create one Neon production database in the standalone Neon Console-managed
organization:

| Neon resource | Value |
| --- | --- |
| Organization | `Aptitude` / `org-wild-pond-20247201` |
| Project | `aptitude-registry` / `bitter-night-16887852` |
| Branch | `production` / `br-calm-bonus-ambx0ki5` |
| Database | `aptitude` |
| Role | `aptitude_app` |

Use Neon's pooled connection string for runtime traffic and a direct connection
string for migration traffic. Convert both URL schemes to
`postgresql+psycopg://` because the app uses `psycopg[binary]`.

Do not point Alembic at a Neon pooled `-pooler` host. The app exposes this
split as `DATABASE_URL` for runtime and `MIGRATION_DATABASE_URL` for
migrations.

Enable the query-statistics extension once on the production database for
observability:

```sql
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
SELECT extname FROM pg_extension WHERE extname = 'pg_stat_statements';
```

## DNS and Domain Ownership

In Render:

1. Add `api.aptitude-registry.dev` as a custom domain on the web service.
2. Keep managed TLS enabled.
3. Copy Render's DNS target for the service.

In Vercel DNS for `aptitude-registry.dev`:

```text
Type: CNAME
Name: api
Value: aptitude-registry-api.onrender.com
TTL: auto/default
```

Do not configure a root-domain app deployment in Vercel. Vercel is DNS-only for
this project until a real website or docs app exists.

## OpenTelemetry Rollout

Optional OpenTelemetry to Grafana Cloud variables must be set together. See
[`../reference/observability-grafana-cloud.md`](../reference/observability-grafana-cloud.md)
for the Access Policy token scopes and signal-specific troubleshooting.

```text
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-<region>.grafana.net/otlp
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic%20<base64(instance_id:access_token)>
OTEL_RESOURCE_ATTRIBUTES=service.namespace=aptitude,deployment.environment.name=prod
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=0.1
```

Rollout sequence:

1. Provision a Grafana Cloud Access Policy with `metrics:write`, `logs:write`,
   and `traces:write` scopes.
2. Confirm the Grafana Cloud OTLP gateway URL for the stack region.
3. In Render, add the OTel variables and mark `OTEL_EXPORTER_OTLP_HEADERS`
   encrypted.
4. Keep the Build Command at `uv sync --frozen --no-dev --extra otel`.
5. Trigger a manual Render deploy.
6. Verify traces, logs, and metrics arrive in Grafana Cloud within about 60
   seconds of the first non-probe request.

When `OTEL_ENABLED=true` and `APP_ENV=prod`, the Settings validator refuses to
boot without `OTEL_EXPORTER_OTLP_ENDPOINT`.

## Migration Policy

Preferred production migration path:

- Render `Starter` or higher runs `uv run alembic upgrade head` as the
  pre-deploy command.
- `DATABASE_URL` remains pooled for the running app.
- `MIGRATION_DATABASE_URL` remains direct for Alembic.

Fallback path when the service is temporarily on Render Free:

```bash
APP_SETTINGS_ENV_FILE=/path/to/prod.env UV_CACHE_DIR=.uv-cache uv run alembic upgrade head
APP_SETTINGS_ENV_FILE=/path/to/prod.env UV_CACHE_DIR=.uv-cache uv run alembic current
```

The live deployment has used this manual path before. At the standalone Neon
cutover, Alembic reported `0003_skill_bundle_storage (head)`.

## Deployment History

This section absorbs the former deployment-readiness changelog and standalone
Neon cutover note. Treat it as rationale for the current architecture, not as a
separate canonical history surface.

### Render and Neon Readiness

- Render plus Neon became the documented production deployment path for
  `https://api.aptitude-registry.dev`.
- Runtime and auth docs were updated so `APP_ENV=prod` host allowlisting points
  at the API subdomain and keeps the Render fallback host during rollout:
  [`.env.example`](../../.env.example),
  [`../reference/runtime-profiles.md`](../reference/runtime-profiles.md),
  [`../reference/service-token-governance.md`](../reference/service-token-governance.md).
- The tracked Vercel Python Function deployment surface was removed because
  Vercel is no longer the app host: `api/index.py`, `server.py`,
  `vercel.json`, and `.vercelignore` no longer define a deployment path.
- Direct runtime dependencies on deployment/tooling packages that are not
  needed by the Render-hosted app process were removed from
  [`pyproject.toml`](../../pyproject.toml) and [`uv.lock`](../../uv.lock).
- CORS stayed disabled because no browser client exists. The deployment work
  changed hosting and infrastructure guidance, not the public HTTP route
  contract in [`../reference/api-contract.md`](../reference/api-contract.md).

### Standalone Neon Cutover

- The first Neon organization was Vercel-managed and rejected creation of a
  separate `aptitude-registry` project.
- Production was cut over to a standalone Neon Console-managed organization,
  project, branch, database, and role.
- The cutover was schema-only; no data was copied from the deleted
  Vercel-managed Neon project.
- Alembic was run manually against the new direct Neon connection before the
  Render service environment was switched.
- Render deploy `dep-d7q5lqdckfvc739isqpg` verified the service after the
  database change.

## Plan 16 Trust-Consumer Deployment Readiness

[`Plan 16 - Registry Trust Consumer Contracts`](../../.agents/plans/16-registry-trust-consumer-contracts.md)
is planning-only in this repository state. There is no implemented Plan 16
deployment surface or milestone changelog to promote into current behavior.

The deployment architecture still needs to preserve these Plan 16 constraints:

| Consumer | Deployment implication |
| --- | --- |
| Gateway | Future trust-context reads must be served from the stable API host and remain exact-coordinate based, such as `slug@version`, instead of becoming fuzzy discovery or runtime orchestration. |
| Identity | Registry namespaces, scopes, policy visibility, and audit correlation must remain registry facts; principal lifecycle stays outside this service. |
| Token/spend control | Runtime usage attribution can reference registry artifact, organization, trust tier, promotion channel, and policy context, but budget enforcement and billing ledgers stay outside this service. |
| Audit consumers | Downstream events should be able to correlate back to registry publish, approval, promotion, policy, and audit evidence without mutating immutable artifact records. |

When Plan 16 is implemented, its changelog should document the new HTTP
contract, DTO shape, schema/storage changes, auth requirements, and deployment
verification against this Render/Neon production architecture. Until then, do
not describe gateway interception, identity issuance, token-budget enforcement,
or billing behavior as registry runtime features.

## Verification

Local preflight:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev ruff check .
UV_CACHE_DIR=.uv-cache uv run --extra dev python -m mypy app
UV_CACHE_DIR=.uv-cache uv run --extra dev python -m pytest tests/unit -q
```

Render shell or deploy-log checks:

```bash
uv run alembic current
uv run alembic upgrade head
```

Endpoint checks:

```bash
curl -i https://aptitude-registry-api.onrender.com/healthz
curl -i https://aptitude-registry-api.onrender.com/readyz
curl -i https://aptitude-registry-api.onrender.com/docs
curl -i --max-time 20 https://api.aptitude-registry.dev/healthz
curl -i --max-time 20 https://api.aptitude-registry.dev/readyz
curl -i --max-time 20 https://api.aptitude-registry.dev/docs
```

DNS checks:

```bash
dig +short api.aptitude-registry.dev CNAME
dig +short api.aptitude-registry.dev A
```

Expected results:

- `/healthz` returns `200` with `"environment":"prod"`.
- `/readyz` returns `200` when Neon is reachable and `503` when the database is
  unavailable.
- `/docs` returns `200` in the current production app wiring.
- Protected routes without a valid token return `401` or `403`.
- `api.aptitude-registry.dev` resolves through `aptitude-registry-api.onrender.com`.

Telemetry verification after a deploy with `OTEL_ENABLED=true`:

- Traces: Grafana Cloud Tempo should show `service.name=aptitude-registry` and
  `deployment.environment.name=prod`; `/healthz` and `/readyz` should be
  excluded.
- Logs: Grafana Cloud Loki should receive application logs with `trace_id` and
  `span_id` fields on traced requests.
- Metrics: Grafana Cloud Mimir should show
  `aptitude_http_requests_total{deployment_environment_name="prod"}` increasing
  after one minute of traffic.

## Constraints

- Keep CORS disabled until a real browser client exists.
- Keep `/healthz` public and lightweight for Render health checks.
- Keep `/readyz` public as a dependency-readiness probe.
- Do not add Neon Auth, Neon JS SDK, Render SDKs, or PostgREST-style packages
  to the FastAPI app.
- Do not move gateway enforcement, identity lifecycle, token-budget
  enforcement, resolver reranking, dependency solving, or runtime execution into
  this repository.
