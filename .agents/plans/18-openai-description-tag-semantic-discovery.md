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

## Scope
- Add OpenAI embedding-provider settings:
  - `OPENAI_API_KEY`
  - `SEMANTIC_EMBEDDING_PROVIDER=openai`
  - `SEMANTIC_EMBEDDING_MODEL=text-embedding-3-small`
  - `SEMANTIC_EMBEDDING_DIMENSIONS=1536`
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

### Semantic Search
Semantic search is optional expansion. It embeds description and tags only for
both indexed skill rows and discovery queries.

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

## OpenAI Provider Design
- Use the official OpenAI Python SDK unless a later implementation spike proves
  direct HTTPX is materially simpler.
- Read credentials from `OPENAI_API_KEY`.
- Treat missing credentials as a startup/configuration problem only when
  semantic mode requires a provider. `SEMANTIC_DISCOVERY_MODE=off` must not
  require an OpenAI key.
- Request `encoding_format="float"`.
- Pass the configured `model` and `dimensions`.
- Validate that returned vectors contain exactly the configured number of finite
  floats.
- Catch provider timeouts, rate limits, and malformed responses at the semantic
  boundary so discovery degrades to lexical-only behavior.
- Never log `OPENAI_API_KEY` or full provider response bodies.

## Indexing Workflow
- Publish continues to create pending semantic rows after metadata persistence.
- The indexer claims work in small batches using a PostgreSQL-safe queue pattern
  such as `FOR UPDATE SKIP LOCKED`.
- The indexer processes rows with `index_status IN ('pending', 'stale',
  'failed')` when retry policy allows it.
- For each claimed row:
  - rebuild the description/tag source text from canonical metadata
  - recompute the checksum
  - skip or mark stale if the source no longer matches the row expectation
  - call OpenAI embeddings
  - validate the vector
  - persist `embedding_vector`, `indexed_at`, and `index_status='indexed'`
  - persist `index_status='failed'` and `last_error` on provider or validation
    failure
- Indexing failure must never roll back publish success.
- Backfills must be idempotent and safe to rerun.

## Database and Neon Notes
- Keep PostgreSQL as the only runtime search store.
- Use pgvector in Neon/Postgres with `CREATE EXTENSION IF NOT EXISTS vector`.
- Keep `halfvec(1536)` and HNSW cosine indexing as the default path.
- Keep governance filters in SQL before semantic rows are returned to the
  service layer.
- Monitor HNSW index size and p95/p99 discovery latency before increasing
  candidate limits or `hnsw.ef_search`.

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
1. Ship provider and indexing code with `SEMANTIC_DISCOVERY_MODE=off`.
2. Run local/manual backfill against a small dataset.
3. Deploy indexing workflow with semantic discovery still off.
4. Enable `SEMANTIC_DISCOVERY_MODE=shadow` and observe provider failures,
   indexing lag, query latency, and semantic candidate coverage.
5. Enable `SEMANTIC_DISCOVERY_MODE=hybrid` only after shadow mode proves lexical
   fallback and governance filtering are reliable.
6. Keep the ability to return to `off` without a database rollback.

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

## Acceptance Criteria
- The app can run without `OPENAI_API_KEY` when semantic discovery is off.
- With `OPENAI_API_KEY` configured, the provider can create valid
  1536-dimensional embeddings for description/tag text.
- The indexing workflow can turn pending rows into indexed pgvector rows.
- `POST /discovery` remains available and lexical-only when the provider fails.
- `shadow` mode exercises semantic retrieval without changing public results.
- `hybrid` mode adds governed semantic recall candidates without changing the
  public response shape.
- Documentation clearly explains what lexical search does, what semantic search
  does, and why full skill content is not embedded.
