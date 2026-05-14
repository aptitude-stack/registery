# Technical Debt Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the current technical-debt audit into a safe cleanup sequence that removes stale contracts, adds missing semantic-search failure visibility, simplifies dependency/config ownership, and defers high-risk architecture splits until guardrails are in place.

**Architecture:** Preserve the current registry boundary: FastAPI routes stay in `app/interface`, business behavior stays in `app/core`, adapters stay in `app/persistence`, and deployment remains Render plus Neon. Start with docs, dependency, config, and telemetry cleanup because those reduce drift without changing behavior; move broader architecture refactors behind tests and explicit decisions.

**Tech Stack:** Python 3.12, FastAPI, Pydantic Settings, SQLAlchemy, PostgreSQL/Neon with pgvector, OpenTelemetry, Render, uv, pytest, Ruff, mypy.

---

## Scope

- Fix current documentation drift around the removed public `/metrics` route.
- Add bounded observability for semantic retrieval failures while preserving lexical fallback.
- Centralize semantic defaults so settings, repository construction, Render config, and docs agree on one source.
- Remove or justify duplicated FastAPI dependency extras and stale FastAPI Cloud tooling now that production hosting is Render.
- Move FastAPI dependency adapters out of `app/core` and enforce the framework-free core boundary.
- Make the production semantic-indexing path reproducible in repository configuration rather than only manual docs.
- Force an explicit co-usage ranking decision before expanding dormant read surfaces.
- Split broad repository ports and large integration tests only after lower-risk cleanup has stabilized.
- Mark stale historical changelog links as historical or exclude them from live-link checks.

## Non-Goals

- Do not reintroduce a public Prometheus `/metrics` endpoint.
- Do not add Bruno, Hoppscotch, or Postman regression coverage; those dev-tool-only surfaces were intentionally de-scoped.
- Do not change the public `POST /discovery` response shape.
- Do not change the semantic source contract: lexical search uses `name + description`; semantic embeddings use `description + tags` only.
- Do not change the staged semantic rollout modes: `off -> shadow -> hybrid`.
- Do not change the persisted semantic compatibility key except through the centralized default constant: `openai:text-embedding-3-small:description-tags-v1`.
- Do not split `SkillCatalogRepository` or `tests/integration/test_skill_registry_endpoints.py` before tasks 1-7 are complete.
- Do not edit tests during implementation without explicit approval from the user, even where this plan names test changes. The approval boundary is required to avoid test drift.

## Assumptions And Constraints

- Work from `/Users/yonatan/Dev/Aptitude/registry`.
- Use `uv`; when the sandbox cannot write the global uv cache, use `UV_CACHE_DIR=.uv-cache`.
- Current dirty Bruno collection/workspace files are unrelated and must be ignored unless they are read for context.
- `make quality` and `make test` remain the canonical final gates.
- Use targeted pytest first, then broader gates.
- Commit after each task. Keep commits small and revert-free.
- Before touching a test file, ask for explicit approval. The plan includes test edits because implementation requires them, but the executor must pause for approval at those steps.
- Do not preserve backward-compatibility shims for internal pre-production cleanup when the user has accepted a breaking cleanup.

## Debt Prioritization

Priority uses `(Impact + Risk) x (6 - Effort)`, where effort is 1 low to 5 high.

| Rank | Audit Item | Type | Impact | Risk | Effort | Priority | Rationale |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | `docs/contributors/development-setup.md` contradicts removed `/metrics` route | Documentation | 4 | 4 | 1 | 40 | Public setup docs actively mislead contributors and conflict with `docs/reference/api-contract.md` plus operability tests. |
| 2 | Semantic query failures are swallowed silently in `app/core/skills/search.py` | Infrastructure, Code | 5 | 5 | 2 | 40 | Hybrid/shadow rollout can fail without warning, masking provider, pgvector, or SQL regressions while still returning lexical results. |
| 3 | Semantic defaults duplicated across settings, repository, Render, docs, and tests | Code, Infrastructure | 4 | 4 | 2 | 32 | Drift can mix incompatible embedding rows or create deploy-time mismatches. |
| 4 | Dependency manifest carries `fastapi[standard]` plus overlapping pins and stale `fastapi-cloud-cli` | Dependency | 3 | 4 | 2 | 28 | The runtime surface is harder to audit and still references a non-production deployment path. |
| 5 | `app/core/dependencies.py` imports FastAPI and API errors | Architecture | 4 | 4 | 3 | 24 | Core is not framework-free; route adapters are in the wrong layer and guardrails do not catch it. |
| 6 | Production semantic indexing is partly manual | Infrastructure | 4 | 4 | 3 | 24 | Semantic discovery cannot safely move toward `hybrid` unless indexing is scheduled and repeatable. |
| 7 | Co-usage ranking has schema/read path/port but no producer/import implementation | Architecture | 3 | 4 | 3 | 21 | Dormant surfaces invite false confidence and future coupling unless implemented or explicitly disabled. |
| 8 | `SkillCatalogRepository` and `SQLAlchemySkillCatalogRepository` are too broad | Architecture, Code | 4 | 3 | 4 | 14 | Broad ports slow reasoning, but splitting before lower-risk cleanup risks churn across every service. |
| 9 | `tests/integration/test_skill_registry_endpoints.py` is a mixed 1350-line regression bucket | Test | 3 | 3 | 4 | 12 | Hard to target and review, but splitting early can create noisy test drift. |
| 10 | Historical changelogs contain stale route names and broken live-relative links | Documentation | 2 | 3 | 2 | 20 | Historical docs should not block current contract checks, but stale live-style links confuse readers. |

## Architecture Decisions And Tradeoffs

### Semantic Failure Visibility

Decision: keep lexical fallback as the user-visible behavior, but emit a bounded warning and internal counter when semantic retrieval fails.

Tradeoff: raising the exception would make semantic rollout more visible but would break the fallback promise in `shadow` and `hybrid`. Silent fallback keeps availability but hides production failure. The recommended path is `logger.warning(..., extra={"event_type": "semantic.discovery.failed", ...})` plus an OpenTelemetry counter in `app/observability/metrics.py`.

### Semantic Defaults Ownership

Decision: create one semantic-defaults module under core configuration, then import it from settings, repository construction, indexing, and tests.

Tradeoff: putting defaults in `app/core/settings.py` is simple but tempts persistence adapters to import the whole settings layer. A small constants module keeps the repository free of environment parsing while avoiding magic defaults in persistence.

Recommended file: `app/core/semantic_defaults.py`.

### FastAPI Dependency Boundary

Decision: move FastAPI dependency providers to `app/interface/api/dependencies.py`; leave core services and auth policy in `app/core`.

Tradeoff: moving all imports in one commit creates churn in route files, but the current placement violates the stated `interface -> core -> persistence` boundary. Keeping a compatibility re-export in `app/core/dependencies.py` would preserve old imports but would keep the architectural smell. Do not keep the re-export unless an external consumer is proven.

### Render Semantic Indexing

Decision: make the Render Workflow and Cron target explicit in `render.yaml`, then keep manual CLI indexing as an operational fallback in docs.

Tradeoff: Render Workflow support is beta and may not support every Blueprint field. If Blueprint support is incomplete, the repository should still add the closest checked-in config and a validation note in `docs/architecture/render-neon-deployment.md`; do not pretend manual dashboard setup is fully codified.

### Co-Usage Ranking

Decision: choose one path before touching ranking internals:

- Recommended: keep the read path disabled and add a no-op guardrail that proves co-usage ranking stays off until `CoUsageObservationImportPort.import_observation_run` is implemented.
- Alternative: implement resolver observation import from trusted resolver outcomes and rebuild aggregate rows.

Tradeoff: removing the dormant surface is clean, but it discards migration-backed work. Implementing import now increases scope and needs resolver-side contract alignment. Keeping it explicitly disabled is the smallest truthful step.

### Repository Port Split

Decision: do not split `SkillCatalogRepository` until semantic defaults, fallback telemetry, dependency cleanup, and dependency adapters have landed.

Tradeoff: the port is too broad today, but splitting it while defaults and adapters still move would amplify conflicts. The later split should produce capability ports aligned to current services: publish, discovery search, exact fetch, resolution, governance admin, embedding indexing, and co-usage import.

### Integration Test Split

Decision: split `tests/integration/test_skill_registry_endpoints.py` only after architecture boundaries stabilize.

Tradeoff: smaller files improve agentic implementation and review. Splitting before behavior and port cleanup risks broad fixture churn and accidental coverage drift.

### Historical Changelog Links

Decision: treat old changelogs as historical records, not current contract docs. Add a link-check allowlist or historical note instead of rewriting history into current semantics.

Tradeoff: rewriting old changelogs can erase useful context. Marking historical constraints keeps current docs canonical while preventing stale live-relative links from masquerading as current API truth.

## File Map

### Planned Creates

- `app/core/semantic_defaults.py`: single source for semantic provider/model/index/dimension/query defaults.
- `app/interface/api/dependencies.py`: FastAPI dependency adapters and typed aliases currently in `app/core/dependencies.py`.
- `docs/reference/historical-docs.md`: link-check and reader guidance for changelog files that intentionally describe past route surfaces.

### Planned Modifies

- `docs/contributors/development-setup.md`: remove `/metrics` local URL and curl probe; point to OTLP/Grafana Cloud docs.
- `docs/reference/api-contract.md`: keep removed `/metrics` language and ensure docs use current telemetry wording.
- `docs/reference/runtime-profiles.md`: reference centralized semantic defaults and indexing command.
- `docs/architecture/render-neon-deployment.md`: align semantic defaults, Render indexing setup, and fallback path.
- `docs/reference/observability-grafana-cloud.md`: mention semantic fallback warning/counter once implemented.
- `docs/README.md`: link `docs/reference/historical-docs.md` if created.
- `app/core/skills/search.py`: emit bounded semantic failure signal while returning lexical fallback.
- `app/observability/metrics.py`: add semantic failure counter helper.
- `app/core/settings.py`: import semantic defaults rather than defining repeated literals inline.
- `app/persistence/skill_registry_repository.py`: remove hard-coded semantic constructor defaults or import from `app/core/semantic_defaults.py`.
- `app/service_container.py`: pass explicit semantic config into repository and services.
- `scripts/index_semantic_embeddings.py`: use centralized defaults through settings; avoid local literal drift.
- `workflows/semantic_embeddings.py`: keep workflow task defaults aligned with centralized defaults and docs.
- `scripts/trigger_semantic_embedding_workflow.py`: keep task slug and batch defaults aligned with Render config.
- `render.yaml`: add semantic defaults from one source and codify workflow/cron when Render Blueprint support allows it.
- `pyproject.toml`: remove stale/duplicated dependency surface after confirming FastAPI CLI and multipart needs.
- `uv.lock`: update after dependency manifest changes.
- `tests/unit/test_public_contract_docs.py`: lock current metrics docs and historical-docs guidance.
- `tests/unit/test_skill_search_service.py`: prove semantic failures emit signal and preserve lexical fallback.
- `tests/unit/test_observability.py`: prove semantic failure metric helper emits the expected instrument.
- `tests/unit/test_settings.py`: assert defaults through centralized constants.
- `tests/unit/test_dependency_manifest.py`: lock dependency cleanup.
- `tests/unit/test_layering_imports.py`: forbid FastAPI imports from `app/core`.
- `tests/unit/test_dependencies.py`: move dependency-adapter tests to the interface dependency module.
- `tests/integration/test_semantic_embedding_indexing.py`: keep indexing commands and defaults aligned.
- `tests/integration/test_skill_registry_endpoints.py`: split only in the later test-debt phase.

### Planned Deletes

- `app/core/dependencies.py`: delete after route imports and tests move to `app/interface/api/dependencies.py`.

## Phase 1: Low-Risk Docs And Dependency Cleanup

### Task 1: Align Contributor Docs With Removed `/metrics`

**Files:**
- Modify: `docs/contributors/development-setup.md`
- Modify: `tests/unit/test_public_contract_docs.py`
- Optional Review: `docs/reference/api-contract.md`

- [ ] **Step 1: Request approval before editing tests**

Ask:

```text
The implementation needs to update tests/unit/test_public_contract_docs.py to lock the /metrics doc cleanup. Do you approve this test edit?
```

Expected: user approves before any test file is changed.

- [ ] **Step 2: Write the failing docs-contract assertion**

In `tests/unit/test_public_contract_docs.py`, extend `test_api_contract_docs_describe_tar_zst_upload_and_fetch`:

```python
    development_setup = Path("docs/contributors/development-setup.md").read_text(
        encoding="utf-8"
    )

    assert "legacy `/metrics` Prometheus exposition endpoint has been removed" in api_contract
    assert "http://127.0.0.1:8000/metrics" not in development_setup
    assert "Example metrics probe" not in development_setup
    assert "OTEL_ENABLED=true" in development_setup
    assert "../reference/observability-grafana-cloud.md" in development_setup
```

- [ ] **Step 3: Run the focused failing test**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_public_contract_docs.py::test_api_contract_docs_describe_tar_zst_upload_and_fetch -q
```

Expected: fail because `docs/contributors/development-setup.md` still lists `http://127.0.0.1:8000/metrics` and an example metrics probe.

- [ ] **Step 4: Update contributor docs**

In `docs/contributors/development-setup.md`, replace the local URL bullet:

```markdown
- Metrics: shipped through OpenTelemetry when `OTEL_ENABLED=true`; no local `/metrics` HTTP route exists.
```

Replace the `Example metrics probe` block with:

```markdown
For telemetry validation, enable OTLP export and use the Grafana Cloud reference instead of probing a local `/metrics` route:

```bash
OTEL_ENABLED=true \
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-<region>.grafana.net/otlp \
uv run fastapi dev
```

See [`../reference/observability-grafana-cloud.md`](../reference/observability-grafana-cloud.md) for the full setup.
```

- [ ] **Step 5: Run the focused passing test**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_public_contract_docs.py::test_api_contract_docs_describe_tar_zst_upload_and_fetch -q
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add docs/contributors/development-setup.md tests/unit/test_public_contract_docs.py
git commit -m "docs: align setup guide with removed metrics route"
```

Expected: one docs-focused commit.

### Task 2: Prune Dependency Manifest Drift

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `tests/unit/test_dependency_manifest.py`
- Review: `docs/contributors/development-setup.md`
- Review: `docs/architecture/render-neon-deployment.md`

- [ ] **Step 1: Request approval before editing tests**

Ask:

```text
The dependency cleanup needs tests/unit/test_dependency_manifest.py to lock the runtime/dev boundary. Do you approve this test edit?
```

Expected: user approves before the dependency test changes.

- [ ] **Step 2: Verify FastAPI CLI and multipart owners**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev python -c "import fastapi, uvicorn, multipart, pydantic; print(fastapi.__version__, pydantic.__version__)"
```

Expected: command imports FastAPI, Uvicorn, multipart support, and Pydantic under the current environment.

- [ ] **Step 3: Write dependency-boundary assertions**

In `tests/unit/test_dependency_manifest.py`, add these assertions:

```python
    assert not any(dependency.startswith("fastapi-cloud-cli") for dependency in development_dependencies)
    assert any(dependency.startswith("fastapi==") for dependency in runtime_dependencies)
    assert any(dependency.startswith("uvicorn[standard]") for dependency in runtime_dependencies)
    assert any(dependency.startswith("python-multipart") for dependency in runtime_dependencies)
```

If implementation chooses to keep `fastapi[standard]`, replace the second assertion with:

```python
    assert any(dependency.startswith("fastapi[standard]") for dependency in runtime_dependencies)
```

Use one form only. The recommended cleanup is plain `fastapi==0.136.1` plus explicit runtime pins that the app imports directly.

- [ ] **Step 4: Run the focused failing test**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_dependency_manifest.py -q
```

Expected: fail because `fastapi-cloud-cli==0.17.1` remains in dev dependencies and `fastapi[standard]==0.136.1` is still present.

- [ ] **Step 5: Edit dependencies**

In `pyproject.toml`, change:

```toml
"fastapi[standard]==0.136.1",
```

to:

```toml
"fastapi==0.136.1",
```

Remove this dev dependency:

```toml
"fastapi-cloud-cli==0.17.1",
```

Keep these runtime dependencies unless an import audit proves they are no longer needed:

```toml
"uvicorn[standard]==0.46.0",
"pydantic==2.13.4",
"python-multipart==0.0.27",
```

- [ ] **Step 6: Refresh the lockfile**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv lock
```

Expected: `uv.lock` no longer contains `fastapi-cloud-cli`; FastAPI remains locked at `0.136.1`.

- [ ] **Step 7: Run focused dependency and startup checks**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_dependency_manifest.py tests/unit/test_settings.py -q
UV_CACHE_DIR=.uv-cache uv run --extra dev python -c "from app.main import create_app; app = create_app(); print(app.title)"
```

Expected: tests pass and the app factory prints `Aptitude Registry Service`.

- [ ] **Step 8: Commit**

Run:

```bash
git add pyproject.toml uv.lock tests/unit/test_dependency_manifest.py
git commit -m "chore: prune stale FastAPI dependency surface"
```

Expected: one dependency-boundary commit.

## Phase 2: Semantic Config And Failure Visibility

### Task 3: Centralize Semantic Defaults

**Files:**
- Create: `app/core/semantic_defaults.py`
- Modify: `app/core/settings.py`
- Modify: `app/core/skills/search.py`
- Modify: `app/persistence/skill_registry_repository.py`
- Modify: `app/service_container.py`
- Modify: `scripts/index_semantic_embeddings.py`
- Modify: `docs/reference/runtime-profiles.md`
- Modify: `docs/architecture/render-neon-deployment.md`
- Modify: `render.yaml`
- Modify: `tests/unit/test_settings.py`
- Modify: `tests/unit/test_skill_search_service.py`
- Modify: `tests/integration/test_semantic_embedding_indexing.py`

- [ ] **Step 1: Request approval before editing tests**

Ask:

```text
The semantic default centralization needs settings/search/indexing tests updated to import the new constants. Do you approve these test edits?
```

Expected: approval before test files change.

- [ ] **Step 2: Write failing constant-ownership tests**

In `tests/unit/test_settings.py`, import:

```python
from app.core.semantic_defaults import (
    DEFAULT_SEMANTIC_CANDIDATE_LIMIT,
    DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS,
    DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
    DEFAULT_SEMANTIC_EMBEDDING_MODEL,
    DEFAULT_SEMANTIC_EMBEDDING_PROVIDER,
    DEFAULT_SEMANTIC_HNSW_EF_SEARCH,
    DEFAULT_SEMANTIC_QUERY_TIMEOUT_MS,
)
```

Then replace literal assertions in `test_settings_load_valid_environment` with:

```python
    assert settings.semantic_embedding_provider == DEFAULT_SEMANTIC_EMBEDDING_PROVIDER
    assert settings.semantic_embedding_model == DEFAULT_SEMANTIC_EMBEDDING_MODEL
    assert settings.semantic_embedding_index_key == DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY
    assert settings.semantic_embedding_dimensions == DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS
    assert settings.semantic_candidate_limit == DEFAULT_SEMANTIC_CANDIDATE_LIMIT
    assert settings.semantic_query_timeout_ms == DEFAULT_SEMANTIC_QUERY_TIMEOUT_MS
    assert settings.semantic_hnsw_ef_search == DEFAULT_SEMANTIC_HNSW_EF_SEARCH
```

- [ ] **Step 3: Run the focused failing test**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_settings.py::test_settings_load_valid_environment -q
```

Expected: fail because `app.core.semantic_defaults` does not exist.

- [ ] **Step 4: Create semantic defaults module**

Create `app/core/semantic_defaults.py`:

```python
"""Semantic discovery defaults shared by settings, adapters, docs, and tests."""

from __future__ import annotations

from typing import Literal

SemanticEmbeddingProvider = Literal["openai"]

DEFAULT_SEMANTIC_DISCOVERY_MODE = "off"
DEFAULT_SEMANTIC_EMBEDDING_PROVIDER: SemanticEmbeddingProvider = "openai"
DEFAULT_SEMANTIC_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_SEMANTIC_EMBEDDING_SOURCE_VERSION = "description-tags-v1"
DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY = (
    f"{DEFAULT_SEMANTIC_EMBEDDING_PROVIDER}:"
    f"{DEFAULT_SEMANTIC_EMBEDDING_MODEL}:"
    f"{DEFAULT_SEMANTIC_EMBEDDING_SOURCE_VERSION}"
)
DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS = 1536
DEFAULT_SEMANTIC_CANDIDATE_LIMIT = 20
DEFAULT_SEMANTIC_QUERY_TIMEOUT_MS = 150
DEFAULT_SEMANTIC_HNSW_EF_SEARCH = 100
DEFAULT_SEMANTIC_INDEX_BATCH_SIZE = 25
DEFAULT_SEMANTIC_INDEX_MAX_BATCHES = 1
DEFAULT_SEMANTIC_RECLAIM_AFTER_SECONDS = 3600
```

- [ ] **Step 5: Replace settings literals**

In `app/core/settings.py`, import defaults from `app.core.semantic_defaults` and set fields to those constants:

```python
from app.core.semantic_defaults import (
    DEFAULT_SEMANTIC_CANDIDATE_LIMIT,
    DEFAULT_SEMANTIC_DISCOVERY_MODE,
    DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS,
    DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
    DEFAULT_SEMANTIC_EMBEDDING_MODEL,
    DEFAULT_SEMANTIC_EMBEDDING_PROVIDER,
    DEFAULT_SEMANTIC_EMBEDDING_SOURCE_VERSION,
    DEFAULT_SEMANTIC_HNSW_EF_SEARCH,
    DEFAULT_SEMANTIC_QUERY_TIMEOUT_MS,
    SemanticEmbeddingProvider,
)
```

Update `expected_index_key` to use `DEFAULT_SEMANTIC_EMBEDDING_SOURCE_VERSION`:

```python
        expected_index_key = (
            f"{self.semantic_embedding_provider}:"
            f"{self.semantic_embedding_model}:"
            f"{DEFAULT_SEMANTIC_EMBEDDING_SOURCE_VERSION}"
        )
```

- [ ] **Step 6: Remove persistence magic defaults**

In `app/persistence/skill_registry_repository.py`, import only the semantic constants needed by the repository:

```python
from app.core.semantic_defaults import (
    DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS,
    DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
)
```

Change constructor defaults:

```python
        semantic_embedding_index_key: str = DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
        semantic_embedding_dimensions: int = DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS,
```

Expected: the repository no longer owns literal model/index/dimension defaults.

- [ ] **Step 7: Align search service defaults**

In `app/core/skills/search.py`, import from `app.core.semantic_defaults` instead of `app.core.settings` for model/index/dimension defaults:

```python
from app.core.semantic_defaults import (
    DEFAULT_SEMANTIC_CANDIDATE_LIMIT,
    DEFAULT_SEMANTIC_EMBEDDING_DIMENSIONS,
    DEFAULT_SEMANTIC_EMBEDDING_INDEX_KEY,
    DEFAULT_SEMANTIC_EMBEDDING_MODEL,
    DEFAULT_SEMANTIC_HNSW_EF_SEARCH,
    DEFAULT_SEMANTIC_QUERY_TIMEOUT_MS,
)
from app.core.settings import SemanticDiscoveryMode
```

Use those constants in `SkillSearchService.__init__`.

- [ ] **Step 8: Align docs and Render config literals**

Update `docs/reference/runtime-profiles.md`, `docs/architecture/render-neon-deployment.md`, and `render.yaml` to match:

```text
SEMANTIC_EMBEDDING_PROVIDER=openai
SEMANTIC_EMBEDDING_MODEL=text-embedding-3-small
SEMANTIC_EMBEDDING_INDEX_KEY=openai:text-embedding-3-small:description-tags-v1
SEMANTIC_EMBEDDING_DIMENSIONS=1536
SEMANTIC_CANDIDATE_LIMIT=20
SEMANTIC_QUERY_TIMEOUT_MS=150
SEMANTIC_HNSW_EF_SEARCH=100
```

Expected: no semantic default value in docs or Render config conflicts with `app/core/semantic_defaults.py`.

- [ ] **Step 9: Search for remaining duplicated literals**

Run:

```bash
rg -n "openai:text-embedding-3-small:description-tags-v1|text-embedding-3-small|SEMANTIC_QUERY_TIMEOUT_MS|SEMANTIC_HNSW_EF_SEARCH|1536" app tests docs render.yaml scripts workflows
```

Expected: remaining occurrences are either constants, env-var examples, assertions importing constants, or expected contract strings. No constructor default outside `app/core/semantic_defaults.py` should define the compatibility key from scratch.

- [ ] **Step 10: Run focused tests**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_settings.py tests/unit/test_skill_search_service.py tests/integration/test_semantic_embedding_indexing.py -q
```

Expected: pass.

- [ ] **Step 11: Commit**

Run:

```bash
git add app/core/semantic_defaults.py app/core/settings.py app/core/skills/search.py app/persistence/skill_registry_repository.py app/service_container.py scripts/index_semantic_embeddings.py docs/reference/runtime-profiles.md docs/architecture/render-neon-deployment.md render.yaml tests/unit/test_settings.py tests/unit/test_skill_search_service.py tests/integration/test_semantic_embedding_indexing.py
git commit -m "refactor: centralize semantic discovery defaults"
```

Expected: one config-ownership commit.

### Task 4: Add Bounded Semantic Failure Signal

**Files:**
- Modify: `app/core/skills/search.py`
- Modify: `app/observability/metrics.py`
- Modify: `docs/reference/observability-grafana-cloud.md`
- Modify: `tests/unit/test_skill_search_service.py`
- Modify: `tests/unit/test_observability.py`

- [ ] **Step 1: Request approval before editing tests**

Ask:

```text
The semantic fallback telemetry change needs search-service and observability tests. Do you approve these test edits?
```

Expected: approval before changing tests.

- [ ] **Step 2: Write failing search-service test**

In `tests/unit/test_skill_search_service.py`, update `_service` to accept an injected audit recorder:

```python
def _service(
    repository: _Repository,
    *,
    semantic_mode: str = "off",
    embedding_provider: _EmbeddingProvider | None = None,
    co_usage_enabled: bool = False,
    audit_recorder: _AuditRecorder | None = None,
) -> SkillSearchService:
    return SkillSearchService(
        repository=repository,
        audit_recorder=audit_recorder or _AuditRecorder(),
        governance_policy=GovernancePolicy(profile=build_default_policy_profile()),
        semantic_discovery_mode=semantic_mode,
        embedding_provider=embedding_provider,
        co_usage_ranking_enabled=co_usage_enabled,
    )
```

Add:

```python
@pytest.mark.unit
def test_hybrid_mode_records_semantic_failure_signal_when_semantic_sql_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider = _EmbeddingProvider()
    repository = _Repository(
        lexical=(_candidate("python.lint"),),
        semantic_should_fail=True,
    )

    with caplog.at_level("WARNING", logger="app.core.skills.search"):
        results = _service(
            repository,
            semantic_mode="hybrid",
            embedding_provider=provider,
        ).search(
            caller=CallerIdentity(token_id="reader", scopes=frozenset({"read"})),
            query=_query(),
        )

    assert tuple(item.slug for item in results) == ("python.lint",)
    assert any(
        record.__dict__.get("event_type") == "semantic.discovery.failed"
        for record in caplog.records
    )
```

- [ ] **Step 3: Write failing observability test**

In `tests/unit/test_observability.py`, add a metric assertion matching the existing in-memory metric-reader style:

```python
        metrics_module.observe_semantic_discovery_failure(
            mode="hybrid",
            stage="repository",
            exception_type="RuntimeError",
        )
```

Expected metric name:

```python
"aptitude_semantic_discovery_failures_total"
```

Expected attributes:

```python
{"mode": "hybrid", "stage": "repository", "exception_type": "RuntimeError"}
```

- [ ] **Step 4: Run focused failing tests**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_skill_search_service.py::test_hybrid_mode_records_semantic_failure_signal_when_semantic_sql_fails tests/unit/test_observability.py -q
```

Expected: fail because no failure metric helper or warning exists.

- [ ] **Step 5: Add semantic failure metric helper**

In `app/observability/metrics.py`, add:

```python
_SEMANTIC_DISCOVERY_FAILURES = _meter.create_counter(
    "aptitude_semantic_discovery_failures_total",
    description="Semantic discovery fallback events by mode, stage, and exception type.",
)


def observe_semantic_discovery_failure(
    *,
    mode: str,
    stage: str,
    exception_type: str,
) -> None:
    """Record one semantic-discovery failure that degraded to lexical fallback."""
    _SEMANTIC_DISCOVERY_FAILURES.add(
        1,
        {
            "mode": mode,
            "stage": stage,
            "exception_type": exception_type,
        },
    )
```

- [ ] **Step 6: Add bounded warning and metric call**

In `app/core/skills/search.py`, add module logger and metric import:

```python
import logging

from app.observability.metrics import observe_semantic_discovery_failure

logger = logging.getLogger(__name__)
```

Replace the broad exception block in `_semantic_candidates`:

```python
        except Exception as exc:
            stage = "provider" if not self._repository_was_called else "repository"
            observe_semantic_discovery_failure(
                mode=self._semantic_discovery_mode,
                stage=stage,
                exception_type=type(exc).__name__,
            )
            logger.warning(
                "semantic discovery degraded to lexical fallback",
                extra={
                    "event_type": "semantic.discovery.failed",
                    "semantic_mode": self._semantic_discovery_mode,
                    "semantic_stage": stage,
                    "exception_type": type(exc).__name__,
                },
            )
            return ()
```

Do not introduce `_repository_was_called`. Instead split the current `try` into provider and repository sections:

```python
        try:
            query_embedding = validate_embedding_vector(
                self._embedding_provider.embed_query(
                    text=query_text,
                    model=self._semantic_embedding_model,
                    dimensions=self._semantic_embedding_dimensions,
                    timeout_ms=self._semantic_query_timeout_ms,
                ),
                dimensions=self._semantic_embedding_dimensions,
            )
        except Exception as exc:
            self._record_semantic_failure(stage="provider", exc=exc)
            return ()

        try:
            return self._repository.search_semantic_candidates(
                request=SearchSemanticCandidatesRequest(
                    query_embedding=query_embedding,
                    embedding_model=self._semantic_embedding_index_key,
                    embedding_dimensions=self._semantic_embedding_dimensions,
                    required_tags=required_tags,
                    fresh_within_days=fresh_within_days,
                    max_content_size_bytes=max_content_size_bytes,
                    lifecycle_statuses=lifecycle_statuses,
                    trust_tiers=trust_tiers,
                    namespaces=namespaces,
                    promotion_channels=promotion_channels,
                    review_states=review_states,
                    limit=min(self._semantic_candidate_limit, normalized_request_limit),
                    hnsw_ef_search=self._semantic_hnsw_ef_search,
                )
            )
        except Exception as exc:
            self._record_semantic_failure(stage="repository", exc=exc)
            return ()
```

Add helper:

```python
    def _record_semantic_failure(self, *, stage: str, exc: Exception) -> None:
        observe_semantic_discovery_failure(
            mode=self._semantic_discovery_mode,
            stage=stage,
            exception_type=type(exc).__name__,
        )
        logger.warning(
            "semantic discovery degraded to lexical fallback",
            extra={
                "event_type": "semantic.discovery.failed",
                "semantic_mode": self._semantic_discovery_mode,
                "semantic_stage": stage,
                "exception_type": type(exc).__name__,
            },
        )
```

- [ ] **Step 7: Document the signal**

In `docs/reference/observability-grafana-cloud.md`, add the metric to the metrics table:

```markdown
| Semantic fallback | `aptitude_semantic_discovery_failures_total` | Counts provider or repository failures that degraded semantic discovery to lexical fallback. Alert on sustained non-zero values before moving from `shadow` to `hybrid`. |
```

- [ ] **Step 8: Run focused tests**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_skill_search_service.py tests/unit/test_observability.py -q
```

Expected: pass; existing lexical fallback tests still pass.

- [ ] **Step 9: Commit**

Run:

```bash
git add app/core/skills/search.py app/observability/metrics.py docs/reference/observability-grafana-cloud.md tests/unit/test_skill_search_service.py tests/unit/test_observability.py
git commit -m "feat: surface semantic discovery fallback failures"
```

Expected: one observability commit.

## Phase 3: Framework Boundary Cleanup

### Task 5: Move FastAPI Dependency Adapters Under Interface

**Files:**
- Create: `app/interface/api/dependencies.py`
- Delete: `app/core/dependencies.py`
- Modify: `app/interface/api/discovery.py`
- Modify: `app/interface/api/enterprise.py`
- Modify: `app/interface/api/fetch.py`
- Modify: `app/interface/api/health.py`
- Modify: `app/interface/api/resolution.py`
- Modify: `app/interface/api/skills.py`
- Modify: `app/core/README.md`
- Modify: `app/interface/api/README.md`
- Modify: `tests/unit/test_layering_imports.py`
- Modify: `tests/unit/test_dependencies.py`

- [ ] **Step 1: Request approval before editing tests**

Ask:

```text
The dependency adapter move needs layering and dependency-wiring tests updated. Do you approve these test edits?
```

Expected: approval before test changes.

- [ ] **Step 2: Strengthen layering test first**

In `tests/unit/test_layering_imports.py`, add rules:

```python
    (REPO_ROOT / "app" / "core", "fastapi"),
    (REPO_ROOT / "app" / "core", "starlette"),
    (REPO_ROOT / "app" / "core", "app.interface"),
```

Rename the test:

```python
def test_layering_forbids_core_framework_and_adapter_imports() -> None:
```

- [ ] **Step 3: Run the focused failing layering test**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_layering_imports.py -q
```

Expected: fail on `app/core/dependencies.py` imports from `fastapi` and `app.interface.api.errors`.

- [ ] **Step 4: Move adapter module**

Create `app/interface/api/dependencies.py` with the current contents of `app/core/dependencies.py`, then update the module docstring:

```python
"""FastAPI dependency adapters for API route handlers.

This module lives in the interface layer so core services stay framework-free.
"""
```

Keep these imports from core:

```python
from app.core.auth import AuthError, AuthorizationError, AuthService
from app.core.governance import CallerIdentity, CallerScope
from app.core.settings import Settings, get_settings
from app.core.skills.discovery import SkillDiscoveryService
from app.core.skills.fetch import SkillFetchService
from app.core.skills.registry import SkillRegistryService
from app.core.skills.resolution import SkillResolutionService
```

- [ ] **Step 5: Update route imports**

Replace route imports:

```python
from app.core.dependencies import ...
```

with:

```python
from app.interface.api.dependencies import ...
```

in:

```text
app/interface/api/discovery.py
app/interface/api/enterprise.py
app/interface/api/fetch.py
app/interface/api/health.py
app/interface/api/resolution.py
app/interface/api/skills.py
```

- [ ] **Step 6: Update dependency tests**

In `tests/unit/test_dependencies.py`, change:

```python
from app.core.dependencies import (
```

to:

```python
from app.interface.api.dependencies import (
```

- [ ] **Step 7: Delete old core module**

Delete `app/core/dependencies.py`.

Do not add a compatibility re-export unless a failing internal import proves it is required. If an internal import fails, update that import to `app.interface.api.dependencies`.

- [ ] **Step 8: Update module READMEs**

In `app/core/README.md`, remove `dependencies.py` from the module map and replace the dependency-provider boundary bullet with:

```markdown
- FastAPI dependency providers live under `app/interface/api/dependencies.py`; core exposes services and ports, not framework adapters.
```

In `app/interface/api/README.md`, add:

```markdown
- `dependencies.py`: FastAPI dependency providers and typed aliases that adapt request handlers to the process-scoped service container.
```

- [ ] **Step 9: Run focused tests**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_layering_imports.py tests/unit/test_dependencies.py tests/unit/test_registry_api_boundary.py -q
```

Expected: pass; core no longer imports FastAPI, Starlette, or `app.interface`.

- [ ] **Step 10: Commit**

Run:

```bash
git add app/interface/api/dependencies.py app/interface/api/discovery.py app/interface/api/enterprise.py app/interface/api/fetch.py app/interface/api/health.py app/interface/api/resolution.py app/interface/api/skills.py app/core/README.md app/interface/api/README.md tests/unit/test_layering_imports.py tests/unit/test_dependencies.py
git add -u app/core/dependencies.py
git commit -m "refactor: move FastAPI dependency adapters to interface"
```

Expected: one architecture-boundary commit.

## Phase 4: Production Indexing And Dormant Co-Usage Surface

### Task 6: Codify Semantic Indexing Deployment Path

**Files:**
- Modify: `render.yaml`
- Modify: `docs/architecture/render-neon-deployment.md`
- Modify: `docs/reference/runtime-profiles.md`
- Modify: `scripts/trigger_semantic_embedding_workflow.py`
- Modify: `workflows/semantic_embeddings.py`
- Modify: `tests/unit/test_ci_workflows.py`
- Modify: `tests/integration/test_semantic_embedding_indexing.py`

- [ ] **Step 1: Request approval before editing tests**

Ask:

```text
The indexing deployment cleanup needs workflow/config tests updated. Do you approve these test edits?
```

Expected: approval before test changes.

- [ ] **Step 2: Confirm Render Blueprint support before editing YAML**

Run:

```bash
rg -n "type: cron|type: worker|workflow|cron" docs render.yaml workflows scripts
```

Expected: current `render.yaml` defines only the web service; docs describe manual Workflow/Cron setup.

- [ ] **Step 3: Add config test for production indexing target**

In `tests/unit/test_ci_workflows.py`, add a YAML test that asserts `render.yaml` includes an indexing service or documented fallback marker:

```python
def test_render_blueprint_declares_semantic_indexing_or_explicit_fallback() -> None:
    blueprint = Path("render.yaml").read_text(encoding="utf-8")

    assert "aptitude-registry-api" in blueprint
    assert (
        "aptitude-registry-semantic-indexing" in blueprint
        or "semantic-indexing-managed-outside-blueprint" in blueprint
    )
```

- [ ] **Step 4: Run focused failing test**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_ci_workflows.py::test_render_blueprint_declares_semantic_indexing_or_explicit_fallback -q
```

Expected: fail because `render.yaml` has only the web service.

- [ ] **Step 5: Add the least-risk checked-in Render target**

If Render Blueprint supports the needed Workflow/Cron shape, add entries to `render.yaml`:

```yaml
  - type: cron
    name: aptitude-registry-semantic-indexing-cron
    runtime: python
    repo: https://github.com/aptitude-stack/registery
    branch: master
    region: virginia
    schedule: "*/30 * * * *"
    buildCommand: uv sync --frozen --no-dev --extra workflow
    startCommand: uv run --extra workflow python scripts/trigger_semantic_embedding_workflow.py
    envVars:
      - key: PYTHON_VERSION
        value: 3.12.13
      - key: RENDER_SEMANTIC_INDEX_WORKFLOW_TASK
        value: aptitude-registry-semantic-indexing/index_semantic_embeddings
      - key: DATABASE_URL
        sync: false
      - key: OPENAI_API_KEY
        sync: false
```

If Render Blueprint cannot represent Workflow services reliably, add an explicit marker comment next to the web service:

```yaml
    # semantic-indexing-managed-outside-blueprint: Render Workflow and Cron are configured manually until Blueprint support covers Workflow services.
```

Use the first option only if it is supported by Render docs and current tooling.

- [ ] **Step 6: Align scripts to centralized defaults**

In `scripts/trigger_semantic_embedding_workflow.py`, import batch defaults:

```python
from app.core.semantic_defaults import (
    DEFAULT_SEMANTIC_INDEX_BATCH_SIZE,
    DEFAULT_SEMANTIC_INDEX_MAX_BATCHES,
    DEFAULT_SEMANTIC_RECLAIM_AFTER_SECONDS,
)
```

Use the constants in argparse defaults:

```python
    parser.add_argument("--batch-size", type=int, default=DEFAULT_SEMANTIC_INDEX_BATCH_SIZE)
    parser.add_argument("--max-batches", type=int, default=DEFAULT_SEMANTIC_INDEX_MAX_BATCHES)
    parser.add_argument(
        "--reclaim-after-seconds",
        type=int,
        default=DEFAULT_SEMANTIC_RECLAIM_AFTER_SECONDS,
    )
```

- [ ] **Step 7: Update deployment docs**

In `docs/architecture/render-neon-deployment.md`, replace manual-only wording with:

```markdown
Production indexing is repository-owned where Render Blueprint support permits it. The desired target is a bounded Render Workflow task, `aptitude-registry-semantic-indexing/index_semantic_embeddings`, triggered by a Cron job that runs `scripts/trigger_semantic_embedding_workflow.py`.

If the current Render account cannot manage Workflow services through Blueprint, keep the Workflow and Cron configured manually in Render and preserve the `semantic-indexing-managed-outside-blueprint` marker in `render.yaml`. That marker is intentional drift documentation, not a missing service definition.
```

Keep the manual/local fallback command.

- [ ] **Step 8: Run focused tests**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_ci_workflows.py tests/integration/test_semantic_embedding_indexing.py -q
```

Expected: pass.

- [ ] **Step 9: Commit**

Run:

```bash
git add render.yaml docs/architecture/render-neon-deployment.md docs/reference/runtime-profiles.md scripts/trigger_semantic_embedding_workflow.py workflows/semantic_embeddings.py tests/unit/test_ci_workflows.py tests/integration/test_semantic_embedding_indexing.py
git commit -m "chore: codify semantic indexing deployment path"
```

Expected: one infrastructure commit that is honest about any provider limitation.

### Task 7: Decide And Guard Co-Usage Ranking Surface

**Files:**
- Modify: `docs/architecture/discovery-and-ranking.md`
- Modify: `docs/reference/schema.md`
- Modify: `app/core/ports.py`
- Modify: `app/core/skills/search.py`
- Modify: `tests/unit/test_skill_search_service.py`
- Optional Modify: `app/persistence/skill_registry_repository.py`

- [ ] **Step 1: Choose the co-usage direction before code changes**

Recommended decision:

```text
Keep co-usage ranking disabled by default and document it as dormant until resolver observation import is implemented. Do not remove existing tables in this cleanup.
```

Alternative decision:

```text
Implement trusted resolver observation import now and rebuild skill_co_usage_pairs from imported observation runs.
```

Expected: one decision is written into `docs/architecture/discovery-and-ranking.md`.

- [ ] **Step 2: Request approval before editing tests**

Ask:

```text
The co-usage decision needs search-service tests updated to lock the chosen behavior. Do you approve these test edits?
```

Expected: approval before test changes.

- [ ] **Step 3: Write the dormant-surface guard test**

If using the recommended decision, add to `tests/unit/test_skill_search_service.py`:

```python
@pytest.mark.unit
def test_co_usage_boosts_are_not_requested_when_ranking_disabled_even_with_context() -> None:
    repository = _Repository(
        lexical=(_candidate("python.docs", lexical_score=0.3), _candidate("python.pytest")),
        boosts={"python.pytest": 0.05},
    )

    results = _service(repository, co_usage_enabled=False).search(
        caller=CallerIdentity(token_id="reader", scopes=frozenset({"read"})),
        query=_query(context_skills=("python.lint",)),
    )

    assert tuple(item.slug for item in results) == ("python.docs", "python.pytest")
    assert repository.co_usage_requests == []
```

- [ ] **Step 4: Run the focused test**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_skill_search_service.py::test_co_usage_boosts_are_not_requested_when_ranking_disabled_even_with_context -q
```

Expected: pass if current default is already disabled. If it fails, fix the implementation before proceeding.

- [ ] **Step 5: Document the decision**

In `docs/architecture/discovery-and-ranking.md`, add:

```markdown
## Co-Usage Ranking Status

Co-usage ranking is schema-backed but disabled by default through `CO_USAGE_RANKING_ENABLED=false`. The registry may read `skill_co_usage_pairs` only when a trusted producer has populated resolver observation aggregates. Until `CoUsageObservationImportPort.import_observation_run` has a production implementation, `context_skills` remains accepted request context but must not imply a populated co-usage signal.
```

In `docs/reference/schema.md`, add:

```markdown
The co-usage tables are derived, dormant infrastructure until trusted resolver observation import is implemented. They are not dependency truth and do not change `GET /resolution/{slug}/{version}`.
```

- [ ] **Step 6: Keep or shrink the port deliberately**

If not implementing import now, leave `CoUsageObservationImportPort` but mark the docstring:

```python
class CoUsageObservationImportPort(Protocol):
    """Dormant import contract for future trusted resolver co-usage evidence."""
```

Do not add fake producer code.

- [ ] **Step 7: Run focused tests**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_skill_search_service.py tests/unit/test_public_contract_docs.py -q
```

Expected: pass.

- [ ] **Step 8: Commit**

Run:

```bash
git add docs/architecture/discovery-and-ranking.md docs/reference/schema.md app/core/ports.py tests/unit/test_skill_search_service.py
git commit -m "docs: make co-usage ranking status explicit"
```

Expected: one decision commit with no fake producer.

## Phase 5: Higher-Risk Architecture And Test Debt

### Task 8: Split `SkillCatalogRepository` Into Capability Ports

**Files:**
- Modify: `app/core/ports.py`
- Modify: `app/core/skills/registry.py`
- Modify: `app/core/skills/search.py`
- Modify: `app/core/skills/fetch.py`
- Modify: `app/core/skills/resolution.py`
- Modify: `app/core/skills/embedding_indexing.py`
- Modify: `app/persistence/skill_registry_repository.py`
- Modify: `app/service_container.py`
- Modify: `tests/unit/test_skill_registry_service.py`
- Modify: `tests/unit/test_skill_search_service.py`
- Modify: `tests/unit/test_skill_fetch_service.py`
- Modify: `tests/unit/test_skill_resolution_service.py`
- Modify: `tests/integration/test_semantic_embedding_indexing.py`

- [ ] **Step 1: Confirm prerequisite tasks are merged**

Run:

```bash
git log --oneline -n 20
```

Expected: commits from tasks 1-7 are present, especially semantic defaults and dependency adapter move.

- [ ] **Step 2: Request approval before editing tests**

Ask:

```text
The repository port split touches service constructor tests across publish, search, fetch, resolution, and indexing. Do you approve these test edits?
```

Expected: approval before test changes.

- [ ] **Step 3: Define capability protocols**

In `app/core/ports.py`, replace the single broad service dependency with smaller protocols while keeping shared dataclasses:

```python
class SkillPublishPort(Protocol):
    def skill_exists(self, *, slug: str) -> bool: ...
    def version_exists(self, *, slug: str, version: str) -> bool: ...
    def create_version(
        self,
        *,
        record: CreateSkillVersionRecord,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> SkillVersionDetail: ...


class SkillDiscoverySearchPort(Protocol):
    def search_candidates(
        self,
        *,
        request: SearchCandidatesRequest,
    ) -> tuple[StoredSkillSearchCandidate, ...]: ...

    def search_semantic_candidates(
        self,
        *,
        request: SearchSemanticCandidatesRequest,
    ) -> tuple[StoredSkillSearchCandidate, ...]: ...

    def get_co_usage_boosts(self, *, request: CoUsageBoostRequest) -> dict[str, float]: ...


class SkillExactReadPort(Protocol):
    def get_version_detail(self, *, slug: str, version: str) -> SkillVersionDetail | None: ...
    def get_version_content(self, *, slug: str, version: str) -> SkillContentRecord | None: ...
    def list_versions(self, *, slug: str) -> tuple[SkillVersionListEntry, ...]: ...


class SkillResolutionPort(Protocol):
    def get_relationship_source(
        self,
        *,
        slug: str,
        version: str,
    ) -> SkillRelationshipSource | None: ...


class SkillGovernanceAdminPort(Protocol):
    def update_version_status(
        self,
        *,
        slug: str,
        version: str,
        lifecycle_status: LifecycleStatus,
        audit_events: tuple[AuditEventRecord, ...] = (),
    ) -> SkillVersionStatusUpdate | None: ...
    def create_organization(...): ...
    def create_namespace(...): ...
    def upsert_policy_pack(...): ...
    def update_skill_ownership(...): ...
    def update_version_governance(...): ...
    def add_trust_evidence(...): ...
```

Keep `SkillCatalogRepository` temporarily as a composition alias only if type churn is too large for one commit:

```python
class SkillCatalogRepository(
    SkillPublishPort,
    SkillDiscoverySearchPort,
    SkillExactReadPort,
    SkillResolutionPort,
    SkillGovernanceAdminPort,
    EmbeddingIndexPort,
    Protocol,
):
    """Compatibility composition for the SQLAlchemy adapter implementation."""
```

- [ ] **Step 4: Update service constructor types**

Use these constructor types:

```text
SkillRegistryService.repository: SkillPublishPort | SkillGovernanceAdminPort | SkillExactReadPort as needed by actual methods
SkillSearchService.repository: SkillDiscoverySearchPort
SkillFetchService.repository: SkillExactReadPort
SkillResolutionService.repository: SkillResolutionPort
SemanticEmbeddingIndexer.index_port: EmbeddingIndexPort
```

If a service needs multiple capabilities, define a local protocol in `app/core/ports.py` with the exact union of methods used by that service.

- [ ] **Step 5: Run type and focused tests**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_skill_registry_service.py tests/unit/test_skill_search_service.py tests/unit/test_skill_fetch_service.py tests/unit/test_skill_resolution_service.py tests/integration/test_semantic_embedding_indexing.py -q
UV_CACHE_DIR=.uv-cache uv run --extra dev mypy app
```

Expected: tests and mypy pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add app/core/ports.py app/core/skills/registry.py app/core/skills/search.py app/core/skills/fetch.py app/core/skills/resolution.py app/core/skills/embedding_indexing.py app/persistence/skill_registry_repository.py app/service_container.py tests/unit/test_skill_registry_service.py tests/unit/test_skill_search_service.py tests/unit/test_skill_fetch_service.py tests/unit/test_skill_resolution_service.py tests/integration/test_semantic_embedding_indexing.py
git commit -m "refactor: split catalog repository capability ports"
```

Expected: one architecture refactor commit with no behavior change.

### Task 9: Split The Large Skill Registry Integration Bucket

**Files:**
- Modify: `tests/integration/test_skill_registry_endpoints.py`
- Create: `tests/integration/test_publish_endpoints.py`
- Create: `tests/integration/test_discovery_endpoints.py`
- Create: `tests/integration/test_exact_fetch_endpoints.py`
- Create: `tests/integration/test_governance_endpoints.py`
- Create: `tests/integration/test_resolution_endpoints.py`

- [ ] **Step 1: Confirm prerequisite architecture cleanup**

Run:

```bash
git log --oneline -n 20
wc -l tests/integration/test_skill_registry_endpoints.py
```

Expected: task 8 is complete and the source file is still around 1350 lines.

- [ ] **Step 2: Request approval before editing tests**

Ask:

```text
This task is test-file-only restructuring of tests/integration/test_skill_registry_endpoints.py. Do you approve these test edits?
```

Expected: approval before moving tests.

- [ ] **Step 3: Move helper fixtures only if shared by at least two files**

If helpers are shared, create `tests/integration/skill_endpoint_helpers.py` with pure helper functions copied from the current file:

```python
"""Shared helpers for registry endpoint integration tests."""
```

Move only helpers used by multiple new files. Keep single-use helpers local to their new test file.

- [ ] **Step 4: Move tests by route family**

Use this mapping:

```text
Publish and multipart validation -> tests/integration/test_publish_endpoints.py
POST /discovery behavior -> tests/integration/test_discovery_endpoints.py
GET /skills and exact content -> tests/integration/test_exact_fetch_endpoints.py
Admin/governance routes -> tests/integration/test_governance_endpoints.py
GET /resolution -> tests/integration/test_resolution_endpoints.py
```

Do not rewrite assertions during the move.

- [ ] **Step 5: Leave a removal assertion**

After moving all tests, delete `tests/integration/test_skill_registry_endpoints.py`. Do not keep an empty shim file.

- [ ] **Step 6: Run each new file**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/integration/test_publish_endpoints.py -q
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/integration/test_discovery_endpoints.py -q
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/integration/test_exact_fetch_endpoints.py -q
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/integration/test_governance_endpoints.py -q
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/integration/test_resolution_endpoints.py -q
```

Expected: each file passes independently.

- [ ] **Step 7: Run full integration suite**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/integration -q
```

Expected: integration suite passes with no changed assertions.

- [ ] **Step 8: Commit**

Run:

```bash
git add tests/integration/test_publish_endpoints.py tests/integration/test_discovery_endpoints.py tests/integration/test_exact_fetch_endpoints.py tests/integration/test_governance_endpoints.py tests/integration/test_resolution_endpoints.py
git add -u tests/integration/test_skill_registry_endpoints.py
git add tests/integration/skill_endpoint_helpers.py
git commit -m "test: split registry endpoint integration coverage"
```

Expected: one test-organization commit.

### Task 10: Mark Historical Changelogs And Link-Check Exceptions

**Files:**
- Create: `docs/reference/historical-docs.md`
- Modify: `docs/README.md`
- Modify: `docs/changelog/05-metadata-search-ranking-changelog.md`
- Modify: `docs/changelog/11-operability-and-release-readiness-changelog.md`
- Modify: `docs/changelog/14-production-security-baseline-and-service-token-governance-changelog.md`
- Modify: `tests/unit/test_public_contract_docs.py`

- [ ] **Step 1: Request approval before editing tests**

Ask:

```text
The historical changelog cleanup needs docs-contract tests updated. Do you approve this test edit?
```

Expected: approval before test changes.

- [ ] **Step 2: Write the historical-docs contract test**

In `tests/unit/test_public_contract_docs.py`, add:

```python
@pytest.mark.unit
def test_historical_changelogs_are_marked_as_historical_contract_records() -> None:
    historical = Path("docs/reference/historical-docs.md").read_text(encoding="utf-8")

    assert "docs/changelog/11-operability-and-release-readiness-changelog.md" in historical
    assert "describes the former `/metrics` route" in historical
    assert "docs/reference/api-contract.md" in historical
```

- [ ] **Step 3: Run the focused failing test**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_public_contract_docs.py::test_historical_changelogs_are_marked_as_historical_contract_records -q
```

Expected: fail because `docs/reference/historical-docs.md` does not exist.

- [ ] **Step 4: Create historical docs reference**

Create `docs/reference/historical-docs.md`:

```markdown
# Historical Docs

This file identifies documentation that is intentionally historical and may describe routes, files, or deployment assets that no longer exist in the live contract.

Current contract sources remain:

- [`api-contract.md`](api-contract.md)
- [`runtime-profiles.md`](runtime-profiles.md)
- [`observability-grafana-cloud.md`](observability-grafana-cloud.md)
- [`../architecture/render-neon-deployment.md`](../architecture/render-neon-deployment.md)

Historical changelog notes:

- `docs/changelog/11-operability-and-release-readiness-changelog.md` describes the former `/metrics` route and local Prometheus assets from the operability milestone.
- `docs/changelog/14-production-security-baseline-and-service-token-governance-changelog.md` describes the protected `/metrics` transition before telemetry moved fully to OTLP push.
- `docs/changelog/05-metadata-search-ranking-changelog.md` contains older route and docs paths retained as milestone history.
```

- [ ] **Step 5: Add historical banner to affected changelogs**

At the top of each affected changelog after the title, add:

```markdown
> Historical note: this changelog records the milestone state at the time it shipped. For the current live HTTP route surface, use [`../reference/api-contract.md`](../reference/api-contract.md).
```

- [ ] **Step 6: Link the historical-docs reference**

In `docs/README.md`, add `docs/reference/historical-docs.md` under reference docs.

- [ ] **Step 7: Run focused docs tests**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_public_contract_docs.py -q
```

Expected: pass.

- [ ] **Step 8: Commit**

Run:

```bash
git add docs/reference/historical-docs.md docs/README.md docs/changelog/05-metadata-search-ranking-changelog.md docs/changelog/11-operability-and-release-readiness-changelog.md docs/changelog/14-production-security-baseline-and-service-token-governance-changelog.md tests/unit/test_public_contract_docs.py
git commit -m "docs: mark historical changelog contracts"
```

Expected: one docs-history commit.

## Final Verification

- [ ] **Step 1: Run targeted quality checks**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev ruff check app tests
UV_CACHE_DIR=.uv-cache uv run --extra dev mypy app
```

Expected: both pass.

- [ ] **Step 2: Run canonical gates**

Run:

```bash
make quality
make test
```

Expected: both pass.

- [ ] **Step 3: Check dirty files before final handoff**

Run:

```bash
git status --short
```

Expected: only intentional files from the active task are dirty before each commit; known Bruno collection/workspace dirt remains ignored unless it was intentionally touched by a separate request.

## Self-Review

- Spec coverage result: covered all 10 audit findings. Tasks 1-4 handle docs/dependency/config/telemetry first; tasks 5-7 cover boundary, indexing, and co-usage decisions; tasks 8-10 defer port/test/changelog cleanup until safer prerequisites land.
- Placeholder scan result: clean. Every task has exact files, commands, expected results, and commit messages.
- Type/path consistency result: paths match the current repo scan: `app/core/skills/search.py`, `app/core/settings.py`, `app/persistence/skill_registry_repository.py`, `app/core/dependencies.py`, `tests/unit/test_layering_imports.py`, `tests/integration/test_skill_registry_endpoints.py`, `render.yaml`, and `docs/architecture/render-neon-deployment.md`.
