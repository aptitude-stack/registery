# Plan 18 - OpenAI Description/Tag Semantic Discovery

## Goal
Turn the existing semantic-discovery plumbing from Plan 17 into a fully
operating OpenAI-backed embedding and semantic-search path, while narrowing the
semantic source text to skill descriptions and tags only.

## Positioning
This is a planning-only milestone. It does not implement semantic search, change
runtime configuration, modify migrations, update tests, or update canonical
discovery documentation by itself.

Plan 17 introduced the optional pgvector read model and lexical-primary fusion
surface, but the default application container still has no concrete embedding
provider and no production indexing workflow. Plan 18 defines the missing
operating layer for provider-backed embeddings, indexing, rollout, and
documentation.

## Strategic Role
Semantic discovery should improve recall for approved catalog skills without
weakening the registry boundary. The registry still performs governed candidate
generation only. It does not become the resolver, final reranker, execution
planner, or agentic search runtime.

Description/tag-only embeddings keep semantic matching focused on what a skill
does and how it is categorized. Slug and name remain lexical identity signals
for exact and near-exact lookup, not embedding input.

## Relationship to Earlier Plans

### Builds On Implemented Plans
- Plan 05 established metadata-centric lexical discovery through
  `skill_search_documents`.
- Plan 09 froze the public route set and kept discovery inside
  `POST /discovery`.
- Plan 14 established production security and service-token posture.
- Plan 17 added `skill_search_embeddings`, pgvector candidate retrieval,
  lexical-primary fusion, semantic rollout modes, and co-usage ranking signals.

### What This Plan Refines
- It narrows Plan 17's semantic source from `slug`, `name`, `description`, and
  `tags` to `description` and `tags` only.
- It converts the internal `EmbeddingProviderPort` from an unwired seam into a
  concrete OpenAI-backed provider.
- It adds an operational indexing workflow so pending and stale embedding rows
  can become indexed vectors.
- It makes the discovery model explicit in documentation so lexical identity
  search, structured tag filtering, and semantic expansion have clear
  responsibilities.

## Stack Alignment
- Runtime: Python 3.12+
- API and contracts: FastAPI + Pydantic v2
- Data layer: SQLAlchemy 2.0 + Alembic
- Database: PostgreSQL with pgvector, including Neon-hosted Postgres
- Embedding provider: OpenAI embeddings API via `OPENAI_API_KEY`
- Default model: `text-embedding-3-small`
- Default vector shape: `1536` dimensions, stored as `halfvec(1536)`
- Background execution: Render Workflow for production indexing, triggered by
  Render Cron because Workflows do not provide built-in scheduling
- Current external references for implementation:
  - OpenAI embeddings guide: `https://platform.openai.com/docs/guides/embeddings`
  - OpenAI `text-embedding-3-small` model page:
    `https://platform.openai.com/docs/models/text-embedding-3-small`
  - Neon AI concepts / pgvector support:
    `https://neon.com/docs/ai/ai-concepts`
  - Neon supported extensions:
    `https://neon.com/docs/extensions/extensions-intro`

## Scope
- Add OpenAI embedding-provider settings:
  - `OPENAI_API_KEY`
  - `SEMANTIC_EMBEDDING_PROVIDER=openai`
  - `SEMANTIC_EMBEDDING_MODEL=text-embedding-3-small`
  - `SEMANTIC_EMBEDDING_INDEX_KEY=openai:text-embedding-3-small:description-tags-v1`
  - `SEMANTIC_EMBEDDING_DIMENSIONS=1536`
- Keep a strict distinction between:
  - provider model name sent to OpenAI: `text-embedding-3-small`
  - persisted embedding index key stored in `skill_search_embeddings.embedding_model`:
    `openai:text-embedding-3-small:description-tags-v1`
- Wire an OpenAI implementation of `EmbeddingProviderPort`.
- Keep `SEMANTIC_DISCOVERY_MODE=off|shadow|hybrid` as the rollout control.
- Build semantic source text only from:
  - normalized `metadata.description`
  - normalized `metadata.tags`
- Exclude from semantic embeddings:
  - slug
  - name
  - README or markdown body text
  - bundled skill files
  - raw artifact contents
- Add an embedding indexing service that processes pending or stale
  `skill_search_embeddings` rows and records indexed vectors or failures.
- Add a Render Workflow task for production embedding indexing.
- Keep a local command or script entrypoint for manual backfill and development
  verification using the same indexing service.
- Update the canonical discovery/ranking documentation during implementation to
  explain the final search model clearly.

## Architecture Decisions
- Keep the provider behind `EmbeddingProviderPort`; do not let OpenAI SDK calls
  leak into API routers, repository code, or SQL helpers.
- Keep query-time embedding generation inside the discovery service boundary,
  under the existing semantic timeout budget.
- Keep index-time embedding generation in a separate application service that
  depends on repository/indexing ports and the same provider abstraction.
- Keep `skill_search_embeddings` as a derived read model. It is rebuildable and
  never the authoritative skill catalog.
- Do not couple publish transactions to OpenAI availability. Publish may create
  or update pending rows, but vector generation remains post-commit work.
- Treat the persisted embedding index key as the compatibility boundary. Any
  future source change, model change, provider change, or dimension change must
  use a new key or an explicit migration/backfill plan.

## Non-Goals
- No new public semantic-search route.
- No public vector-score, explanation, or debug endpoint.
- No change to the public `POST /discovery` response shape.
- No full-skill, README, markdown, or artifact-content embedding.
- No LLM traversal or agentic search loop inside the request path.
- No resolver-side final choice, lock generation, recursive solving, or
  execution-planning behavior in the registry.
- No co-usage redesign; preserve the Plan 17 co-usage behavior unless a later
  plan changes it.

## Search and Discovery Model

### Lexical Search
Lexical search remains the always-on baseline. It searches the derived
`skill_search_documents` model built from slug, name, description, and tags.

Lexical search owns:
- exact slug lookup
- exact name lookup
- substring slug/name matching
- full-text matching over metadata
- deterministic base ordering

### Structured Tags
Tags remain structured filters when supplied in discovery requests. If a caller
requests tags, matching candidates must contain those normalized tags. Semantic
similarity must not turn requested tags into soft preferences.

Tags therefore have two roles:
- hard filter when supplied as `tags` in the discovery request
- semantic source text when persisted as part of a skill's metadata

### Semantic Search
Semantic search is optional expansion. It embeds description and tags only for
both indexed skill rows and discovery queries.

The semantic query source is:
- normalized discovery `description`, if present
- normalized discovery `tags`, if present

The required discovery `name` is not semantic input. If a request has only
`name` and no description or tags, semantic expansion is skipped even when
`SEMANTIC_DISCOVERY_MODE` is `shadow` or `hybrid`.

Semantic search owns:
- recovering semantically similar candidates when wording differs
- adding bounded recall candidates in `hybrid` mode
- running in `shadow` mode for rollout observation without changing returned
  ordering

Semantic search does not own:
- exact identity matching
- final resolver choice
- lifecycle or trust visibility
- dependency truth

### Fusion
Fusion remains lexical-primary:
1. exact slug match
2. exact name match
3. lexical-primary fused score
4. bounded semantic recall signal
5. existing deterministic tie-breakers

Raw vector distance must not be exposed publicly and must not be compared
directly against lexical scores as a standalone global relevance score.

### Failure Behavior
- Missing provider configuration in `off` mode must not block app startup.
- Missing provider configuration in `shadow` or `hybrid` must fail startup
  clearly, because the selected mode cannot operate as configured.
- Provider timeouts, rate limits, invalid vectors, or SQL vector-query failures
  during a request must degrade that request to lexical-only results.
- Indexing failures must mark rows failed and must not affect publish, exact
  fetch, resolution, lifecycle changes, or lexical discovery.

## OpenAI Provider Design
- Use the official OpenAI Python SDK as a runtime dependency.
- Read credentials from `OPENAI_API_KEY`.
- Treat missing credentials as a startup/configuration problem only when
  semantic mode requires a provider. `SEMANTIC_DISCOVERY_MODE=off` must not
  require an OpenAI key.
- Request `encoding_format="float"`.
- Pass the configured `model` and `dimensions`.
- Validate that returned vectors contain exactly the configured number of finite
  floats.
- Use one embedding input per call for query-time embedding.
- Permit batch embedding only in the indexing service, where provider rate
  limits and partial failures can be handled without user-facing latency.
- Catch provider timeouts, rate limits, and malformed responses at the semantic
  boundary so discovery degrades to lexical-only behavior.
- Never log `OPENAI_API_KEY` or full provider response bodies.
- Log only sanitized provider metadata: provider name, configured model,
  dimensions, input count, elapsed time, success/failure class, and row counts.

## Indexing Workflow
- Publish continues to create pending semantic rows after metadata persistence.
- The indexer claims work in small batches using a PostgreSQL-safe queue pattern
  such as `FOR UPDATE SKIP LOCKED`.
- The indexer processes rows with `index_status IN ('pending', 'stale')`.
- Failed rows are retried only by an explicit retry/backfill mode in the first
  implementation. Do not blindly retry failed rows on every scheduled run.
- For each claimed row:
  - rebuild the description/tag source text from canonical metadata
  - recompute the checksum
  - skip empty sources and mark them failed with a non-secret reason such as
    `empty semantic source`
  - mark rows stale if the source checksum no longer matches the row expectation
  - call OpenAI embeddings
  - validate the vector
  - persist `embedding_vector`, `indexed_at`, and `index_status='indexed'`
  - persist `index_status='failed'` and `last_error` on provider or validation
    failure
- Indexing failure must never roll back publish success.
- Backfills must be idempotent and safe to rerun.
- The first implementation should avoid adding a new queue table. Use the
  existing `skill_search_embeddings` status fields unless implementation proves
  that retry scheduling requires more state.

### Source Migration and Backfill
Plan 17 pending rows may have checksums based on slug/name/description/tags.
Plan 18 changes the source definition. Implementation must include a deliberate
backfill path:

- Insert or update rows using
  `SEMANTIC_EMBEDDING_INDEX_KEY=openai:text-embedding-3-small:description-tags-v1`.
- Treat any prior `metadata-1536-v1` or slug/name-based rows as obsolete for
  Plan 18 semantic retrieval.
- Do not reuse the old `embedding_model` key for the new description/tag source.
- Provide a local backfill command that can create pending Plan 18 rows for all
  eligible published skill versions.
- Make the query path request only the Plan 18 index key so mixed old and new
  semantic rows cannot affect ranking.

## Database and Neon Notes
- Keep PostgreSQL as the only runtime search store.
- Use pgvector in Neon/Postgres with `CREATE EXTENSION IF NOT EXISTS vector`.
- Neon currently documents pgvector support and supported extension version
  `0.8.0` for recent Postgres versions; verify this against Neon docs before
  implementation if the production project version changes.
- Keep `halfvec(1536)` and HNSW cosine indexing as the default path.
- Keep the current partial HNSW shape:
  `WHERE embedding_vector IS NOT NULL AND index_status = 'indexed'`.
- Keep governance filters in SQL before semantic rows are returned to the
  service layer.
- Cast query vectors explicitly to `halfvec(1536)` so prepared statements do not
  rely on implicit vector casts.
- Use the cosine operator `<=>` to match the `halfvec_cosine_ops` index.
- Keep `SET LOCAL hnsw.ef_search = :value` inside the semantic query
  transaction, with a bounded setting such as the existing
  `SEMANTIC_HNSW_EF_SEARCH`.
- Add or preserve B-tree indexes that support queue claiming and filters before
  tuning ANN settings. At minimum, the existing `(embedding_model,
  index_status)` index must remain.
- If filtered semantic queries return too few candidates, prefer measured
  over-fetching or pgvector iterative scan over weakening governance filters.
- Monitor HNSW index size and p95/p99 discovery latency before increasing
  candidate limits or `hnsw.ef_search`.

### Neon Connection Boundaries
- Runtime app connections may use the pooled Neon host if the current app
  configuration supports it.
- Alembic migrations, extension creation, and HNSW index maintenance must use a
  direct Neon connection, not the PgBouncer `-pooler` host.
- Render Workflow indexers should use the same database URL policy as the app:
  pooled for ordinary short transactions only if safe, direct for maintenance
  or migration-like work.
- Document `MIGRATION_DATABASE_URL` or equivalent direct-connection use when
  implementation touches migrations or extension/index maintenance.

## Render Workflow Notes
- Add a Python Render Workflow task for embedding indexing when implementation
  begins.
- Use a Render Cron job to trigger the workflow on a schedule.
- Keep Workflow arguments JSON-serializable and small, such as batch size and
  maximum retry count.
- Configure production environment variables in Render:
  - `DATABASE_URL`
  - `OPENAI_API_KEY`
  - semantic discovery/indexing settings
- Treat Render Workflows as beta; keep the local CLI indexing path as the stable
  fallback.

## Rollout Plan
1. Add settings, source construction, provider, and tests with
   `SEMANTIC_DISCOVERY_MODE=off`.
2. Add indexing service and local backfill command.
3. Run local/manual backfill against a small dataset.
4. Deploy Render Workflow indexing with semantic discovery still off.
5. Backfill production Plan 18 rows under the new embedding index key.
6. Enable `SEMANTIC_DISCOVERY_MODE=shadow` and observe provider failures,
   indexing lag, query latency, candidate coverage, and exact-match stability.
7. Enable `SEMANTIC_DISCOVERY_MODE=hybrid` only after shadow mode proves lexical
   fallback and governance filtering are reliable.
8. Keep the ability to return to `off` without a database rollback.

## Observability and Operations
- Track indexed, pending, stale, and failed embedding row counts by embedding
  index key.
- Track indexing batch duration, rows claimed, rows indexed, rows failed, and
  provider failure classes.
- Track query-time semantic provider latency and semantic fallback count.
- Track semantic SQL latency separately from lexical discovery latency.
- Add an operation note for responding to:
  - OpenAI outage or rate limiting
  - indexing backlog growth
  - unexpectedly high HNSW query latency
  - failed-row accumulation
  - rollback from `hybrid` to `shadow` or `off`

## Required Documentation Updates During Implementation
- Update `docs/architecture/discovery-and-ranking.md` to define lexical search,
  structured tag filters, description/tag semantic search, and fusion.
- Update runtime or contributor docs with `OPENAI_API_KEY`, semantic settings,
  local indexing command, Render Workflow operation, and rollout modes.
- Update schema docs if implementation changes any table, index, or status
  semantics beyond Plan 17.
- Add a milestone changelog after implementation is complete.

## Verification Requirements
Implementation must follow TDD:
- write failing tests first
- verify the failure is for the intended missing behavior
- implement the minimal code
- verify green before refactoring

Required test coverage:
- embedding source uses description and tags only
- slug/name changes do not change the semantic source checksum
- description/tag changes do change the semantic source checksum
- missing or blank description/tags skip semantic query embedding
- OpenAI provider sends model, dimensions, input, and timeout
- wrong-dimension or non-finite provider responses are rejected
- provider failure falls back to lexical-only discovery
- pending/stale rows can be indexed
- provider failures mark rows failed without affecting publish
- semantic SQL still applies lifecycle, trust, namespace, review, promotion, and
  tag filters before returning candidates
- shadow mode calls semantic retrieval without changing returned lexical order
- hybrid mode can add semantic recall candidates after lexical candidates
- old Plan 17 slug/name-based semantic rows are ignored when the Plan 18 index
  key is active
- Neon migration/index maintenance guidance rejects pooled migration URLs when
  direct connections are required

## Acceptance Criteria
- The app can run without `OPENAI_API_KEY` when semantic discovery is off.
- With `OPENAI_API_KEY` configured, the provider can create valid
  1536-dimensional embeddings for description/tag text.
- The indexing workflow can turn pending rows into indexed pgvector rows.
- Backfill can create Plan 18 pending rows without relying on slug/name source
  text.
- `POST /discovery` remains available and lexical-only when the provider fails.
- `shadow` mode exercises semantic retrieval without changing public results.
- `hybrid` mode adds governed semantic recall candidates without changing the
  public response shape.
- Documentation clearly explains what lexical search does, what semantic search
  does, and why full skill content is not embedded.
