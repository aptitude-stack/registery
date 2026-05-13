# Runtime Profiles and Environment Variables

This repo has two different kinds of "profiles". They solve different problems and should not be mixed together.

## Runtime Profile: `APP_ENV`

`APP_ENV` is the application's runtime profile. It is validated and accepts only:

- `dev`: local development and fast iteration
- `prod`: deployed or production-like execution

`APP_ENV` changes runtime posture such as logging and future environment-specific wiring. It does not change the public HTTP contract. The same routes, request shapes, and response shapes must exist in both profiles.

Runtime posture changes that do apply today:

- `dev` and `prod` both keep `/docs`, `/redoc`, and `/openapi.json` enabled.
- `prod` enforces `ALLOWED_HOSTS_JSON` through trusted-host validation.
- protected routes require the same governed bearer-token auth in both `dev` and `prod`.

There is no `test`, `container`, or `staging` runtime profile in the app.

## FastAPI CLI vs `APP_ENV`

The FastAPI CLI mode and the app runtime profile are separate controls.

- `fastapi dev`: local server mode with reload, bound to `127.0.0.1` by default
- `fastapi run`: production-style server mode without reload
- `APP_ENV=dev|prod`: application runtime posture used by the registry settings layer

Do not assume `fastapi dev` automatically means `APP_ENV=dev`, or that `fastapi run`
automatically means `APP_ENV=prod`. Set `APP_ENV` explicitly when you care about the
app posture.

Recommended app-process commands:

```bash
APP_ENV=dev uv run fastapi dev
APP_ENV=prod uv run fastapi run
```

If the app process should read a dotenv file other than `.env`, point
`APP_SETTINGS_ENV_FILE` at it:

```bash
APP_ENV=prod APP_SETTINGS_ENV_FILE=.env.local-prod uv run fastapi run
```

Plan 14 keeps the route-protection model aligned across both profiles. `dev` does not
add an auth bypass; it mainly keeps local-only conveniences such as docs exposure.

## Recommended Local Env Files

Keep the default local workflow on one dotenv file:

- `.env`: local-only defaults for the checked-in Docker Compose stack and local app-process startup
- `.env.example`: checked-in template only

Create your local file with `cp .env.example .env`.
Use `APP_ENV=dev|prod` on the command line to select the runtime profile.
Only introduce `APP_SETTINGS_ENV_FILE` when you truly need an alternate dotenv file,
for example a one-off local prod-like experiment or a deployment-specific secret set.

## Compose Profiles

Docker Compose also uses profiles, but those are orchestration selectors, not app runtime modes.

Current Compose profiles include:

- `demo`: adds the demo seed job
- `test`: adds the dedicated test PostgreSQL container

The previous `observability` profile (Prometheus, Grafana, Loki) has been
removed; telemetry now flows over OTLP/HTTP directly to Grafana Cloud.
See [`observability-grafana-cloud.md`](observability-grafana-cloud.md).

These Compose profiles decide which containers run. They do not define new FastAPI behaviors or new `APP_ENV` values.

## Test and CI Environments

Tests and CI are execution environments, not runtime profiles.

- Most tests should boot the app with `APP_ENV=prod` when they need production-like behavior.
- Tests should use `APP_ENV=dev` only when they explicitly validate local-development behavior.
- The dedicated test database is selected with `TEST_DATABASE_URL`, not with a special app runtime profile.

## Common Variables

- `APP_ENV`: runtime profile for the app (`dev` or `prod`)
- `DATABASE_URL`: primary application database
- `MIGRATION_DATABASE_URL`: optional direct database URL for Alembic when the
  runtime `DATABASE_URL` uses a pooled host
- `TEST_DATABASE_URL`: dedicated database used by integration-test flows
- `AUTH_SERVICE_TOKENS_JSON`: governed service-token registry records used by authenticated routes
- `ALLOWED_HOSTS_JSON`: required host allowlist when `APP_ENV=prod`; deployed prod should include `api.aptitude-registry.dev` and the Render `onrender.com` host during rollout
- `POLICY_PROFILES_JSON`: optional named governance-profile overrides merged over the built-in default profile
- `ACTIVE_POLICY_PROFILE`: selects which policy profile is active at runtime; defaults to `default`
- `LOG_LEVEL`, `LOG_FORMAT`: logging configuration
- `OTEL_ENABLED` plus standard `OTEL_EXPORTER_OTLP_*` env vars: OpenTelemetry/Grafana Cloud configuration (see `observability-grafana-cloud.md`)
- `OPENAI_API_KEY`: required only when semantic discovery/indexing calls OpenAI
- `SEMANTIC_DISCOVERY_MODE`: `off`, `shadow`, or `hybrid`; defaults to `off`
- `SEMANTIC_EMBEDDING_PROVIDER`: embedding provider, currently `openai`
- `SEMANTIC_EMBEDDING_MODEL`: provider model sent to OpenAI, currently `text-embedding-3-small`
- `SEMANTIC_EMBEDDING_INDEX_KEY`: persisted embedding compatibility key, currently `openai:text-embedding-3-small:description-tags-v1`
- `SEMANTIC_EMBEDDING_DIMENSIONS`: fixed at `1536` for the current `halfvec(1536)` read model
- `SEMANTIC_CANDIDATE_LIMIT`: semantic candidate cap, default `20`
- `SEMANTIC_QUERY_TIMEOUT_MS`: provider query timeout, default `150`
- `SEMANTIC_HNSW_EF_SEARCH`: pgvector HNSW recall control, default `100`
- `APP_SETTINGS_ENV_FILE`: optional alternate dotenv file path for app-process startup; otherwise the app loads `.env`

Service-token settings use this JSON shape:

```json
[
  {
    "token_id": "reader-token",
    "secret_digest": "sha256-hex-of-secret",
    "scopes": ["read"],
    "namespace_grants": [
      {
        "namespace": "public",
        "roles": ["read"],
        "promotion_channels": ["prod"]
      }
    ],
    "active": true,
    "expires_at": null
  }
]
```

Clients send the raw secret only over HTTP:

```text
Authorization: Bearer reader-token.dev-reader-secret
```

Promotion channels are governance workflow state, not runtime profiles. `dev`,
`staging`, and `prod` promotion channels control enterprise visibility; they do not
create new `APP_ENV` values.

## Practical Defaults

- `make run-dev` starts the checked-in Compose stack with `APP_ENV=dev`, the `demo` profile, and the `observability` profile
- `make run-prod` starts the checked-in Compose stack with `APP_ENV=prod` and the `observability` profile
- raw `docker compose` usage defaults the checked-in app services to `APP_ENV=prod` unless you override `APP_ENV`
- deployed prod at `https://api.aptitude-registry.dev` must set `ALLOWED_HOSTS_JSON` to include `api.aptitude-registry.dev`
- the root domain `https://aptitude-registry.dev` is not an API host until a website or redirect is introduced
- `make test` manages the dedicated `test` profile database container for the full test suite
- `LOG_FORMAT=auto` prefers readable local logs in `dev` and structured JSON logs in `prod`
- app-process startup reads local `.env` unless `APP_SETTINGS_ENV_FILE` points to another dotenv file
- forwarded proxy headers stay untrusted by default; enable them explicitly at the deploy entrypoint behind a trusted proxy

## Semantic Indexing

Semantic discovery is off by default and remains optional. The app can boot
without `OPENAI_API_KEY` while `SEMANTIC_DISCOVERY_MODE=off`.

Use the local indexer for development backfills and emergency production
fallbacks:

```bash
uv run python scripts/index_semantic_embeddings.py --batch-size 25 --max-batches 1 --reclaim-after-seconds 3600
```

The checked-in indexing defaults are `--batch-size 25 --max-batches 1 --reclaim-after-seconds 3600`.
The indexer creates missing pending rows for the active
`SEMANTIC_EMBEDDING_INDEX_KEY`, claims rows as `processing`, calls OpenAI, and
then marks rows `indexed` or `failed`. Provider failures do not affect publish,
exact fetch, resolution, lifecycle changes, or lexical discovery.

Rollout order:

1. Run indexing with semantic discovery still `off`.
2. Enable `SEMANTIC_DISCOVERY_MODE=shadow` to exercise provider and SQL paths
   without changing public ordering.
3. Move to `hybrid` only after indexed-row counts, failures, and latency are
   acceptable.
4. Roll back by setting `SEMANTIC_DISCOVERY_MODE=off`; no database rollback is
   required.

In production, `render.yaml` owns the Cron trigger for the semantic indexing
Workflow task. The Workflow service itself remains configured in the Render
Dashboard while Render Blueprints lack workflow service support.
