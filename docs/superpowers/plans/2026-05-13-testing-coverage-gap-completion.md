# Testing Coverage Gap Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the missing functional, integration, and security test coverage identified in the testing coverage gap audit without expanding dev-tool-only coverage.

**Architecture:** Add focused pytest coverage at the layer where each risk can fail: governance unit tests for policy decisions, HTTP integration tests for repository/container/API wiring, archive unit tests for hostile tar shapes, migration integration tests for downgrade data behavior, and workflow parsing tests for CI deployment semantics. Keep code changes minimal and only in the production files named by the failing tests.

**Tech Stack:** FastAPI `TestClient`, pytest, SQLAlchemy, Alembic, pgvector-backed Postgres integration fixtures, PyYAML or `ruamel.yaml` if already available or explicitly approved, `uv`, `make quality`, `make test`.

---

## Scope

This plan covers test additions and any minimal production fixes required to make those tests pass:

- Restricted policy-pack read visibility across exact metadata, content, resolution, and discovery.
- Semantic discovery through the real HTTP route, service container, repository, and Postgres path in `shadow` and `hybrid` modes.
- Hostile `.tar.zst` archive member validation for path traversal and unsafe tar entry types.
- Alembic `0006_embedding_processing_status` downgrade data behavior.
- Enterprise admin API error mapping for missing and duplicate admin resources.
- CI workflow YAML syntax and deploy hook/ref construction semantics.
- Root status HTML route/resource regression coverage.

Execution note: this repository prefers approval before changing tests to avoid drift. Use this plan as the approval checkpoint; during implementation, stop before editing tests if the user has not explicitly approved test edits in that session.

## Non-Goals

- Do not add Bruno, Hoppscotch, Postman, or other dev-tool-only coverage.
- Do not redesign discovery ranking or change the semantic contract: lexical remains `name + description`, semantic remains `description + tags`, modes remain `off -> shadow -> hybrid`, and the compatibility key remains `openai:text-embedding-3-small:description-tags-v1`.
- Do not broaden public API routes or OpenAPI exposure.
- Do not consolidate unrelated endpoint tests into one large rewrite.
- Do not introduce a new test runtime profile.

## File Map

- Modify: `tests/unit/test_governance.py` for policy-pack read decisions.
- Modify: `tests/integration/test_skill_registry_endpoints.py` only for admin error mapping and restricted policy-pack HTTP coverage that benefits from existing publish helpers.
- Create: `tests/integration/test_semantic_discovery_api.py` for HTTP/container/repository semantic discovery.
- Modify: `tests/unit/test_skill_bundle_validation.py` for hostile tar member shapes.
- Modify if tests require it: `app/core/skills/bundle_archive.py` for archive member validation.
- Modify: `tests/integration/test_migrations.py` for `0006` downgrade data behavior.
- Modify only if tests expose a bug: `alembic/versions/0006_embedding_processing_status.py`.
- Modify: `tests/unit/test_ci_workflows.py` for parsed YAML and deploy/ref semantics.
- Modify if parser dependency is approved: `pyproject.toml`, `uv.lock`.
- Modify: `tests/integration/test_health_endpoints.py` for root status page route/resource coverage.
- Modify only if test exposes a regression: `app/interface/api/root.py`, `app/interface/api/resource/root.html`.
- Inspect only unless failing tests point here: `app/core/governance.py`, `app/core/skills/search.py`, `app/service_container.py`, `app/persistence/skill_registry_repository.py`, `app/interface/api/enterprise.py`.

## Coverage Matrix

| Gap | Test Level | File | Behavior | Risk Protected |
| --- | --- | --- | --- | --- |
| Restricted policy-pack read restrictions | Unit and integration | `tests/unit/test_governance.py`, `tests/integration/test_skill_registry_endpoints.py` | Unauthorized readers cannot exact-read metadata/content/resolution or discover restricted versions; allowed token or namespace can | Prevents private policy-pack bypass through projection mapping or API path differences |
| Semantic discovery HTTP path | Integration | `tests/integration/test_semantic_discovery_api.py` | Published indexed embeddings are queried through `POST /discovery`; `shadow` preserves lexical ordering; `hybrid` can return semantic-only candidates | Protects service container wiring, provider injection, semantic SQL, and rollout mode semantics |
| Hostile archive members | Unit | `tests/unit/test_skill_bundle_validation.py` | Reject `../`, absolute paths, symlinks, hardlinks, device entries, duplicate paths, and empty archives | Prevents unsafe archive shapes from becoming accepted registry artifacts |
| Alembic 0006 downgrade data behavior | Integration | `tests/integration/test_migrations.py` | `processing` embedding rows become `stale` before the old check constraint is restored | Prevents downgrade failures and invalid historical state |
| Enterprise admin error mapping | Integration, optional unit service | `tests/integration/test_skill_registry_endpoints.py` | Missing organization, namespace, policy pack, duplicate organization, and duplicate namespace produce stable API errors | Prevents persistence exceptions from leaking as 500s and keeps admin contracts predictable |
| Workflow YAML validation | Unit | `tests/unit/test_ci_workflows.py` | Workflows parse as YAML; master deploy hook appends `ref=${GITHUB_SHA}` safely; deployment env and required secrets are structured | Prevents string-test false positives and malformed deploy workflows |
| Root status page | Integration | `tests/integration/test_health_endpoints.py` | `GET /` returns HTML and references `/healthz`, `/readyz`, and `/docs` | Prevents landing/status resource regressions outside OpenAPI route tests |

## Task 1: Restricted Policy-Pack Read Visibility

**Files:**
- Modify: `tests/unit/test_governance.py`
- Modify: `tests/integration/test_skill_registry_endpoints.py`
- Inspect if failing: `app/core/governance.py`
- Inspect if failing: `app/persistence/skill_registry_repository.py`

- [ ] **Step 1: Add unit tests for restricted policy-pack read decisions**

Add these tests to `tests/unit/test_governance.py`:

```python
from app.core.governance import PolicyPack


@pytest.mark.unit
def test_governance_policy_blocks_reader_not_allowed_by_restricted_policy_pack() -> None:
    policy = GovernancePolicy(
        profile=Settings.model_validate(
            {"DATABASE_URL": "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude"}
        ).active_policy
    )

    with pytest.raises(PolicyViolation) as exc_info:
        policy.ensure_exact_read_allowed(
            caller=CallerIdentity(token_id="reader-token", scopes=frozenset({"read"})),
            lifecycle_status="published",
            namespace="acme.private",
            review_state="approved",
            promotion_channel="prod",
            trust_tier="verified",
            policy_pack=PolicyPack(
                slug="restricted-pack",
                rules={
                    "visibility": "restricted",
                    "allowed_token_ids": ["private-reader"],
                    "allowed_namespaces": ["acme.private"],
                },
            ),
        )

    assert exc_info.value.code == "POLICY_PACK_READ_FORBIDDEN"
    assert exc_info.value.details == {
        "policy_pack": "restricted-pack",
        "namespace": "acme.private",
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    ("caller", "namespace"),
    [
        (
            CallerIdentity(token_id="private-reader", scopes=frozenset({"read"})),
            "other.namespace",
        ),
        (
            CallerIdentity(
                token_id="reader-token",
                scopes=frozenset({"read"}),
                namespace_grants=(
                    NamespaceGrant(
                        namespace="acme.private",
                        roles=frozenset({"read"}),
                        promotion_channels=frozenset({"prod"}),
                    ),
                ),
            ),
            "acme.private",
        ),
    ],
)
def test_governance_policy_allows_restricted_policy_pack_by_token_or_namespace(
    caller: CallerIdentity,
    namespace: str,
) -> None:
    policy = GovernancePolicy(
        profile=Settings.model_validate(
            {"DATABASE_URL": "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/aptitude"}
        ).active_policy
    )

    policy.ensure_exact_read_allowed(
        caller=caller,
        lifecycle_status="published",
        namespace=namespace,
        review_state="approved",
        promotion_channel="prod",
        trust_tier="verified",
        policy_pack=PolicyPack(
            slug="restricted-pack",
            rules={
                "visibility": "restricted",
                "allowed_token_ids": ["private-reader"],
                "allowed_namespaces": ["acme.private"],
            },
        ),
    )
```

- [ ] **Step 2: Run the governance red check**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_governance.py::test_governance_policy_blocks_reader_not_allowed_by_restricted_policy_pack tests/unit/test_governance.py::test_governance_policy_allows_restricted_policy_pack_by_token_or_namespace -q
```

Expected: the new tests either pass if the policy layer already enforces the contract, or fail with an exact code/detail mismatch that points to `app/core/governance.py`.

- [ ] **Step 3: Add HTTP integration coverage for restricted policy packs**

Add a dedicated test near the enterprise workflow tests in `tests/integration/test_skill_registry_endpoints.py`:

```python
@pytest.mark.integration
def test_restricted_policy_pack_blocks_unlisted_reader_across_read_surfaces(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    private_reader_secret = "dev-private-reader-secret"
    token_records = [
        *DEFAULT_AUTH_SERVICE_TOKENS,
        _token_record(
            token_id="private-reader",
            secret=private_reader_secret,
            scopes=["read"],
            namespace_grants=[
                {
                    "namespace": "acme.private",
                    "roles": ["read"],
                    "promotion_channels": ["prod"],
                }
            ],
        ),
    ]
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    monkeypatch.setenv("AUTH_SERVICE_TOKENS_JSON", json.dumps(token_records))
    suffix = uuid4().hex
    slug = f"python.restricted.policy.{suffix}"
    private_headers = {"Authorization": f"Bearer private-reader.{private_reader_secret}"}

    with TestClient(create_app()) as client:
        org = client.post(
            "/admin/organizations",
            json={"slug": f"acme-{suffix}", "display_name": "Acme Restricted"},
            headers=_headers("admin-token"),
        )
        namespace = client.post(
            "/admin/namespaces",
            json={
                "slug": "acme.private",
                "organization_slug": f"acme-{suffix}",
                "visibility": "private",
            },
            headers=_headers("admin-token"),
        )
        pack = client.put(
            "/admin/policy-packs/restricted-pack",
            json={
                "description": "Reader allow-list regression fixture",
                "rules": {
                    "visibility": "restricted",
                    "allowed_token_ids": ["private-reader"],
                    "allowed_namespaces": ["acme.private"],
                },
            },
            headers=_headers("admin-token"),
        )
        published = _publish(
            client,
            slug,
            _request(
                "1.0.0",
                name="Restricted Policy Candidate",
                description="Restricted policy discovery fixture",
                tags=["python", "restricted"],
                trust_tier="verified",
            )
            | {
                "governance": {
                    "trust_tier": "verified",
                    "namespace": "acme.private",
                    "artifact_origin": "verified",
                    "review_state": "approved",
                    "promotion_channel": "prod",
                    "policy_pack_slug": "restricted-pack",
                    "provenance": {
                        "repo_url": "https://github.com/acme/private-skill",
                        "commit_sha": "0123456789abcdef0123456789abcdef01234567",
                        "tree_path": "skills/restricted",
                    },
                }
            },
            token="admin-token",
        )

        unauthorized_discovery = client.post(
            "/discovery",
            json={"name": "Restricted Policy Candidate"},
            headers=_headers("reader-token"),
        )
        unauthorized_resolution = client.get(
            f"/resolution/{slug}/1.0.0",
            headers=_headers("reader-token"),
        )
        unauthorized_metadata = client.get(
            f"/skills/{slug}/1.0.0",
            headers=_headers("reader-token"),
        )
        unauthorized_content = client.get(
            f"/skills/{slug}/1.0.0/content",
            headers=_headers("reader-token"),
        )
        allowed_discovery = client.post(
            "/discovery",
            json={"name": "Restricted Policy Candidate"},
            headers=private_headers,
        )
        allowed_metadata = client.get(f"/skills/{slug}/1.0.0", headers=private_headers)
        allowed_content = client.get(f"/skills/{slug}/1.0.0/content", headers=private_headers)

    assert org.status_code == 201, org.text
    assert namespace.status_code == 201, namespace.text
    assert pack.status_code == 200, pack.text
    assert published["policy_pack_slug"] == "restricted-pack"

    assert unauthorized_discovery.status_code == 200
    assert slug not in unauthorized_discovery.json()["candidates"]
    assert unauthorized_resolution.status_code == 403
    assert unauthorized_resolution.json()["error"]["code"] == "POLICY_PACK_READ_FORBIDDEN"
    assert unauthorized_metadata.status_code == 403
    assert unauthorized_metadata.json()["error"]["code"] == "POLICY_PACK_READ_FORBIDDEN"
    assert unauthorized_content.status_code == 403
    assert unauthorized_content.json()["error"]["code"] == "POLICY_PACK_READ_FORBIDDEN"

    assert allowed_discovery.status_code == 200
    assert slug in allowed_discovery.json()["candidates"]
    assert allowed_metadata.status_code == 200
    assert allowed_metadata.json()["policy_pack_slug"] == "restricted-pack"
    assert allowed_content.status_code == 200
    assert allowed_content.content == _bundle("# Python Lint\n\nLint Python files.\n")
```

- [ ] **Step 4: Run the restricted policy-pack integration red check**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/integration/test_skill_registry_endpoints.py::test_restricted_policy_pack_blocks_unlisted_reader_across_read_surfaces -q
```

Expected: the test passes if repository projection already maps `policy_pack_slug` and rules into exact-read/discovery records. If it fails, expected failures are `slug in unauthorized_discovery.json()["candidates"]`, `200` instead of `403`, or missing `POLICY_PACK_READ_FORBIDDEN`.

- [ ] **Step 5: Apply minimal green fixes only if the new tests fail**

If needed, fix only:

```python
# app/persistence/skill_registry_repository.py
# Ensure search/exact projections include the attached pack data.
policy_pack=(
    None
    if row["policy_pack_slug"] is None
    else PolicyPack(
        slug=str(row["policy_pack_slug"]),
        rules=dict(row["policy_pack_rules"] or {}),
    )
)
```

or:

```python
# app/core/governance.py
if visibility == "restricted" and (
    caller.token_id not in allowed_token_ids and namespace not in allowed_namespaces
):
    raise PolicyViolation(
        code="POLICY_PACK_READ_FORBIDDEN",
        message="Caller is not allowed by the attached policy pack.",
        details={"policy_pack": policy_pack.slug, "namespace": namespace},
    )
```

- [ ] **Step 6: Run the focused green check**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_governance.py tests/integration/test_skill_registry_endpoints.py::test_restricted_policy_pack_blocks_unlisted_reader_across_read_surfaces -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```bash
git add tests/unit/test_governance.py tests/integration/test_skill_registry_endpoints.py app/core/governance.py app/persistence/skill_registry_repository.py
git commit -m "test: cover restricted policy-pack read visibility"
```

## Task 2: Semantic Discovery Through HTTP, Container, and Repository

**Files:**
- Create: `tests/integration/test_semantic_discovery_api.py`
- Inspect if failing: `app/service_container.py`
- Inspect if failing: `app/core/skills/search.py`
- Inspect if failing: `app/persistence/skill_registry_repository.py`

- [ ] **Step 1: Create a focused semantic discovery integration test file**

Create `tests/integration/test_semantic_discovery_api.py`:

```python
"""Integration tests for semantic discovery through the HTTP API."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.ports import SkillEmbeddingIndexRecord
from app.main import create_app
from app.persistence.db import get_session_factory
from app.persistence.skill_registry_repository import SQLAlchemySkillCatalogRepository
from tests.integration.test_skill_registry_endpoints import _headers, _publish, _request

PLAN18_INDEX_KEY = "openai:text-embedding-3-small:description-tags-v1"


class _DeterministicEmbeddingProvider:
    def __init__(self, vectors: dict[str, tuple[float, ...]]) -> None:
        self.vectors = vectors
        self.calls: list[tuple[str, str, int, int]] = []

    def embed_query(
        self,
        *,
        text: str,
        model: str,
        dimensions: int,
        timeout_ms: int,
    ) -> tuple[float, ...]:
        self.calls.append((text, model, dimensions, timeout_ms))
        return self.vectors[text]


def _index_first_embedding(
    *,
    repository: SQLAlchemySkillCatalogRepository,
    vector: tuple[float, ...],
) -> None:
    work_items = repository.claim_skill_embedding_work(
        embedding_model=PLAN18_INDEX_KEY,
        limit=1,
        reclaim_after_seconds=3600,
    )
    assert len(work_items) == 1
    work = work_items[0]
    repository.index_skill_embedding(
        record=SkillEmbeddingIndexRecord(
            skill_version_fk=work.skill_version_fk,
            embedding_model=PLAN18_INDEX_KEY,
            embedding_dimensions=len(vector),
            source_checksum_digest=work.source_checksum_digest,
            embedding_vector=vector,
        )
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    ("semantic_mode", "expected_order"),
    [
        ("shadow", ("python.lexical.",)),
        ("hybrid", ("python.semantic.", "python.lexical.")),
    ],
)
def test_semantic_discovery_api_modes_use_container_provider_and_repository_path(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
    semantic_mode: str,
    expected_order: tuple[str, ...],
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    monkeypatch.setenv("SEMANTIC_DISCOVERY_MODE", semantic_mode)
    monkeypatch.setenv("SEMANTIC_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")
    monkeypatch.setenv("SEMANTIC_EMBEDDING_INDEX_KEY", PLAN18_INDEX_KEY)
    monkeypatch.setenv("SEMANTIC_EMBEDDING_DIMENSIONS", "3")
    query_text = "static checks python quality"
    provider = _DeterministicEmbeddingProvider({query_text: (0.01, 0.01, 0.01)})
    monkeypatch.setattr("app.service_container.OpenAIEmbeddingProvider", lambda **_: provider)

    suffix = uuid4().hex
    lexical_slug = f"python.lexical.{suffix}"
    semantic_slug = f"python.semantic.{suffix}"

    with TestClient(create_app()) as client:
        _publish(
            client,
            lexical_slug,
            _request(
                "1.0.0",
                name="Static Checks Python",
                description="Lexical static checks python quality",
                tags=["python", "quality"],
            ),
        )
        _publish(
            client,
            semantic_slug,
            _request(
                "1.0.0",
                name="Unrelated Name",
                description="Static checks python quality",
                tags=["python", "quality"],
            ),
        )

        repository = SQLAlchemySkillCatalogRepository(
            get_session_factory(),
            semantic_embedding_index_key=PLAN18_INDEX_KEY,
            semantic_embedding_dimensions=3,
        )
        _index_first_embedding(repository=repository, vector=(0.99, 0.99, 0.99))
        _index_first_embedding(repository=repository, vector=(0.01, 0.01, 0.01))

        discovery = client.post(
            "/discovery",
            json={
                "description": "Static checks",
                "tags": ["python", "quality"],
                "limit": 5,
            },
            headers=_headers("reader-token"),
        )

    assert discovery.status_code == 200, discovery.text
    candidates = discovery.json()["candidates"]
    assert provider.calls == [(query_text, "text-embedding-3-small", 3, 150)]
    assert candidates[0].startswith(expected_order[0])
    if semantic_mode == "shadow":
        assert semantic_slug not in candidates[:1]
    else:
        assert candidates[:2] == [semantic_slug, lexical_slug]
```

- [ ] **Step 2: Run the semantic HTTP red check**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/integration/test_semantic_discovery_api.py -q
```

Expected: failures should identify real integration gaps, such as the provider not being constructed from settings, wrong semantic source text, vector dimension mismatch, `shadow` reordering results, or `hybrid` not returning the semantic-only candidate.

- [ ] **Step 3: Apply minimal green fixes only if the test exposes a bug**

Use these constraints for fixes:

```python
# app/service_container.py
# The provider should be present only when semantic discovery is enabled and configured.
if settings.semantic_discovery_mode == "off":
    return None
if settings.semantic_embedding_provider == "openai" and settings.openai_api_key is not None:
    return OpenAIEmbeddingProvider(api_key=settings.openai_api_key)
return None
```

```python
# app/core/skills/search.py
# Shadow mode may execute semantic lookup for observability, but must not alter response order.
if self._semantic_discovery_mode == "shadow":
    semantic_results = ()
```

```python
# app/persistence/skill_registry_repository.py
# Search semantic candidates must respect index key, dimensions, lifecycle, namespace, review,
# promotion, trust, and policy-pack visibility filters already used by lexical discovery.
```

- [ ] **Step 4: Run the semantic green and nearby regression checks**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/integration/test_semantic_discovery_api.py tests/unit/test_skill_search_service.py tests/integration/test_semantic_embedding_indexing.py -q
```

Expected: all selected semantic tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_semantic_discovery_api.py app/service_container.py app/core/skills/search.py app/persistence/skill_registry_repository.py
git commit -m "test: cover semantic discovery api rollout modes"
```

## Task 3: Hostile Tar Member Validation

**Files:**
- Modify: `tests/unit/test_skill_bundle_validation.py`
- Modify if failing: `app/core/skills/bundle_archive.py`
- Inspect: `app/interface/validation/skill_bundle.py`

- [ ] **Step 1: Add archive-builder helpers for unsafe member shapes**

Add these helpers to `tests/unit/test_skill_bundle_validation.py`:

```python
import tarfile
from io import BytesIO

import zstandard


def _tar_zst_with_members(members: list[tarfile.TarInfo]) -> bytes:
    tar_buffer = BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w") as archive:
        for member in members:
            payload = b"" if member.size == 0 else b"x" * member.size
            archive.addfile(member, BytesIO(payload))
    return zstandard.ZstdCompressor().compress(tar_buffer.getvalue())


def _regular_member(name: str, payload: bytes = b"content") -> tarfile.TarInfo:
    member = tarfile.TarInfo(name)
    member.size = len(payload)
    member.mode = 0o644
    member.mtime = 0
    return member
```

- [ ] **Step 2: Add parametrized path and type rejection tests**

Add:

```python
@pytest.mark.unit
@pytest.mark.parametrize(
    "member",
    [
        _regular_member("../escape.txt"),
        _regular_member("skill-bundle/../escape.txt"),
        _regular_member("/absolute/path.txt"),
    ],
)
def test_validate_skill_bundle_rejects_unsafe_member_paths(member: tarfile.TarInfo) -> None:
    with pytest.raises(SkillBundleValidationError, match="safe relative paths"):
        validate_skill_bundle(
            _tar_zst_with_members([member]),
            filename="python-lint.tar.zst",
            media_type="application/zstd",
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "member",
    [
        tarfile.TarInfo("skill-bundle/link"),
        tarfile.TarInfo("skill-bundle/hardlink"),
        tarfile.TarInfo("skill-bundle/device"),
    ],
)
def test_validate_skill_bundle_rejects_non_regular_members(member: tarfile.TarInfo) -> None:
    if member.name.endswith("link"):
        member.type = tarfile.SYMTYPE
        member.linkname = "skill-bundle/SKILL.md"
    elif member.name.endswith("hardlink"):
        member.type = tarfile.LNKTYPE
        member.linkname = "skill-bundle/SKILL.md"
    else:
        member.type = tarfile.CHRTYPE
        member.devmajor = 1
        member.devminor = 3

    with pytest.raises(SkillBundleValidationError, match="regular files"):
        validate_skill_bundle(
            _tar_zst_with_members([member]),
            filename="python-lint.tar.zst",
            media_type="application/zstd",
        )
```

- [ ] **Step 3: Add duplicate and empty archive tests**

Add:

```python
@pytest.mark.unit
def test_validate_skill_bundle_rejects_duplicate_member_paths() -> None:
    with pytest.raises(SkillBundleValidationError, match="duplicate member path"):
        validate_skill_bundle(
            _tar_zst_with_members(
                [
                    _regular_member("skill-bundle/SKILL.md", b"first"),
                    _regular_member("skill-bundle/SKILL.md", b"second"),
                ]
            ),
            filename="python-lint.tar.zst",
            media_type="application/zstd",
        )


@pytest.mark.unit
def test_validate_skill_bundle_rejects_empty_archives() -> None:
    with pytest.raises(SkillBundleValidationError, match="at least one file"):
        validate_skill_bundle(
            _tar_zst_with_members([]),
            filename="python-lint.tar.zst",
            media_type="application/zstd",
        )
```

- [ ] **Step 4: Run the archive validation red check**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_skill_bundle_validation.py -q
```

Expected: new hostile-shape tests fail until `inspect_skill_bundle` validates normalized paths, member types, duplicates, and non-empty archives.

- [ ] **Step 5: Implement minimal archive validation**

Update `app/core/skills/bundle_archive.py` with logic equivalent to:

```python
from pathlib import PurePosixPath


def _validate_member(member: tarfile.TarInfo, seen_paths: set[str]) -> int:
    path = PurePosixPath(member.name)
    if member.name.startswith("/") or path.is_absolute() or ".." in path.parts:
        raise SkillBundleArchiveError("Skill artifact members must use safe relative paths.")
    if not member.isfile():
        raise SkillBundleArchiveError("Skill artifact members must be regular files.")
    if member.name in seen_paths:
        raise SkillBundleArchiveError("Skill artifact contains a duplicate member path.")
    seen_paths.add(member.name)
    return len(member.name.encode("utf-8"))
```

Then call `_validate_member(member, seen_paths)` inside the existing archive iteration and raise:

```python
if member_count == 0:
    raise SkillBundleArchiveError("Skill artifact must contain at least one file.")
```

- [ ] **Step 6: Ensure interface validation maps archive errors clearly**

If needed, update `app/interface/validation/skill_bundle.py` to preserve the hostile-shape messages:

```python
raise SkillBundleValidationError(message.replace("`", "")) from exc
```

Keep existing file-count and path-length messages stable.

- [ ] **Step 7: Run the archive green check**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_skill_bundle_validation.py -q
```

Expected: all bundle validation tests pass.

- [ ] **Step 8: Commit**

```bash
git add tests/unit/test_skill_bundle_validation.py app/core/skills/bundle_archive.py app/interface/validation/skill_bundle.py
git commit -m "test: cover hostile skill bundle archives"
```

## Task 4: Alembic 0006 Downgrade Data Behavior

**Files:**
- Modify: `tests/integration/test_migrations.py`
- Modify if failing: `alembic/versions/0006_embedding_processing_status.py`

- [ ] **Step 1: Add focused downgrade data test**

Add imports and test to `tests/integration/test_migrations.py`:

```python
from sqlalchemy import text
```

```python
@pytest.mark.integration
def test_0006_downgrade_marks_processing_embeddings_stale_before_restoring_constraint(
    clean_integration_database: str,
) -> None:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", clean_integration_database)

    command.upgrade(config, "head")
    engine = create_engine(clean_integration_database)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO skills (slug, namespace_fk)
                    VALUES (
                        'python.processing-downgrade',
                        (SELECT id FROM namespaces WHERE slug = 'public')
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO skill_versions (
                        skill_fk,
                        version,
                        lifecycle_status,
                        trust_tier,
                        artifact_origin,
                        review_state,
                        promotion_channel,
                        content_fk,
                        metadata_fk
                    )
                    SELECT
                        skills.id,
                        '1.0.0',
                        'published',
                        'untrusted',
                        'internal',
                        'approved',
                        'prod',
                        skill_contents.id,
                        skill_metadata.id
                    FROM skills
                    CROSS JOIN LATERAL (
                        INSERT INTO skill_contents (
                            sha256_digest,
                            size_bytes,
                            content_bytes,
                            media_type,
                            filename
                        )
                        VALUES ('a' || repeat('0', 63), 1, decode('00', 'hex'), 'application/zstd', 'skill.tar.zst')
                        RETURNING id
                    ) AS skill_contents
                    CROSS JOIN LATERAL (
                        INSERT INTO skill_metadata (
                            name,
                            description,
                            tags,
                            inputs_schema,
                            outputs_schema,
                            token_estimate,
                            maturity_score,
                            security_score
                        )
                        VALUES (
                            'Processing Downgrade',
                            'Processing downgrade fixture',
                            ARRAY['python'],
                            '{}'::jsonb,
                            '{}'::jsonb,
                            1,
                            0.1,
                            0.1
                        )
                        RETURNING id
                    ) AS skill_metadata
                    WHERE skills.slug = 'python.processing-downgrade'
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO skill_search_embeddings (
                        skill_version_fk,
                        embedding_model,
                        embedding_dimensions,
                        source_checksum_digest,
                        index_status
                    )
                    SELECT id, 'openai:text-embedding-3-small:description-tags-v1', 1536, repeat('b', 64), 'processing'
                    FROM skill_versions
                    WHERE version = '1.0.0'
                    """
                )
            )
    finally:
        engine.dispose()

    command.downgrade(config, "0005_semantic_discovery_signals")

    downgraded_engine = create_engine(clean_integration_database)
    try:
        with downgraded_engine.connect() as connection:
            status = connection.execute(
                text("SELECT index_status FROM skill_search_embeddings")
            ).scalar_one()
            check_sql = {
                constraint["name"]: constraint["sqltext"]
                for constraint in inspect(downgraded_engine).get_check_constraints(
                    "skill_search_embeddings"
                )
            }["ck_skill_search_embeddings_index_status"]
    finally:
        downgraded_engine.dispose()

    assert status == "stale"
    assert "processing" not in check_sql
```

- [ ] **Step 2: Run the migration red check**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/integration/test_migrations.py::test_0006_downgrade_marks_processing_embeddings_stale_before_restoring_constraint -q
```

Expected: pass if `0006` already updates data before restoring the old constraint; otherwise fail during downgrade with a check-constraint violation or with `status == "processing"`.

- [ ] **Step 3: Apply minimal migration fix if needed**

Ensure `alembic/versions/0006_embedding_processing_status.py` downgrade keeps this order:

```python
op.execute(
    """
    UPDATE skill_search_embeddings
    SET index_status = 'stale',
        updated_at = CURRENT_TIMESTAMP
    WHERE index_status = 'processing'
    """
)
op.execute("ALTER TABLE skill_search_embeddings DROP CONSTRAINT ck_skill_search_embeddings_index_status")
op.execute(
    """
    ALTER TABLE skill_search_embeddings
    ADD CONSTRAINT ck_skill_search_embeddings_index_status
    CHECK (index_status IN ('pending', 'indexed', 'failed', 'stale'))
    """
)
```

- [ ] **Step 4: Run migration green checks**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/integration/test_migrations.py -q
```

Expected: all migration integration tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_migrations.py alembic/versions/0006_embedding_processing_status.py
git commit -m "test: cover embedding processing downgrade behavior"
```

## Task 5: Enterprise Admin Error Mapping

**Files:**
- Modify: `tests/integration/test_skill_registry_endpoints.py`
- Inspect if failing: `app/interface/api/enterprise.py`
- Inspect if failing: `app/persistence/skill_registry_repository.py`
- Optional if integration failure needs service-level isolation: `tests/unit/test_skill_registry_service.py`

- [ ] **Step 1: Add integration tests for missing admin resources**

Add:

```python
@pytest.mark.integration
def test_enterprise_admin_missing_resource_errors_are_mapped(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python.enterprise.error.{uuid4().hex}"

    with TestClient(create_app()) as client:
        missing_org = client.post(
            "/admin/namespaces",
            json={
                "slug": "missing-org.namespace",
                "organization_slug": "missing-org",
                "visibility": "private",
            },
            headers=_headers("admin-token"),
        )
        missing_namespace = client.patch(
            f"/admin/skills/{slug}/ownership",
            json={"namespace": "missing.namespace"},
            headers=_headers("admin-token"),
        )
        _publish(client, slug, _request("1.0.0"), token="admin-token")
        missing_policy_pack = client.patch(
            f"/admin/skills/{slug}/1.0.0/governance",
            json={"policy_pack_slug": "missing-pack"},
            headers=_headers("admin-token"),
        )

    assert missing_org.status_code == 404
    assert missing_org.json()["error"]["code"] == "ORGANIZATION_NOT_FOUND"
    assert missing_org.json()["error"]["details"] == {"organization_slug": "missing-org"}
    assert missing_namespace.status_code == 404
    assert missing_namespace.json()["error"]["code"] == "NAMESPACE_NOT_FOUND"
    assert missing_policy_pack.status_code == 404
    assert missing_policy_pack.json()["error"]["code"] == "POLICY_PACK_NOT_FOUND"
```

- [ ] **Step 2: Add duplicate admin resource tests**

Add:

```python
@pytest.mark.integration
def test_enterprise_admin_duplicate_resource_errors_are_mapped(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    suffix = uuid4().hex
    org_slug = f"duplicate-{suffix}"
    namespace_slug = f"{org_slug}.private"

    with TestClient(create_app()) as client:
        first_org = client.post(
            "/admin/organizations",
            json={"slug": org_slug, "display_name": "Duplicate Org"},
            headers=_headers("admin-token"),
        )
        duplicate_org = client.post(
            "/admin/organizations",
            json={"slug": org_slug, "display_name": "Duplicate Org"},
            headers=_headers("admin-token"),
        )
        first_namespace = client.post(
            "/admin/namespaces",
            json={
                "slug": namespace_slug,
                "organization_slug": org_slug,
                "visibility": "private",
            },
            headers=_headers("admin-token"),
        )
        duplicate_namespace = client.post(
            "/admin/namespaces",
            json={
                "slug": namespace_slug,
                "organization_slug": org_slug,
                "visibility": "private",
            },
            headers=_headers("admin-token"),
        )

    assert first_org.status_code == 201, first_org.text
    assert duplicate_org.status_code == 409
    assert duplicate_org.json()["error"]["code"] == "ORGANIZATION_ALREADY_EXISTS"
    assert first_namespace.status_code == 201, first_namespace.text
    assert duplicate_namespace.status_code == 409
    assert duplicate_namespace.json()["error"]["code"] == "NAMESPACE_ALREADY_EXISTS"
```

- [ ] **Step 3: Run the admin error red check**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/integration/test_skill_registry_endpoints.py::test_enterprise_admin_missing_resource_errors_are_mapped tests/integration/test_skill_registry_endpoints.py::test_enterprise_admin_duplicate_resource_errors_are_mapped -q
```

Expected: failures likely surface as `500` responses from `SkillRegistryPersistenceError`; those are the exact regressions this task should convert to stable `404` or `409` responses.

- [ ] **Step 4: Apply minimal green fixes**

Prefer explicit domain errors rather than string-parsing persistence exceptions:

```python
# app/core/skills/models.py
class OrganizationNotFoundError(SkillRegistryError): ...
class NamespaceNotFoundError(SkillRegistryError): ...
class PolicyPackNotFoundError(SkillRegistryError): ...
class OrganizationAlreadyExistsError(SkillRegistryError): ...
class NamespaceAlreadyExistsError(SkillRegistryError): ...
```

Then map them in `app/interface/api/enterprise.py`:

```python
except OrganizationNotFoundError as exc:
    return error_response(
        request=http_request,
        status_code=status.HTTP_404_NOT_FOUND,
        code="ORGANIZATION_NOT_FOUND",
        message=str(exc),
        details={"organization_slug": exc.organization_slug},
    )
except NamespaceAlreadyExistsError as exc:
    return error_response(
        request=http_request,
        status_code=status.HTTP_409_CONFLICT,
        code="NAMESPACE_ALREADY_EXISTS",
        message=str(exc),
        details={"namespace": exc.namespace},
    )
```

Keep the exact response shape aligned with existing `error_response` usage and avoid changing successful admin payloads.

- [ ] **Step 5: Run admin endpoint green checks**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/integration/test_skill_registry_endpoints.py::test_enterprise_admin_missing_resource_errors_are_mapped tests/integration/test_skill_registry_endpoints.py::test_enterprise_admin_duplicate_resource_errors_are_mapped tests/integration/test_skill_registry_endpoints.py::test_enterprise_namespace_review_promotion_and_trust_evidence_workflow -q
```

Expected: missing and duplicate resource tests pass, and the existing enterprise workflow still passes.

- [ ] **Step 6: Commit**

```bash
git add tests/integration/test_skill_registry_endpoints.py app/interface/api/enterprise.py app/core/skills/models.py app/persistence/skill_registry_repository.py
git commit -m "test: cover enterprise admin error mapping"
```

## Task 6: CI Workflow YAML and Deployment Semantics

**Files:**
- Modify: `tests/unit/test_ci_workflows.py`
- Modify if dependency approved: `pyproject.toml`
- Modify if dependency approved: `uv.lock`
- Inspect if failing: `.github/workflows/master-push-ci.yml`

- [ ] **Step 1: Confirm parser dependency before editing**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev python - <<'PY'
import importlib.util
print("yaml", importlib.util.find_spec("yaml") is not None)
print("ruamel.yaml", importlib.util.find_spec("ruamel.yaml") is not None)
PY
```

Expected: at least one YAML parser is available. If neither is available, ask for approval before adding `pyyaml` as a dev dependency:

```bash
uv add --dev pyyaml
```

- [ ] **Step 2: Add parsed workflow helpers**

Update `tests/unit/test_ci_workflows.py`:

```python
import yaml


def workflow_yaml(name: str) -> dict[str, object]:
    return yaml.safe_load((WORKFLOWS_DIR / name).read_text())
```

- [ ] **Step 3: Add workflow syntax and semantic tests**

Add:

```python
@pytest.mark.unit
def test_all_ci_workflows_parse_as_yaml_documents() -> None:
    for path in WORKFLOWS_DIR.glob("*.yml"):
        document = yaml.safe_load(path.read_text())
        assert isinstance(document, dict), path.name
        assert "jobs" in document, path.name


@pytest.mark.unit
def test_master_push_deploy_hook_uses_current_commit_ref_and_safe_separator() -> None:
    document = workflow_yaml("master-push-ci.yml")
    production_deploy = document["jobs"]["production-deploy"]
    trigger_step = next(
        step
        for step in production_deploy["steps"]
        if step["name"] == "Trigger Render deploy for this commit"
    )

    assert trigger_step["env"] == {"REF": "${{ github.sha }}"}
    script = trigger_step["run"]
    assert "separator='?'" in script
    assert "*\\?*) separator='&'" in script
    assert 'curl -fsS -X POST "${RENDER_DEPLOY_HOOK_URL}${separator}ref=${REF}"' in script


@pytest.mark.unit
def test_master_push_deployment_job_requires_migration_and_render_secrets() -> None:
    document = workflow_yaml("master-push-ci.yml")
    production_deploy = document["jobs"]["production-deploy"]

    assert production_deploy["needs"] == ["final-local-gate"]
    assert production_deploy["env"] == {
        "DATABASE_URL": "${{ secrets.MIGRATION_DATABASE_URL }}",
        "MIGRATION_DATABASE_URL": "${{ secrets.MIGRATION_DATABASE_URL }}",
        "RENDER_DEPLOY_HOOK_URL": "${{ secrets.RENDER_DEPLOY_HOOK_URL }}",
    }
    secret_check = production_deploy["steps"][0]["run"]
    assert "MIGRATION_DATABASE_URL GitHub secret is required" in secret_check
    assert "RENDER_DEPLOY_HOOK_URL GitHub secret is required" in secret_check
```

- [ ] **Step 4: Run the workflow red check**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_ci_workflows.py -q
```

Expected: tests pass if workflow YAML is valid and deploy semantics are correct. If `yaml` is missing, the expected failure is `ModuleNotFoundError: No module named 'yaml'`, which must be resolved by approved dev dependency addition.

- [ ] **Step 5: Optionally add actionlint as a separate dependency decision**

If the team wants action-level validation, keep it outside pytest string checks and add a separate command after approval:

```bash
bunx actionlint .github/workflows/*.yml
```

Do not add this to `make quality` until the dependency and CI install path are explicit.

- [ ] **Step 6: Commit**

```bash
git add tests/unit/test_ci_workflows.py pyproject.toml uv.lock .github/workflows/master-push-ci.yml
git commit -m "test: parse ci workflows and validate deploy semantics"
```

## Task 7: Root Status Page Route and Resource Regression

**Files:**
- Modify: `tests/integration/test_health_endpoints.py`
- Inspect if failing: `app/interface/api/root.py`
- Inspect if failing: `app/interface/api/resource/root.html`

- [ ] **Step 1: Add root HTML integration test**

Add to `tests/integration/test_health_endpoints.py`:

```python
@pytest.mark.integration
def test_root_status_page_returns_html_and_links_operational_routes(
    monkeypatch: pytest.MonkeyPatch,
    require_integration_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", require_integration_database)
    monkeypatch.setenv("APP_ENV", "prod")

    with TestClient(create_app()) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    html = response.text
    assert "<title>Aptitude Registry / Status</title>" in html
    assert 'href="/healthz"' in html
    assert 'href="/readyz"' in html
    assert 'href="/docs"' in html
    assert "fetchJson('/healthz')" in html
    assert "fetchJson('/readyz')" in html
    assert "const probeCount = 2;" in html
```

- [ ] **Step 2: Run the root route red check**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/integration/test_health_endpoints.py::test_root_status_page_returns_html_and_links_operational_routes -q
```

Expected: pass if `GET /` still serves the checked-in status HTML. Failures point to missing route registration, broken content type, or drift in required operational links.

- [ ] **Step 3: Apply minimal green fixes if needed**

Keep fixes local:

```python
# app/interface/api/root.py
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def get_root() -> HTMLResponse:
    return HTMLResponse(ROOT_PAGE_HTML)
```

```html
<!-- app/interface/api/resource/root.html -->
<a href="/docs">API</a>
<a href="/healthz">Health</a>
<a href="/readyz">Readiness</a>
```

- [ ] **Step 4: Run root and boundary checks**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/integration/test_health_endpoints.py tests/unit/test_registry_api_boundary.py -q
```

Expected: root status page integration tests pass and OpenAPI boundary tests still exclude `/` from public schema.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_health_endpoints.py app/interface/api/root.py app/interface/api/resource/root.html
git commit -m "test: cover root status page resource"
```

## Task 8: Final Regression Gate and Coverage Review

**Files:**
- No new files unless previous tasks exposed minimal production fixes.

- [ ] **Step 1: Run targeted test suite**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest tests/unit/test_governance.py tests/unit/test_skill_bundle_validation.py tests/unit/test_ci_workflows.py tests/integration/test_semantic_discovery_api.py tests/integration/test_migrations.py tests/integration/test_health_endpoints.py tests/integration/test_skill_registry_endpoints.py -q
```

Expected: all targeted unit and integration tests pass or integration tests skip only when the configured Postgres test database is unreachable.

- [ ] **Step 2: Run canonical repository gates**

Run:

```bash
make quality
make test
```

Expected: both canonical gates pass. If `make test` skips integration tests due database availability, rerun with a reachable `TEST_DATABASE_URL` before merging.

- [ ] **Step 3: Run a focused coverage check for critical paths**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest \
  tests/unit/test_governance.py \
  tests/unit/test_skill_bundle_validation.py \
  tests/integration/test_semantic_discovery_api.py \
  tests/integration/test_skill_registry_endpoints.py::test_restricted_policy_pack_blocks_unlisted_reader_across_read_surfaces \
  --cov=app.core.governance \
  --cov=app.core.skills.bundle_archive \
  --cov=app.core.skills.search \
  --cov=app.persistence.skill_registry_repository \
  --cov-report=term-missing
```

Expected: the newly protected security-critical branches are shown as covered. Do not chase unrelated global percentage changes in this task.

- [ ] **Step 4: Commit final adjustments**

```bash
git status --short
git add tests/unit/test_governance.py tests/unit/test_skill_bundle_validation.py tests/unit/test_ci_workflows.py tests/integration/test_semantic_discovery_api.py tests/integration/test_migrations.py tests/integration/test_health_endpoints.py tests/integration/test_skill_registry_endpoints.py app/core/governance.py app/core/skills/bundle_archive.py app/core/skills/search.py app/service_container.py app/persistence/skill_registry_repository.py app/interface/api/enterprise.py app/interface/api/root.py app/interface/api/resource/root.html alembic/versions/0006_embedding_processing_status.py pyproject.toml uv.lock
git commit -m "test: complete registry coverage gap audit"
```

Expected: commit includes only files changed by the executed tasks. If some listed files were not changed, Git ignores them or reports no staged changes for those paths.

## Execution Order Recommendation

1. Start with Task 3 and Task 7 because they are narrow and should not require database debugging.
2. Run Task 1 before Task 2 so policy-pack visibility is protected before adding more discovery paths.
3. Run Task 4 before the full integration sweep because migration failures can block many tests.
4. Run Task 5 after Task 1 because both use enterprise fixtures.
5. Run Task 6 after test-only work unless a parser dependency decision is needed.
6. Finish with Task 8.

## Architectural Review Notes

- The plan keeps security behavior asserted at both policy and HTTP boundaries. Unit tests catch policy regressions quickly; integration tests prove repository projections and route-specific error mapping do not bypass policy.
- Semantic discovery is intentionally tested through HTTP with a mocked provider injected at the service-container seam. This avoids external OpenAI calls while still exercising settings, container construction, search service mode behavior, and SQL repository behavior.
- Archive validation belongs in `app/core/skills/bundle_archive.py` because unsafe tar shapes are artifact-format rules, not FastAPI request concerns. The interface layer should translate those errors, not reimplement archive inspection.
- Workflow validation should parse YAML and inspect structured jobs. String checks can remain as cheap contract locks, but they should not be the only proof that deployment YAML is well-formed.

## Self-Review

- Spec coverage: all seven audit findings map to tasks: policy-pack restrictions in Task 1, semantic HTTP discovery in Task 2, hostile archive validation in Task 3, Alembic downgrade behavior in Task 4, enterprise admin error mapping in Task 5, workflow validation in Task 6, and root status page regression in Task 7. Existing well-covered areas are referenced only as regression companions, not duplicated.
- Placeholder scan result: no placeholder markers or deferred-work phrases remain; each task names exact files, commands, expected outcomes, and representative assertions.
- Type/path consistency result: test names, paths, tokens, semantic key, mode names, endpoint paths, and command style match the current repository conventions observed in `tests/conftest.py`, `tests/integration/test_skill_registry_endpoints.py`, `tests/unit/test_skill_search_service.py`, and the semantic indexing tests.
