# Full Skill Directory Bundle Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current single-markdown skill artifact model with a full skill-directory bundle model, where the registry stores normalized discovery metadata plus one immutable zip bundle per published version.

**Architecture:** Keep discovery, governance, and resolution data normalized and queryable in PostgreSQL, but stop modeling skill content as raw markdown. Treat the exact skill artifact as one validated, digest-addressed zip bundle uploaded by the publisher and returned by exact content fetch. This is a deliberate breaking change to the current publish/content-fetch contract and requires explicit migration documentation.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, PostgreSQL, `zipfile`, `pathlib`, `hashlib`, pytest, ruff

---

## Summary

- Break the current publish/content contract on purpose:
  - publish no longer accepts `content.raw_markdown`
  - exact content fetch no longer returns `text/markdown`
- Keep metadata, description, relationships, governance, and discovery/ranking inputs outside the bundle as structured fields.
- Store one immutable zip bundle per version instead of storing parsed markdown/content/assets separately.
- Update the full fetch surface, not only the `/content` route:
  - `GET /skills/{slug}`
  - `GET /skills/{slug}/{version}`
  - `GET /skills/{slug}/{version}/content`
- Add a migration document that explains the contract break, storage change, compatibility stance, and upgrade path for publishers and consumers.

## Public Contract and Storage Changes

### Publish

- Change `POST /skills/{slug}` from JSON-with-markdown to bundle upload.
- Preferred request shape: `multipart/form-data` with:
  - one JSON part for publish metadata, relationships, governance, and provenance
  - one binary part for the zip bundle
- The publisher remains responsible for heavy pre-validation and archive creation.
- The server still performs authoritative artifact validation before persisting a version.

### Fetch

- `GET /skills/{slug}` remains the identity/version-list endpoint.
  - No route-path change.
  - No markdown-specific semantics should remain in its docs or examples.
- `GET /skills/{slug}/{version}` remains the exact metadata endpoint.
  - Its content summary becomes bundle-oriented instead of markdown-oriented.
  - Expected metadata fields include checksum digest, media type, and size bytes for the stored bundle.
- `GET /skills/{slug}/{version}/content` becomes exact zip download.
  - Response media type: `application/zip`
  - Preserve immutable cache semantics with digest-based `ETag`
  - Preserve `Cache-Control: public, immutable`

### Discovery and Resolution

- `POST /discovery` still uses normalized metadata only.
- `GET /resolution/{slug}/{version}` still returns structured authored dependency declarations only.
- The server must not inspect zip bundle contents during discovery, ranking, or resolution beyond publish-time validation.

### Storage

- Replace markdown-content-centric persistence with one digest-addressed bundle/blob store in PostgreSQL.
- Version rows bind immutably to one bundle blob row.
- Identical bundles deduplicate by digest.
- Do not explode bundle files into separate runtime content rows unless a later milestone proves that file-level reads are required.

## Validation Rules

- The uploaded artifact must be a valid zip archive.
- The archive must unpack safely:
  - no absolute paths
  - no path traversal
  - no duplicate normalized entries
- The archive must contain exactly one root skill directory.
- The root skill directory name must be kebab-case.
- `SKILL.md` is required at the root of the skill directory.
- `README.md` is forbidden inside the skill directory root.
- Allowed top-level children are:
  - `SKILL.md`
  - `scripts/`
  - `references/`
  - `assets/`
- Enforce bounded archive size, file count, and path length.

## Migration and Documentation

- Add `docs/reference/publish-bundle-migration.md`.
- The migration document must explain:
  - old publish contract: JSON with `content.raw_markdown`
  - new publish contract: structured metadata plus uploaded zip bundle
  - old content fetch: `text/markdown`
  - new content fetch: `application/zip`
  - exact metadata, discovery, and resolution remain structured and queryable
- Compatibility stance must be explicit:
  - default recommendation: hard cut for new publishes
  - existing historical versions may remain readable under legacy semantics only if the implementation intentionally preserves that behavior
- Update contract docs, examples, and fetch-route docs so the rewritten milestone does not leave contradictory language behind.

## File Structure and Responsibilities

- Modify: `.agents/plans/12-optional-evaluation-signals-and-snapshotting.md`
  - Rewrite as the implementation-grade milestone plan
- Create: `docs/reference/publish-bundle-migration.md`
  - Breaking-change migration guide for publishers and consumers
- Modify: `docs/reference/publish-request-schema.md`
  - Replace markdown-body schema with bundle-upload contract
- Modify: `docs/reference/storage-strategy.md`
  - Add bundle-blob storage direction and rationale
- Modify: `docs/reference/api-contract.md`
  - Update publish and fetch contract language
- Modify: `app/interface/api/skills.py`
  - Publish endpoint transport and validation wiring
- Modify: `app/interface/api/fetch.py`
  - Full fetch-surface contract updates and zip content response behavior
- Modify: `app/interface/dto/skills_publish.py`
  - Replace markdown content DTO with bundle metadata/request DTOs
- Modify: `app/interface/dto/skills_fetch.py`
  - Add bundle-specific metadata fields and remove markdown-specific assumptions
- Modify: `app/interface/dto/skills_shared.py`
  - Replace markdown-oriented content-summary response semantics with bundle-oriented content-summary response semantics
- Create: `app/interface/validation/skill_bundle.py`
  - Zip safety and directory-structure validation
- Modify: `app/core/skills/models.py`
  - Replace raw-markdown content inputs/outputs with bundle artifact models
- Modify: `app/core/skills/registry.py`
  - Publish orchestration for metadata plus bundle
- Modify: `app/core/skills/fetch.py`
  - Exact bundle fetch behavior and metadata projection
- Modify: `app/persistence/models/skill_content.py` or replace with bundle-focused model
  - Move from markdown content row semantics to bundle/blob semantics
- Modify: `app/persistence/skill_registry_repository_writes.py`
  - Bundle persistence and digest deduplication
- Modify: `app/persistence/skill_registry_repository_reads.py`
  - Exact metadata/content fetch backed by bundle blob metadata/payload
- Create or modify: `alembic/versions/<new_bundle_storage_migration>.py`
  - Schema change from markdown-content assumptions to bundle storage
- Modify: `tests/integration/test_skill_registry_endpoints.py`
  - End-to-end publish and fetch behavior for bundle artifacts
- Create: `tests/unit/test_skill_bundle_validation.py`
  - Archive safety and structure validation coverage
- Create or modify: `tests/integration/test_publish_bundle_migration_contract.py`
  - Breaking-contract and migration-path coverage

## Task Plan

### Task 1: Lock the milestone narrative and contract direction

**Files:**
- Modify: `.agents/plans/12-optional-evaluation-signals-and-snapshotting.md`
- Modify: `.agents/plans/roadmap.md`
- Test: `tests/unit/test_public_contract_docs.py`

- [ ] **Step 1: Write the failing doc expectation test**

```python
def test_plan_12_describes_full_skill_directory_bundle_support():
    text = Path(".agents/plans/12-optional-evaluation-signals-and-snapshotting.md").read_text()
    assert "zip bundle" in text
    assert "application/zip" in text
    assert "raw_markdown" not in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_public_contract_docs.py -v`

Expected: FAIL because Plan 12 still describes evaluation signals/snapshotting or omits the fetch-surface break

- [ ] **Step 3: Rewrite the milestone docs**

```md
Goal: support full skill-directory publish/fetch via validated zip bundle
Architecture: normalized metadata + opaque immutable zip artifact
Fetch surface: list route unchanged, metadata route bundle-oriented, content route application/zip
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_public_contract_docs.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .agents/plans/12-optional-evaluation-signals-and-snapshotting.md .agents/plans/roadmap.md tests/unit/test_public_contract_docs.py
git commit -m "docs: redefine plan 12 around skill directory bundles"
```

### Task 2: Add the migration document for the breaking publish and fetch contract

**Files:**
- Create: `docs/reference/publish-bundle-migration.md`
- Modify: `docs/reference/api-contract.md`
- Modify: `docs/reference/publish-request-schema.md`
- Test: `tests/unit/test_public_contract_docs.py`

- [ ] **Step 1: Write the failing migration-doc test**

```python
def test_publish_bundle_migration_doc_exists_and_mentions_breaking_change():
    path = Path("docs/reference/publish-bundle-migration.md")
    assert path.exists()
    text = path.read_text()
    assert "breaking change" in text.lower()
    assert "application/zip" in text
    assert "content.raw_markdown" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_public_contract_docs.py -v`

Expected: FAIL because the migration doc does not exist yet

- [ ] **Step 3: Write the migration doc**

```md
- old publish request vs new multipart bundle upload
- old exact metadata/content assumptions vs new bundle-oriented fetch semantics
- old markdown fetch vs new zip fetch
- compatibility stance
- publisher migration steps
- consumer migration steps
- historical data expectations
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_public_contract_docs.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/reference/publish-bundle-migration.md docs/reference/api-contract.md docs/reference/publish-request-schema.md tests/unit/test_public_contract_docs.py
git commit -m "docs: add bundle contract migration guide"
```

### Task 3: Introduce zip-bundle validation at the interface boundary

**Files:**
- Create: `app/interface/validation/skill_bundle.py`
- Modify: `app/interface/api/skills.py`
- Modify: `app/interface/dto/skills_publish.py`
- Test: `tests/unit/test_skill_bundle_validation.py`

- [ ] **Step 1: Write failing unit tests for bundle validation**

```python
def test_valid_bundle_requires_root_skill_dir_and_skill_md():
    bundle = build_zip({
        "python-lint/SKILL.md": "---\nname: Python Lint\n---\n",
    })
    validate_skill_bundle(bundle)


def test_bundle_rejects_root_readme():
    bundle = build_zip({
        "python-lint/SKILL.md": "---\nname: Python Lint\n---\n",
        "python-lint/README.md": "# nope\n",
    })
    with pytest.raises(BundleValidationError):
        validate_skill_bundle(bundle)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_skill_bundle_validation.py -v`

Expected: FAIL because the validation module does not exist yet

- [ ] **Step 3: Write minimal validation implementation**

```python
def validate_skill_bundle(data: bytes) -> ValidatedSkillBundle:
    # open zip safely
    # normalize member paths
    # reject traversal / absolute paths
    # verify one kebab-case root dir
    # require root SKILL.md
    # reject root README.md
    # allow only SKILL.md, scripts/, references/, assets/
    return ValidatedSkillBundle(...)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_skill_bundle_validation.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/interface/validation/skill_bundle.py app/interface/api/skills.py app/interface/dto/skills_publish.py tests/unit/test_skill_bundle_validation.py
git commit -m "feat: validate uploaded skill directory bundles"
```

### Task 4: Replace raw-markdown publish with bundle upload

**Files:**
- Modify: `app/interface/api/skills.py`
- Modify: `app/interface/dto/skills_publish.py`
- Modify: `app/interface/api/skill_api_support_publish.py`
- Modify: `app/core/skills/models.py`
- Modify: `app/core/skills/registry.py`
- Test: `tests/integration/test_skill_registry_endpoints.py`

- [ ] **Step 1: Write the failing publish integration test**

```python
def test_publish_accepts_metadata_plus_zip_bundle(client):
    response = client.post(
        "/skills/python.lint",
        files={
            "request": ("request.json", json.dumps({...}), "application/json"),
            "bundle": ("python-lint.zip", make_valid_bundle(), "application/zip"),
        },
        headers=_headers("publisher-token"),
    )
    assert response.status_code == 201
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_skill_registry_endpoints.py::test_publish_accepts_metadata_plus_zip_bundle -v`

Expected: FAIL because publish still expects JSON markdown content

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(frozen=True, slots=True)
class SkillBundleInput:
    filename: str
    media_type: str
    payload: bytes
    sha256_digest: str
    size_bytes: int
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_skill_registry_endpoints.py::test_publish_accepts_metadata_plus_zip_bundle -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/interface/api/skills.py app/interface/dto/skills_publish.py app/interface/api/skill_api_support_publish.py app/core/skills/models.py app/core/skills/registry.py tests/integration/test_skill_registry_endpoints.py
git commit -m "feat: accept skill bundle uploads on publish"
```

### Task 5: Move persistence from markdown content rows to bundle blobs

**Files:**
- Modify: `app/persistence/models/skill_content.py` or replace with bundle model
- Modify: `app/persistence/skill_registry_repository_writes.py`
- Modify: `app/persistence/skill_registry_repository_reads.py`
- Create or modify: `alembic/versions/<new_bundle_storage_migration>.py`
- Test: `tests/integration/test_migrations.py`
- Test: `tests/integration/test_skill_registry_endpoints.py`

- [ ] **Step 1: Write failing persistence tests**

```python
def test_publish_reuses_digest_backed_bundle_rows_for_identical_zip_payloads():
    first = publish_bundle(...)
    second = publish_bundle(...)
    assert first["content"]["checksum"]["digest"] == second["content"]["checksum"]["digest"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_skill_registry_endpoints.py::test_publish_reuses_digest_backed_bundle_rows_for_identical_zip_payloads -v`

Expected: FAIL because content storage is still markdown-oriented

- [ ] **Step 3: Write minimal implementation**

```python
class SkillBundleBlob(Base):
    __tablename__ = "skill_bundle_blobs"
    checksum_digest = mapped_column(...)
    media_type = mapped_column(default="application/zip")
    payload = mapped_column(LargeBinary)
    size_bytes = mapped_column(...)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_migrations.py tests/integration/test_skill_registry_endpoints.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/persistence/models app/persistence/skill_registry_repository_writes.py app/persistence/skill_registry_repository_reads.py alembic/versions tests/integration/test_migrations.py tests/integration/test_skill_registry_endpoints.py
git commit -m "feat: store immutable skill bundles as digest-addressed blobs"
```

### Task 6: Update the full fetch surface to bundle semantics

**Files:**
- Modify: `app/interface/api/fetch.py`
- Modify: `app/core/skills/fetch.py`
- Modify: `app/interface/dto/skills_fetch.py`
- Modify: `app/interface/dto/skills_shared.py`
- Modify: `app/interface/api/skill_api_support_fetch.py`
- Test: `tests/integration/test_skill_registry_endpoints.py`

- [ ] **Step 1: Write the failing fetch tests**

```python
def test_exact_metadata_fetch_returns_bundle_oriented_content_summary(client):
    publish_bundle(...)
    response = client.get("/skills/python.lint/1.0.0", headers=_headers("reader-token"))
    assert response.status_code == 200
    assert response.json()["content"]["media_type"] == "application/zip"


def test_exact_content_fetch_returns_zip_bundle(client):
    publish_bundle(...)
    response = client.get(
        "/skills/python.lint/1.0.0/content",
        headers=_headers("reader-token"),
    )
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/zip"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_skill_registry_endpoints.py -k "bundle_oriented_content_summary or zip_bundle" -v`

Expected: FAIL because fetch routes still expose markdown semantics

- [ ] **Step 3: Write minimal implementation**

```python
class SkillContentSummaryResponse(BaseModel):
    checksum: ChecksumResponse
    media_type: str
    size_bytes: int


return Response(
    content=bundle.payload,
    media_type="application/zip",
    headers={
        "ETag": bundle.checksum.digest,
        "Cache-Control": "public, immutable",
        "Content-Length": str(bundle.size_bytes),
    },
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_skill_registry_endpoints.py -k "bundle_oriented_content_summary or zip_bundle" -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/interface/api/fetch.py app/core/skills/fetch.py app/interface/dto/skills_fetch.py app/interface/dto/skills_shared.py app/interface/api/skill_api_support_fetch.py tests/integration/test_skill_registry_endpoints.py
git commit -m "feat: update fetch endpoints for bundle artifacts"
```

### Task 7: Preserve discovery and resolution behavior on normalized metadata only

**Files:**
- Modify: `app/persistence/skill_registry_repository_search.py`
- Modify: `app/core/skills/search.py`
- Modify: tests if ranking depends on removed markdown-size assumptions
- Test: `tests/integration/test_skill_registry_endpoints.py`

- [ ] **Step 1: Write a regression test that discovery ignores bundle internals**

```python
def test_discovery_uses_metadata_not_bundle_contents(client):
    publish_bundle_with_reference_docs(...)
    result = client.post("/discovery", json={"name": "Python Lint"})
    assert result.status_code == 200
```

- [ ] **Step 2: Run test to verify current behavior or expose regressions**

Run: `uv run pytest tests/integration/test_skill_registry_endpoints.py::test_discovery_uses_metadata_not_bundle_contents -v`

Expected: PASS after implementation; may fail during transition if old content assumptions leak

- [ ] **Step 3: Remove markdown-content coupling where needed**

```python
# eliminate raw_markdown-derived assumptions from discovery/ranking
# keep ranking inputs on normalized metadata/search rows only
```

- [ ] **Step 4: Run the targeted tests**

Run: `uv run pytest tests/integration/test_skill_registry_endpoints.py -k "discovery or resolution" -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/persistence/skill_registry_repository_search.py app/core/skills/search.py tests/integration/test_skill_registry_endpoints.py
git commit -m "refactor: keep discovery and resolution independent of bundle contents"
```

### Task 8: Final verification and documentation pass

**Files:**
- Modify: any remaining docs/tests needed for contract consistency
- Test: `tests/unit/test_public_contract_docs.py`
- Test: `tests/integration/test_skill_registry_endpoints.py`
- Test: `tests/integration/test_migrations.py`

- [ ] **Step 1: Run documentation and contract regression tests**

Run: `uv run pytest tests/unit/test_public_contract_docs.py tests/integration/test_migrations.py tests/integration/test_skill_registry_endpoints.py -v`

Expected: PASS

- [ ] **Step 2: Run lint**

Run: `uv run ruff check app tests docs`

Expected: PASS

- [ ] **Step 3: Review the migration doc against the live code paths**

```md
Confirm that examples, route semantics, content types, and compatibility notes match the implemented API exactly.
```

- [ ] **Step 4: Commit the final consistency pass**

```bash
git add docs app tests
git commit -m "docs: finalize bundle contract and migration coverage"
```

## Test Plan

- Unit tests for zip safety:
  - reject path traversal
  - reject absolute paths
  - reject duplicate normalized members
  - require one kebab-case root directory
  - require root `SKILL.md`
  - reject root `README.md`
  - reject unexpected top-level folders
- Publish integration tests:
  - valid metadata plus valid zip publishes successfully
  - invalid metadata fails with stable error format
  - invalid zip structure fails with stable error format
  - duplicate version publish still fails deterministically
- Persistence tests:
  - identical bundles deduplicate by digest
  - distinct bundles create distinct blob rows
  - version rows bind immutably to one bundle digest
- Fetch tests:
  - exact metadata fetch returns bundle-oriented content summary
  - exact content fetch returns `application/zip`
  - `ETag` equals bundle digest
  - identity list fetch remains route-compatible and free of markdown-specific semantics
- Discovery/resolution regression tests:
  - discovery remains metadata-driven
  - resolution remains relationship-driven
  - bundle internals do not change ranking or dependency reads
- Documentation tests:
  - contract docs mention bundle upload and zip fetch
  - migration doc exists and matches live behavior

## Assumptions and Defaults

- User-directed decision: rewrite Plan 12 in place even though it supersedes an already-shipped milestone; the implementation must add migration/supersession documentation to reduce historical ambiguity.
- The registry may break the current publish/content-fetch contract intentionally.
- The publisher is responsible for heavy pre-validation and creating the zip artifact.
- The server still performs authoritative artifact validation at publish time for safety and contract integrity.
- Metadata, description, relationships, governance, discovery, ranking, and resolution remain structured and normalized outside the zip bundle.
- The zip bundle is the only exact content artifact stored for new publishes.
- Preferred storage remains PostgreSQL-only unless testing proves bundle sizes exceed the current operational envelope.
- Route paths remain the current repo baseline:
  - `POST /skills/{slug}`
  - `GET /skills/{slug}`
  - `GET /skills/{slug}/{version}`
  - `GET /skills/{slug}/{version}/content`
  - `GET /resolution/{slug}/{version}`
- File-by-file fetch APIs, bundle browsing, and server-side execution of bundle scripts are out of scope for this milestone.
