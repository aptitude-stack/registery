# Plan 17 - Redis L1 Caching Over PostgreSQL Read Models

## Summary
Add a bounded, optional Redis read cache across all registry read surfaces while keeping PostgreSQL as the only authoritative store and the existing Postgres read models as the canonical server-side query acceleration layer.

This milestone caches:
- `POST /discovery`
- `GET /skills/{slug}`
- `GET /skills/{slug}/{version}`
- `GET /skills/{slug}/{version}/content`
- `GET /resolution/{slug}/{version}`

This milestone does not add new public routes or change response shapes. Redis is optional and best-effort. If Redis is unavailable or disabled, the app must continue to function correctly against PostgreSQL only.

## Strategic Role
Redis caching supports the enterprise moat by making governed reads predictable,
cheap, and operationally trustworthy under repeated resolver and gateway
traffic. It is reliability and cost-control infrastructure for immutable exact
reads and bounded discovery, not product differentiation by itself.

The cache must remain optional, bounded, and non-authoritative. PostgreSQL stays
the source of truth for registry facts, trust state, lifecycle, audit, and
artifact identity.

## Key Changes
- Add cache configuration to `Settings`:
    - `REDIS_URL` optional
    - `CACHE_ENABLED` default `true`
    - `CACHE_DISCOVERY_TTL_SECONDS` default `60`
    - `CACHE_LIST_TTL_SECONDS` default `300`
    - `CACHE_RESOLUTION_TTL_SECONDS` default `300`
    - `CACHE_METADATA_TTL_SECONDS` default `3600`
    - `CACHE_CONTENT_TTL_SECONDS` default `3600`
    - `CACHE_MAX_CONTENT_BYTES` default `1048576` (1 MiB); larger artifacts bypass Redis content caching
- Introduce internal cache ports/adapters instead of putting Redis logic in FastAPI handlers:
    - cache backend abstraction
    - cached decorators for `SkillSearchPort`, `SkillVersionReadPort`, and relationship/exact-read ports
    - service container wiring that wraps the existing SQLAlchemy repository when Redis is configured
- Keep PostgreSQL as the authoritative and fallback data path:
    - do not add a generic Postgres cache table
    - continue using existing derived Postgres read models such as `skill_search_documents`
    - tighten/query-shape documentation around those Postgres read models as the PG side of the caching story
- Cache key design must be governance-safe:
    - exact-read keys include `slug`, `version`, policy profile, and effective caller visibility class
    - discovery keys include normalized query text, normalized tags, limit, effective lifecycle filters, and effective trust-tier filters
    - identity-list and resolution keys include the same policy dimensions that affect visibility
- Invalidation must be mutation-driven, not TTL-only:
    - on publish: invalidate skill list for the slug, discovery namespace, and exact/read keys for the new coordinate
    - on lifecycle/status change: invalidate exact metadata/content, resolution, skill list, and discovery namespace keys affected by that coordinate
    - use namespace-version keys in Redis to avoid unsafe wildcard deletes
- Move install counting off the exact-content hot path:
    - exact content fetch returns immediately after governance and content retrieval
    - install increments run as post-response best-effort background work
    - Postgres remains the source of truth for persisted `install_count`
    - discovery ranking and metadata responses accept eventual consistency for `install_count`
- Add observability for cache behavior:
    - hit/miss/error counters by surface
    - cache latency histogram
    - bypass counters for oversized content and disabled/unavailable Redis
    - log cache fallback events at warning level only when the failure is persistent/noisy enough to matter

## Public/Internal Interface Changes
- No public API contract changes.
- Internal configuration/environment changes:
    - add the Redis/cache settings above to `app/core/settings.py`
    - add local Docker support for an optional Redis service/profile and document that the stack works without it
- Internal service graph changes:
    - `build_service_container()` becomes responsible for selecting either direct Postgres ports or cached decorators
    - fetch/search/resolution services continue depending on ports, not Redis clients
- Internal behavior changes:
    - exact content reads become eventually consistent for `install_count`
    - exact metadata/content semantics remain immutable and cache-safe

## Test Plan
- Unit tests for cache-key normalization:
    - same logical discovery request yields same key
    - governance-visible differences yield different keys
    - exact-read keys do not leak across policy profiles or caller visibility classes
- Unit tests for cached decorators:
    - cache miss reads Postgres and stores value
    - cache hit avoids Postgres
    - Redis errors fall back to Postgres without failing the request
    - oversized content bypasses Redis content caching
- Unit tests for invalidation:
    - publish invalidates slug list and discovery namespace
    - lifecycle patch invalidates exact/read/list/discovery keys for affected coordinates
- API/integration tests:
    - response bodies and headers stay unchanged with caching enabled
    - exact content still returns correct `ETag`, `Cache-Control`, and `Content-Length`
    - discovery/list/metadata/resolution reflect publish and status changes after invalidation
    - app remains fully functional with Redis disabled
- Behavioral tests for install counting:
    - content fetch no longer performs the synchronous counter write before response completion
    - eventual install-count persistence still updates discovery ranking inputs and metadata output on a later read cycle

## Assumptions And Defaults
- Redis is a shared optional L1 cache, not a required dependency and not an authority.
- PostgreSQL remains the only source of truth; no cross-store write coordination is introduced.
- No `LISTEN/NOTIFY`, pub/sub invalidation bus, or generic Postgres cache table is added in v1 of this milestone.
- Exact content caching in Redis is intentionally bounded by artifact size to avoid turning Redis into blob storage.
- Eventual consistency for `install_count` is acceptable because it is an advisory ranking/metadata signal, not a correctness boundary.
