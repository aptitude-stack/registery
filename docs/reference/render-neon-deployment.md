# Render and Neon Deployment

Canonical deployment reference for the production Aptitude Registry API.

## Deployment Shape

- Render owns the persistent FastAPI web service.
- Neon owns the production PostgreSQL database.
- Vercel may manage DNS for `aptitude-registry.dev`, but must not deploy a frontend, docs app, or Python Function for this project yet.
- Production API host: `https://api.aptitude-registry.dev`.
- Root domain: leave unused, parked, or redirect later when a website exists.

Deployable backend entrypoint:

- FastAPI import string: `app.main:app`
- FastAPI CLI entrypoint: `[tool.fastapi] entrypoint = "app.main:app"` in `pyproject.toml`
- Runtime settings: `app/core/settings.py`
- Migration entrypoint: `uv run alembic upgrade head`
- Health endpoints: `GET /healthz` for liveness, `GET /readyz` for database readiness

## Render Web Service

Create a Render Web Service from the Git repository using the native Python runtime.
Do not use Docker for the first free-tier deployment.

Recommended settings:

| Setting | Value |
| --- | --- |
| Service name | `aptitude-registry-api` |
| Runtime | `Python 3` |
| Instance type | `Free` for first validation |
| Branch | `master` |
| Region | Match Neon as closely as possible; Frankfurt is a reasonable first choice |
| Python version env | `PYTHON_VERSION=3.12.13` |
| Build command | `uv sync --frozen --no-dev` |
| Pre-deploy command | `uv run alembic upgrade head` |
| Start command | `uv run fastapi run --entrypoint app.main:app --host 0.0.0.0 --port $PORT --no-proxy-headers` |
| Health check path | `/healthz` |

Required Render environment variables:

```text
APP_ENV=prod
APP_NAME=aptitude-registry
LOG_LEVEL=INFO
LOG_FORMAT=auto
DATABASE_URL=postgresql+psycopg://<neon-role>:<password>@<neon-host>/<database>?sslmode=require&channel_binding=require
AUTH_SERVICE_TOKENS_JSON=[{"token_id":"reader-token","secret_digest":"<sha256>","scopes":["read"],"active":true},{"token_id":"publisher-token","secret_digest":"<sha256>","scopes":["read","publish"],"active":true},{"token_id":"admin-token","secret_digest":"<sha256>","scopes":["read","publish","admin"],"active":true}]
ALLOWED_HOSTS_JSON=["api.aptitude-registry.dev","<render-service>.onrender.com"]
ACTIVE_POLICY_PROFILE=default
```

Keep the Render `onrender.com` host in `ALLOWED_HOSTS_JSON` until custom-domain verification and health checks are stable. After that, either keep it for emergency access or disable the Render subdomain and remove it from the allowlist.

## Neon Database

Create one Neon production database:

| Neon resource | Value |
| --- | --- |
| Project | `aptitude-registry` |
| Branch | `production` |
| Database | `aptitude` |
| Role | `aptitude_app` |

Use Neon's direct connection string for initial runtime and migration traffic.
Convert the URL scheme to `postgresql+psycopg://` because the app uses `psycopg[binary]`.

Do not point Alembic at a Neon pooled `-pooler` host. If runtime pooling becomes necessary later, add a separate migration URL setting first so Alembic can keep using the direct connection while the web process uses the pooled runtime URL.

## DNS

In Render:

1. Add `api.aptitude-registry.dev` as a custom domain on the web service.
2. Keep managed TLS enabled.
3. Copy Render's DNS target for the service.

In Vercel DNS for `aptitude-registry.dev`:

```text
Type: CNAME
Name: api
Value: <render-service>.onrender.com
TTL: auto/default
```

Do not configure a root-domain app deployment in Vercel.

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
curl -i https://<render-service>.onrender.com/healthz
curl -i https://<render-service>.onrender.com/readyz
curl -i https://api.aptitude-registry.dev/healthz
curl -i https://api.aptitude-registry.dev/readyz
curl -i https://api.aptitude-registry.dev/docs
curl -i -H "Authorization: Bearer admin-token.<raw-secret>" https://api.aptitude-registry.dev/metrics
```

Expected results:

- `/healthz` returns `200` with `"environment":"prod"`.
- `/readyz` returns `200` when Neon is reachable and `503` when the database is unavailable.
- `/docs` returns `404` in production.
- `/metrics` returns `200` only with an admin bearer token.
- Protected routes without a valid token return `401` or `403`.

## Constraints

- Keep CORS disabled until a real browser client exists.
- Keep `/healthz` public and lightweight for Render health checks.
- Keep `/readyz` public as a dependency-readiness probe.
- Do not add Neon Auth, Neon JS SDK, Render SDKs, or PostgREST-style packages to the FastAPI app.
- Free-tier Render services and Neon compute can sleep after idle periods, so first request latency is expected.
