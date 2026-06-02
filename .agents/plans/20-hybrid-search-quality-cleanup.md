# Plan 20 - Hybrid Search Quality Cleanup

## Goal
Make registry search hybrid by default and improve shorthand recall so common user queries like `docs` return the expected skill, including `documentation-writing`.

## Positioning
This plan is an additive discovery-quality cleanup after Plans 17-19. It preserves the frozen public API contract while tightening the default runtime posture, lexical recall, seeded catalog coverage, and endpoint tests around concrete `word -> expected skill` behavior.

Discovery remains candidate generation only. The registry still does not perform resolver-owned final selection, recursive solving, lock generation, or execution planning.

## Architecture
Search should be hybrid unless explicitly configured otherwise:

- Lexical retrieval always runs through `skill_search_documents`.
- Semantic retrieval runs by default through `skill_search_embeddings`.
- `SEMANTIC_DISCOVERY_MODE=off` remains the explicit lexical-only escape hatch.
- `SEMANTIC_DISCOVERY_MODE=shadow` still exercises semantic retrieval without changing returned order.
- Provider or semantic SQL failures degrade to lexical-only results.

Lexical cleanup should handle obvious aliases and abbreviations locally. Semantic search should improve meaning-based recall, but it should not be the only reason `docs` can find a documentation skill.

## Scope
- Add this plan as `.agents/plans/20-hybrid-search-quality-cleanup.md`.
- Sync implementation work from current `origin/dev` before editing code.
- Change semantic discovery default from `off` to `hybrid`.
- Preserve explicit configuration override through `SEMANTIC_DISCOVERY_MODE`.
- Add lexical alias expansion for `doc` and `docs` -> `documentation`.
- Keep exact slug/name and substring matching based on the original normalized query.
- Use expanded query text for PostgreSQL full-text matching and scoring.
- Let semantic search run for name-only discovery/search requests when hybrid is enabled.
- Add or update seeded catalog data so `documentation-writing` exists and is discoverable.
- Add integration tests for `word -> expected skill/s` expectations across discovery endpoints.

## Non-Goals
- No new public search endpoint.
- No change to `/discovery` response shape.
- No public semantic score, vector score, or debug output.
- No artifact body, README, bundle, or raw content search.
- No agentic server-side traversal or resolver behavior.
- No replacement of PostgreSQL full-text search with a separate search service.
- No broad synonym engine beyond a small explicit alias map needed for known catalog vocabulary.

## Implementation Tasks

### Task 0: Start From Synced `dev`
- [x] Run `git status --short --branch`.
- [x] Confirm branch is current feature branch based on `dev`.
- [x] Preserve unrelated untracked files such as `tmp/`.
- [x] Run `git pull --ff-only origin dev`.
- [x] Re-check `git status --short --branch`.
- [x] Do not inspect local `.env` files.

### Task 1: Make Hybrid The Default
Files: `app/core/semantic_defaults.py`, `app/core/settings.py`, `tests/unit/test_settings.py`, `tests/conftest.py`

- [x] Change `DEFAULT_SEMANTIC_DISCOVERY_MODE` to `hybrid`.
- [x] Keep valid modes as `off`, `shadow`, and `hybrid`.
- [x] Keep the rule that `shadow` and `hybrid` require `OPENAI_API_KEY`.
- [x] Update tests so generic app/test fixtures explicitly set `SEMANTIC_DISCOVERY_MODE=off` when provider access is not under test.
- [x] Add a settings test proving the default is `hybrid` when `OPENAI_API_KEY` is present.
- [x] Add or update a settings test proving explicit `SEMANTIC_DISCOVERY_MODE=off` does not require `OPENAI_API_KEY`.

### Task 2: Add Explicit Lexical Alias Expansion
Files: `app/core/skills/normalization.py`, `app/intelligence/search_ranking.py`, `app/persistence/skill_registry_repository_support.py`, `tests/unit/test_skill_normalization.py`, `tests/unit/test_skill_registry_repository.py`

- [x] Add a small typed alias map for known search abbreviations.
- [x] Start with `doc` and `docs` expanding to `documentation`.
- [x] Ensure expansion is deterministic and deduplicated.
- [x] Keep original normalized query text available for exact slug/name and substring matching.
- [x] Use expanded query text for full-text query matching and `ts_rank_cd`.
- [x] Ensure search documents include expanded aliases for stored slug, name, description, and tags where applicable.
- [x] Add unit tests proving `docs` expands to include `documentation`.
- [x] Add unit tests proving exact/substring query behavior still uses the original query.

### Task 3: Split Identity Query From Full-Text Query
Files: `app/core/ports.py`, `app/core/skills/search.py`, `app/persistence/skill_registry_repository.py`, `app/persistence/skill_registry_repository_support.py`, `tests/unit/test_skill_search_service.py`

- [x] Extend the search request sent to persistence with separate identity and full-text query values.
- [x] Use identity query for exact slug match, exact name match, and slug/name substring pattern.
- [x] Use full-text query for `search_vector @@ plainto_tsquery(...)` and `ts_rank_cd(...)`.
- [x] Keep tag filters as hard containment filters.
- [x] Preserve existing deterministic ordering after the improved match set is built.
- [x] Add tests proving an expanded FTS match can enter results without pretending to be an exact slug/name match.

### Task 4: Run Semantic Retrieval For Name-Only Hybrid Searches
Files: `app/core/skills/discovery.py`, `tests/unit/test_skill_search_service.py`, `docs/architecture/discovery-and-ranking.md`

- [x] Keep semantic source as `description + tags` when either description or tags are provided.
- [x] Fall back to `name` as semantic query text only when description and tags are absent.
- [x] Preserve explicit `off` mode as lexical-only.
- [x] Preserve `shadow` mode as semantic-observed but lexical-ordered.
- [x] Add a unit test proving a name-only request in hybrid mode calls the embedding provider.
- [x] Update the existing test that currently expects name-only discovery to skip semantic retrieval.

### Task 5: Add Documentation Skill Seed Coverage
Files: `app/bootstrap/demo_catalog.py`, `tests/integration/test_demo_seed_integration.py`

- [x] Add a seeded skill with slug `documentation-writing`.
- [x] Use a clear name such as `Documentation Writing`.
- [x] Include description text about writing docs, guides, references, or documentation.
- [x] Include tags such as `documentation`, `docs`, and `writing`.
- [x] Keep seed idempotence intact.
- [x] Update expected seeded version counts.
- [x] Add a demo-seed assertion that a `POST /discovery` query for `docs` includes `documentation-writing`.

### Task 6: Add Word-To-Skill Endpoint Tests
Files: `tests/integration/test_discovery_endpoints.py`, `tests/integration/test_exact_fetch_endpoints.py`

- [x] Add parameterized `/discovery` tests for `docs`, `documentation`, and `writing` returning `documentation-writing`.
- [x] Add matching `/catalog/search` coverage.
- [x] Assert ordered candidates/cards contain expected slug values.
- [x] Keep fixtures small and use existing publish helpers instead of direct SQL inserts.

### Task 7: Update Runtime And Architecture Docs
Files: `.env.example`, `docs/architecture/discovery-and-ranking.md`, `docs/reference/api-contract.md`, `docs/architecture/render-neon-deployment.md`

- [x] Document that the default search posture is hybrid.
- [x] Document that `SEMANTIC_DISCOVERY_MODE=off` is the explicit lexical-only setting.
- [x] Document that `OPENAI_API_KEY` is required for default hybrid operation.
- [x] Explain alias expansion as a bounded lexical recall aid, not a broad synonym service.
- [x] Explain name-only semantic fallback for short search-box queries.
- [x] Keep the server/resolver boundary wording unchanged.

### Task 8: Verification
Targeted tests first:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_skill_normalization.py tests/unit/test_skill_registry_repository.py tests/unit/test_settings.py tests/unit/test_skill_search_service.py -q
```

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/integration/test_discovery_endpoints.py tests/integration/test_demo_seed_integration.py tests/integration/test_exact_fetch_endpoints.py -q
```

Full gates:

```bash
make quality
make test
```

## Acceptance Criteria
- `DEFAULT_SEMANTIC_DISCOVERY_MODE` is `hybrid`.
- Explicit `SEMANTIC_DISCOVERY_MODE=off` keeps lexical-only behavior and does not require `OPENAI_API_KEY`.
- Hybrid and shadow modes fail configuration clearly without `OPENAI_API_KEY`.
- `docs` can return `documentation-writing` through lexical alias expansion.
- Name-only hybrid discovery/search can use semantic retrieval.
- `/discovery` still returns ordered slug strings only.
- `/catalog/search` still returns visible metadata cards in discovery order.
- Provider and semantic SQL failures still degrade to lexical-only results.
- Governance, lifecycle, namespace, review, promotion, trust-tier, and tag filters still apply before candidates are returned.
- No raw artifact contents are searched or embedded.

## Assumptions
- Test edits are approved for this plan.
- `documentation-writing` is the canonical seeded slug for documentation-related skill discovery.
- The first alias map stays deliberately small; future aliases should be added only with failing `word -> expected skill` tests.
- Local and CI test configuration may explicitly set `SEMANTIC_DISCOVERY_MODE=off` to avoid requiring provider credentials outside semantic-specific tests.
