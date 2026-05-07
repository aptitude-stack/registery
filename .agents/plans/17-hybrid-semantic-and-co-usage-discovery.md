# Plan 17 - Lexical-Primary Semantic Expansion and Co-Usage Discovery Signals

## Goal
Add a post-launch semantic candidate-expansion layer to `POST /discovery`
using PostgreSQL `pgvector`, while keeping deterministic lexical discovery as
the primary ranking model. Also introduce a bounded statistical signal for
"commonly used together" skills that can improve advisory ranking when caller
context exists, without changing the server/resolver boundary or the frozen
public route set.

## Positioning
This milestone is post-launch and optional. It is not part of MVP readiness,
read-contract reset, contract freeze, release hardening, or auth-boundary work.

This plan extracts a concrete implementation path from the broader optional
discovery bucket: semantic retrieval and co-usage ranking signals should be
implemented here rather than folded loosely into generic evaluation work.
It assumes the summary unification cleanup is already complete, with
`metadata.description` as the only canonical short-text field.

## Strategic Role
Lexical-primary semantic expansion and co-usage signals improve governed reuse
and progressive disclosure inside an enterprise catalog. They help consumers
find approved capabilities without turning the registry into the final decision
maker.

This is a moat enabler, not the moat itself. Discovery quality only matters when
it is subordinate to trust tier, lifecycle state, policy visibility, and
approved catalog scope. Relevance must never admit artifacts that governance
would otherwise hide or reject.

## Relationship to Earlier Plans

### Builds On Implemented Plans
- Plan 05 established the lexical `skill_search_documents` read model and the
  rule that discovery remains metadata-centric and body-free.
- Plan 08 finalized PostgreSQL as the only runtime store and kept discovery off
  raw content rows by default.
- Plan 09 froze the public route set and the rule that discovery stays inside
  `POST /discovery`.
- Plan 10 finalized governance expectations that discovery must respect
  lifecycle and trust filtering inside the server.

### What This Plan Overwrites or Supersedes
- It overwrites the implicit assumption from the lexical-search milestone that
  `skill_search_documents` is the only discovery retrieval model. After this
  plan, lexical search remains the baseline but no longer the only candidate
  source.
- It supersedes any post-Plan-05 reading that discovery ranking is purely
  `tsvector`-based. Ranking remains lexical-primary, with optional semantic
  expansion and bounded co-usage boosts, while preserving exact-match
  precedence and deterministic tie-breakers.
- It extends the PostgreSQL-only storage direction from Plan 08 by adding new
  derived PostgreSQL read models such as `skill_search_embeddings` and
  co-usage aggregates. It does not reopen the decision to keep PostgreSQL as the
  only runtime store.
- It preserves the Plan 09 route freeze and explicitly rejects any alternative
  interpretation that semantic search requires a sibling route, debug route, or
  public vector-score API.
- It preserves the governance rules from Plans 06 and 10 but overwrites any
  interpretation that governance only applies to lexical retrieval; the same
  policy filters must apply to semantic and co-usage-enhanced discovery.
- It does not overwrite canonical dependency semantics. Co-usage signals are
  advisory and must not replace authored dependency declarations or exact
  resolution behavior from earlier implemented plans.

## Stack Alignment
- Runtime: Python 3.12+
- API and contracts: FastAPI + Pydantic v2
- Data layer: SQLAlchemy 2.0 + Alembic
- Database: PostgreSQL as the only authoritative runtime store
- Vector indexing: PostgreSQL `pgvector`
- Background execution: APScheduler for low-volume indexing, with queue-backed
  workers only if observed scale requires it

## Recommended Architecture
- Keep lexical retrieval from `skill_search_documents` as the always-on primary
  ranking path.
- Add semantic retrieval as a second, additive, best-effort candidate expansion
  source.
- Keep embeddings in a separate derived table so lexical and semantic indexing
  can evolve independently.
- Generate embeddings asynchronously after publish commit so immutable publish
  success never depends on model-service availability.
- Keep statistical co-usage signals derived and rebuildable. They must inform
  candidate ranking only and must never become a canonical dependency source.
- Do not implement agentic or LLM-driven traversal in the server request path.
  Discovery must remain data-local, bounded, auditable, and deterministic under
  fallback.
- Enforce governance eligibility before relevance. Trust tier, lifecycle,
  policy, and approved visibility constraints define the candidate universe;
  lexical, semantic, and co-usage ranking only order eligible candidates.

## Scope
- Add a `pgvector`-backed semantic expansion layer for `POST /discovery`.
- Keep semantic retrieval metadata-centric by embedding:
  - `slug`
  - `name`
  - `description`
  - `tags`
- Keep zip bundle contents out of the first semantic-search version. Semantic
  retrieval remains metadata-centric and must not depend on unpacking or
  embedding bundle files during request handling.
- Add a new derived read model, recommended as `skill_search_embeddings`, with:
  - `skill_version_fk`
  - `embedding_model`
  - `embedding_dimensions`
  - `source_checksum_digest`
  - `embedding_vector`
  - `index_status`
  - `indexed_at`
  - `created_at`
  - `last_error`
- Add deterministic lexical-primary retrieval flow:
  - lexical retrieval
  - optional semantic expansion
  - candidate union
  - lexical-biased deterministic fusion
  - per-slug collapse
  - final ordering and limit
- Use lexical-biased Reciprocal Rank Fusion (RRF), or an equivalent
  deterministic fusion rule, to combine lexical and semantic candidate ranks
  instead of comparing raw cosine distance directly with lexical scores.
- Keep exact slug match and exact name match above fused semantic relevance.
- Add a derived co-usage statistics layer for skills that are commonly used
  together.
- Model co-usage as advisory relationship strength, not as a replacement for
  authored dependency declarations.
- Keep all semantic and co-usage improvements inside `POST /discovery` and the
  existing discovery internals; do not add new public discovery route families.

## Non-Goals
- No new public semantic-search route.
- No server-side final selection, reranking policy ownership, solving, lock
  generation, or execution planning.
- No agent-based search or internal LLM traversal in the discovery request path.
- No embedding of full zip bundle contents or unpacked bundle files in the
  first version.
- No requirement that semantic retrieval be available for discovery to succeed.
- No treatment of co-usage statistics as authoritative install, dependency, or
  compatibility data.

## Semantic Retrieval Design

### Retrieval Shape
- `POST /discovery` continues to accept the existing request shape by default.
- Query normalization remains the current lexical normalization path.
- If query text is empty, skip semantic retrieval.
- If semantic retrieval is enabled and query text exists:
  - generate one query embedding under a strict timeout budget
  - fetch top semantic candidates from `skill_search_embeddings`
  - union those candidates with lexical results
  - apply lexical-biased deterministic fusion and existing tie-breakers
- Lexical retrieval remains mandatory.
- Semantic retrieval is thin, bounded, best-effort, and must degrade cleanly to
  lexical-only behavior.

### Ranking Rules
Recommended fused ordering:
1. exact slug match
2. exact name match
3. lexical-primary fused score
4. `tag_overlap_count`
5. `usage_count`
6. newer `published_at`
7. smaller bundle size or derived content footprint field, once Plan 12's
   bundle-oriented metadata summary is finalized
8. lexical `slug`
9. higher internal version id

### Filtering and Governance
- Semantic retrieval must honor the same server-enforced filters as lexical
  search:
  - lifecycle visibility
  - trust tier
  - freshness window
  - max bundle size or derived artifact-size limit
  - required tags
- Forbidden candidates must not be admitted by semantic retrieval and merely
  pruned later in Python.
- If ANN behavior performs poorly under selective filters, over-fetch
  candidates inside a governance-safe SQL path and then apply deterministic
  ranking over the eligible subset.

## Co-Usage Statistics Design

### Recommendation
Add a separate derived statistics pipeline for skills that are commonly used
together. This should be a ranking signal, not an independent retrieval source
in the first version.

### Data Model Direction
Recommended derived tables:

- `skill_usage_observations`
  - append-only or replayable observation log
  - source examples: resolver lock snapshots, curated bundle exports, or other
    explicit post-selection signals
  - must not be inferred from arbitrary browsing or discovery clicks alone

- `skill_co_usage_pairs`
  - `anchor_skill_fk`
  - `related_skill_fk`
  - `observation_count`
  - `distinct_run_count`
  - `co_usage_rate`
  - `lift_score`
  - `pmi_score` or another association-strength metric
  - `last_observed_at`
  - `window_days`
  - `created_at`
  - `updated_at`

The exact metric can be finalized during implementation, but it should reward
true association strength rather than raw popularity alone.

### Recommended Source of Truth
- Keep canonical dependency declarations in the existing normalized dependency
  model.
- Keep co-usage observations derived from explicit consumer outcomes, ideally
  resolver-produced lock or selected-bundle facts.
- If no high-quality outcome feed exists yet, defer co-usage boosting rather
  than approximating it from noisy page-view or discovery-request data.

### Ranking Use
- Apply co-usage only as a bounded boost after lexical and semantic candidates
  are already assembled.
- Prefer using co-usage when the caller provides meaningful context, such as:
  - already selected skills
  - installed skills
  - explicit task bundle context
- If discovery remains context-free, co-usage should stay off or be limited to a
  conservative tie-break role.
- Co-usage must never outrank exact identifier matches on its own.
- Co-usage boosts must be capped to prevent popularity loops from dominating
  lexical or semantic relevance.

## Component Boundaries
- `app/intelligence/`
  - embedding source-text construction
  - source checksum helpers
  - RRF fusion helpers
  - co-usage score-combination helpers
- `app/core/`
  - lexical-primary discovery orchestration
  - fallback behavior
  - latency budgeting
  - feature-flag and rollout rules
- `app/persistence/`
  - `pgvector` model and ANN query support
  - co-usage aggregate models and queries
  - governance-safe filtered retrieval
- background worker
  - embedding generation
  - reindex and retry workflows
  - co-usage aggregate rebuilds or incremental refreshes

## Rollout Plan

### Phase 0 - Instrumentation
- Measure lexical miss and weak-recall cases in discovery.
- Establish latency and recall targets before changing ranking behavior.
- Define the minimum viable quality bar for semantic and co-usage boosts.

### Phase 1 - Semantic Schema and Indexing
- Add `pgvector` migration and `skill_search_embeddings`.
- Add metadata-centric source-text builder plus source checksumming.
- Add post-commit embedding indexing and retry behavior.

### Phase 2 - Dark Launch
- Backfill embeddings for existing published versions.
- Generate query embeddings in shadow mode.
- Log semantic overlap with lexical results without changing responses.

### Phase 3 - Lexical-Primary Expansion
- Enable lexical + semantic union under a feature flag.
- Roll out lexical-biased fusion on a controlled traffic slice.
- Benchmark latency, recall, and candidate stability.

### Phase 4 - Co-Usage Signals
- Introduce co-usage observation ingestion from explicit outcome sources.
- Build `skill_co_usage_pairs` aggregates.
- Apply capped co-usage boosts only where context quality justifies it.

### Phase 5 - Hardening
- Add rebuild tooling for embedding-model changes.
- Add metrics, lag alerts, and failure dashboards for indexing pipelines.
- Freeze the first supported embedding model and co-usage metric version.

## Deliverables
- Migration plan for PostgreSQL `pgvector` enablement and
  `skill_search_embeddings`.
- Discovery design note describing lexical-primary semantic expansion and
  deterministic fusion.
- Derived co-usage signal design note with event source, aggregation method, and
  bounded ranking impact.
- Repository and service changes scoped to the existing discovery route family.
- Reindex and backfill tooling for embeddings and co-usage aggregates.
- Feature-flag strategy for dark launch and staged rollout.

## Acceptance Criteria
- `POST /discovery` continues to work when embeddings are unavailable, stale, or
  timing out.
- Semantic retrieval never blocks immutable publish success.
- Semantic ranking is additive, secondary, and keeps exact slug/name matches
  ahead of fused relevance.
- No new public semantic-search or statistical-discovery route family is added.
- Governance filters are enforced consistently across lexical and semantic
  retrieval paths.
- Co-usage signals remain advisory and derived; they do not mutate canonical
  dependency, metadata, or content records.
- Co-usage boosts are context-aware and capped so they cannot dominate exact
  matches or overwhelm semantic and lexical relevance.
- The server/resolver boundary remains unchanged: the server expands candidates,
  while final selection and runtime policy remain resolver-owned.

## Test Plan
- Unit tests for embedding source normalization and source checksum behavior.
- Unit tests for RRF fusion ordering and deterministic tie-breaks.
- Unit tests for co-usage score normalization, capping, and fallback behavior.
- Integration tests for lexical-only fallback when embeddings are unavailable.
- Integration tests for governance-safe semantic retrieval under lifecycle and
  trust filters.
- Integration tests for per-slug collapse with hybrid candidates.
- Migration tests for embedding backfill on historical published versions.
- Migration or persistence tests for co-usage aggregate rebuilds.
- Performance tests for discovery p95 under lexical-only, shadow, and hybrid
  modes.
- Regression tests proving exact fetch and dependency-resolution behavior remain
  independent of semantic and co-usage state.

## Open Design Questions
- `POST /discovery` gains optional `context_skills` for high-quality co-usage
  boosts.
- Resolver lock snapshots or selected-skill outcome facts are the canonical
  input for co-usage; curated exports can seed analysis but are not the trusted
  runtime source.
- Which ANN index type and vector distance function perform best on the target
  PostgreSQL deployment.
- Whether hot query embedding caching is needed after initial latency
  measurement.

## Recommendation Summary
- Implement semantic search with `pgvector`, not agent traversal.
- Keep lexical retrieval as the primary path and semantic retrieval as additive
  expansion.
- Keep semantic indexing asynchronous and rebuildable.
- Add co-usage as a bounded statistical ranking signal only after a trustworthy
  explicit outcome feed exists.
- Preserve the discovery contract and keep all new logic inside the current
  server boundary.
