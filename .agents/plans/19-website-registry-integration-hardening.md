# Website Registry Integration Hardening Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make the Vercel website survive registry outages/misconfiguration, align its UI with the registry contract, reduce search fanout, and bound registry readiness failures.

**Architecture:** Add one registry-owned `POST /catalog/search` endpoint that accepts the existing discovery request body and returns card-ready skill metadata in one request. Harden the website registry client with timeouts and graceful fallbacks. Bound database readiness pings so Render `/readyz` returns `503` instead of hanging.

**Tech Stack:** Next.js 16, React 19, TypeScript/Jest, FastAPI/Pydantic, SQLAlchemy/Postgres/Neon, Render, Vercel.

---

## Key Interface Changes

- Add public registry endpoint: `POST /catalog/search`
  - Request: same JSON as `POST /discovery`: `{ name, description?, tags?, context_skills? }`
  - Query: optional `limit`, default `20`, max `20`
  - Response: reuse `TopSkillsResponse` shape: `{ "skills": SkillVersionMetadataResponse[] }`
- Keep `POST /discovery` unchanged and discovery-only.
- Website uses:
  - `GET /catalog/top-skills` for homepage top skills
  - `POST /catalog/search` for search results
  - exact metadata/content endpoints only on skill detail pages

---

## Implementation Tasks

### Task 1: Website Fallback And Timeout Safety

**Files:**
- Modify `website/src/lib/registry-client.ts`
- Modify `website/src/app/page.tsx`
- Test `website/src/lib/__tests__/registry-client.test.ts`

- [x] Add a `REGISTRY_FETCH_TIMEOUT_MS = 5000` constant and a helper that wraps each registry fetch in `AbortController`.
- [x] Ensure all registry JSON and content fetches use the timeout.
- [x] Add `fetchTopSkillCardsSafe(limit = 12): Promise<SkillCardData[]>` that returns `[]` for missing env, invalid env, timeout, non-OK registry response, or malformed registry response.
- [x] Change the homepage to call `fetchTopSkillCardsSafe(12)` so production never renders HTTP 500 just because registry data is unavailable.
- [x] Add Jest tests for:
  - missing `REGISTRY_BASE_URL` / `REGISTRY_READ_TOKEN` returns empty top skills
  - registry `500` returns empty top skills
  - aborted/timeout fetch returns empty top skills
  - strict `registryFetch` still throws for callers that need fail-fast behavior

### Task 2: Align Website Trust Tiers With Registry Contract

**Files:**
- Modify `website/src/lib/types.ts`
- Modify `website/src/components/skill-card.tsx`
- Modify `website/src/components/skill-header.tsx`
- Modify website tests using `trusted` / `community`

- [x] Add narrow TypeScript unions for registry enums used by the website:
  - `TrustTier = "untrusted" | "internal" | "verified"`
  - `LifecycleStatus = "published" | "deprecated" | "archived"`
- [x] Replace `trusted/community` UI mapping with:
  - `verified -> trust-verified`
  - `internal -> trust-internal`
  - `untrusted -> trust-untrusted`
- [x] Update CSS class names or keep aliases only if existing styling reuse is cleaner.
- [x] Update all website fixtures from `trusted` to valid registry values, preferably `verified` for positive/trusted examples and `untrusted` for default examples.
- [x] Add component tests proving `verified`, `internal`, and `untrusted` render distinct classes.

### Task 3: Add Registry `POST /catalog/search`

**Files:**
- Modify `registry/app/core/skills/fetch.py`
- Modify `registry/app/interface/api/fetch.py`
- Modify `registry/app/interface/dto/skills_fetch.py`
- Test `registry/tests/unit/test_skill_fetch_service.py`
- Test `registry/tests/integration/test_exact_fetch_endpoints.py`
- Test `registry/tests/unit/test_registry_api_boundary.py`

- [x] Add `SkillFetchService.search_catalog(caller, request, limit)` that reuses discovery/search behavior but returns visible current-default `SkillVersionDetail` records.
- [x] Keep visibility filtering identical to `list_top_installed`.
- [x] Return at most `limit`, default `20`, max `20`.
- [x] Add route `POST /catalog/search` with `SkillDiscoveryRequest` body and `TopSkillsResponse` response.
- [x] Do not change `/discovery` behavior or response shape.
- [x] Add tests for:
  - search returns metadata cards in discovery order
  - archived/non-visible candidates are filtered out
  - max limit validation rejects values above `20`
  - OpenAPI contains `/catalog/search`
  - `/discovery` still returns only slug strings

### Task 4: Switch Website Search To One Registry Call

**Files:**
- Modify `website/src/lib/registry-client.ts`
- Modify `website/src/app/api/search/route.ts`
- Test `website/src/app/api/search/__tests__/route.test.ts`

- [x] Add `searchSkillCards(query: string): Promise<SkillCardData[]>` that calls `POST /catalog/search?limit=20`.
- [x] Replace current `/api/search` fanout path:
  - remove `discoverSlugs(query)`
  - remove per-slug `fetchSkillCardData`
  - return the registry-provided card list directly
- [x] Keep browser API response unchanged: `{ candidates: SkillCardData[] }`
- [x] Keep `/api/search` validation unchanged: invalid JSON, missing query, blank query, and query length > 200 return `400`.
- [x] Add tests proving one browser search causes exactly one registry fetch.

### Task 5: Bound Registry Database Readiness

**Files:**
- Modify `registry/app/core/settings.py`
- Modify `registry/app/persistence/db.py`
- Test `registry/tests/unit/test_db_engine.py`
- Test `registry/tests/integration/test_health_endpoints.py`

- [x] Add setting `DATABASE_CONNECT_TIMEOUT_SECONDS`, default `5`, range `1..30`.
- [x] Pass it to SQLAlchemy/psycopg `connect_args` during `init_engine`.
- [x] Preserve existing `application_name` connect arg.
- [x] Ensure `/readyz` still returns:
  - `200` when `SELECT 1` succeeds
  - `503` with database error detail when connection fails
- [x] Add a unit test that engine creation includes both `application_name` and `connect_timeout`.

### Task 6: Docs And Deployment Contract

**Files:**
- Modify `website/README.md`
- Modify `website/.env.local.example`
- Modify `registry/docs/architecture/render-neon-deployment.md`
- Modify `registry/.env.example` if it documents runtime DB settings

- [x] Document website production env vars in Vercel:
  - `REGISTRY_BASE_URL=https://api.aptitude-registry.dev`
  - `REGISTRY_READ_TOKEN=<read token>`
- [x] Document that the website degrades to an empty catalog instead of failing the whole page when the registry is unavailable.
- [x] Document `POST /catalog/search` as the website search integration endpoint.
- [x] Document `DATABASE_CONNECT_TIMEOUT_SECONDS=5` for Render runtime and why it protects `/readyz`.

---

## Test Plan

- Website:
  - `npm run typecheck`
  - `npm test -- --runInBand`
  - `npm run build` or `bun run build` when Bun is available and sandbox permits Turbopack worker ports
- Registry:
  - `uv --cache-dir .uv-cache run --extra dev pytest tests/unit/test_skill_fetch_service.py tests/unit/test_db_engine.py tests/unit/test_registry_api_boundary.py -q`
  - `uv --cache-dir .uv-cache run --extra dev pytest tests/integration/test_exact_fetch_endpoints.py tests/integration/test_health_endpoints.py -q`
  - Full gate if local Postgres is available: `make quality && make test`
- Live verification after deploy:
  - `curl -i --max-time 20 https://api.aptitude-registry.dev/healthz`
  - `curl -i --max-time 20 https://api.aptitude-registry.dev/readyz`
  - Open `https://aptitude-registry.dev/` and confirm it does not return HTTP 500 when registry search/top-skill calls fail.

---

## Assumptions

- Test edits are approved for this plan.
- Public website failure behavior should degrade gracefully, not fail closed.
- New registry endpoint is additive; no breaking change to existing `/discovery` or exact fetch contracts.
- Vercel env/log inspection may require account permission fixes because the current connector returned `403 Forbidden`.
- The plan document should be saved during execution as `registry/docs/superpowers/plans/2026-05-14-website-registry-integration-hardening.md` or equivalent repo-owned plan path; no file is written while still in Plan Mode.
