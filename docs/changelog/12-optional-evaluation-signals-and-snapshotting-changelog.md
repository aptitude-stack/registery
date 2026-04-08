# Milestone 12 Changelog - Optional Evaluation Signals and Snapshotting

This changelog documents implementation of [.agents/plans/12-optional-evaluation-signals-and-snapshotting.md](../../.agents/plans/12-optional-evaluation-signals-and-snapshotting.md).

This milestone stays intentionally narrow. It adds one mutable, derived evaluation signal for advisory retrieval and exact-read metadata, keeps default-version selection derived and deterministic, and does not introduce any snapshot route family or snapshot storage model. Exact immutable coordinates remain the reproducibility baseline, while the new signal stays outside authored metadata and dependency declarations.

## Scope Delivered

- Exact metadata now carries a mutable aggregate `install_count` per skill slug, backed by the new `skills.install_count` column and surfaced through the existing exact metadata route rather than a new endpoint family: [alembic/versions/0002_skill_install_counts.py](../../alembic/versions/0002_skill_install_counts.py), [app/persistence/models/skill.py](../../app/persistence/models/skill.py), [app/core/skills/fetch.py](../../app/core/skills/fetch.py), [app/interface/api/fetch.py](../../app/interface/api/fetch.py), [app/interface/api/skill_api_support_fetch.py](../../app/interface/api/skill_api_support_fetch.py), [app/interface/dto/skills_fetch.py](../../app/interface/dto/skills_fetch.py), [docs/reference/api-contract.md](../reference/api-contract.md).
- Successful exact content fetches now update the derived evaluation signal in one place and mirror it into discovery ranking state by incrementing `skills.install_count` and `skill_search_documents.usage_count`, without mutating immutable version rows, content rows, or authored selectors: [app/core/skills/fetch.py](../../app/core/skills/fetch.py), [app/persistence/skill_registry_repository_reads.py](../../app/persistence/skill_registry_repository_reads.py), [app/persistence/skill_registry_repository_support.py](../../app/persistence/skill_registry_repository_support.py), [tests/integration/test_skill_registry_endpoints.py](../../tests/integration/test_skill_registry_endpoints.py), [docs/reference/api-contract.md](../reference/api-contract.md), [docs/reference/schema.md](../reference/schema.md).
- Identity list responses and lifecycle updates now share one canonical ordering rule for `is_current_default` instead of relying on duplicated logic or a stored pointer. The rule remains derived from visible versions only and still does not introduce snapshot state or separate “latest view” APIs: [app/core/skills/version_ordering.py](../../app/core/skills/version_ordering.py), [app/core/skills/fetch.py](../../app/core/skills/fetch.py), [app/persistence/skill_registry_repository_base.py](../../app/persistence/skill_registry_repository_base.py), [app/persistence/skill_registry_repository_status.py](../../app/persistence/skill_registry_repository_status.py), [docs/reference/api-contract.md](../reference/api-contract.md), [tests/unit/test_skill_fetch_service.py](../../tests/unit/test_skill_fetch_service.py), [tests/integration/test_skill_registry_endpoints.py](../../tests/integration/test_skill_registry_endpoints.py).
- Snapshotting stayed deferred. The public route surface is still the same publish, discovery, resolution, exact metadata/content, lifecycle, and operability set from prior milestones, with no snapshot routes or pinned latest-state route tree added in this branch: [.agents/plans/12-optional-evaluation-signals-and-snapshotting.md](../../.agents/plans/12-optional-evaluation-signals-and-snapshotting.md), [docs/reference/api-contract.md](../reference/api-contract.md), [app/interface/api/discovery.py](../../app/interface/api/discovery.py), [app/interface/api/fetch.py](../../app/interface/api/fetch.py), [app/interface/api/resolution.py](../../app/interface/api/resolution.py).

## Architecture Snapshot

```mermaid
flowchart LR
    Client["Client"] --> Content["GET /skills/{slug}/{version}/content"]
    Content --> Fetch["SkillFetchService"]
    Fetch --> Repo["SQLAlchemySkillRegistryRepository"]
    Repo --> Skill["skills.install_count"]
    Repo --> Search["skill_search_documents.usage_count"]

    Client --> List["GET /skills/{slug}"]
    List --> Fetch
    Fetch --> Ordering["version_ordering.select_current_default_version()"]
```

Why this shape:
- The evaluation signal stays derived and mutable on identity/search state instead of contaminating immutable version rows or authored metadata payloads, which matches the optional and advisory framing in Plan 12: [.agents/plans/12-optional-evaluation-signals-and-snapshotting.md](../../.agents/plans/12-optional-evaluation-signals-and-snapshotting.md), [app/persistence/models/skill.py](../../app/persistence/models/skill.py), [app/persistence/skill_registry_repository_reads.py](../../app/persistence/skill_registry_repository_reads.py).
- Default-version selection remains a pure derived rule shared by fetch and lifecycle paths, which avoids introducing a stored “latest snapshot” pointer or reopening route surface complexity: [app/core/skills/version_ordering.py](../../app/core/skills/version_ordering.py), [app/core/skills/fetch.py](../../app/core/skills/fetch.py), [app/persistence/skill_registry_repository_base.py](../../app/persistence/skill_registry_repository_base.py), [app/persistence/skill_registry_repository_status.py](../../app/persistence/skill_registry_repository_status.py).

## Runtime Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant A as GET /skills/{slug}/{version}/content
    participant S as SkillFetchService
    participant R as Repository
    participant D as skills + search docs

    C->>A: Exact content fetch
    A->>S: get_content(slug, version)
    S->>R: get_version_content()
    R-->>S: Stored content row
    S->>R: record_install(slug, version)
    R->>D: increment install_count + usage_count
    S-->>A: SkillContentDocument
    A-->>C: text/markdown response
```

## Design Notes

- `install_count` is intentionally not part of authored immutable metadata. It is exposed alongside immutable metadata, but it lives on the logical skill identity and is updated after successful exact content reads, which keeps authored content, version digests, and dependency declarations unchanged: [app/core/skills/models.py](../../app/core/skills/models.py), [app/interface/dto/skills_fetch.py](../../app/interface/dto/skills_fetch.py), [app/core/skills/fetch.py](../../app/core/skills/fetch.py), [app/persistence/models/skill.py](../../app/persistence/models/skill.py).
- Discovery ranking reuses the same aggregate signal via `skill_search_documents.usage_count` rather than inventing a separate evaluation-results store. That keeps the milestone within the “optional derived metadata” scope instead of becoming a broader evaluation pipeline: [app/persistence/skill_registry_repository_reads.py](../../app/persistence/skill_registry_repository_reads.py), [app/persistence/models/skill_search_document.py](../../app/persistence/models/skill_search_document.py), [app/persistence/skill_registry_repository_support.py](../../app/persistence/skill_registry_repository_support.py).
- The branch deliberately does not add snapshot APIs, snapshot tables, or snapshot-aware fetch behavior. Exact immutable coordinates and client-generated locks remain the reproducibility mechanism, which is the conservative choice Plan 12 called for unless stronger trigger criteria emerge: [.agents/plans/12-optional-evaluation-signals-and-snapshotting.md](../../.agents/plans/12-optional-evaluation-signals-and-snapshotting.md), [docs/reference/api-contract.md](../reference/api-contract.md), [docs/reference/schema.md](../reference/schema.md).
- Canonical version ordering is centralized because default selection is governance-aware behavior, not storage state. Reusing one helper across fetch and lifecycle updates prevents divergent “current default” answers under the same visible version set: [app/core/skills/version_ordering.py](../../app/core/skills/version_ordering.py), [app/core/skills/fetch.py](../../app/core/skills/fetch.py), [app/persistence/skill_registry_repository_status.py](../../app/persistence/skill_registry_repository_status.py), [tests/unit/test_skill_fetch_service.py](../../tests/unit/test_skill_fetch_service.py).

## Schema Reference

Source: [alembic/versions/0002_skill_install_counts.py](../../alembic/versions/0002_skill_install_counts.py), [docs/reference/schema.md](../reference/schema.md), [app/persistence/models/skill.py](../../app/persistence/models/skill.py), [app/persistence/models/skill_search_document.py](../../app/persistence/models/skill_search_document.py).

### `skills`

| Field | Type | Nullable | Default / Constraint | Role |
| --- | --- | --- | --- | --- |
| `id` | `bigint` | No | PK | Internal identity key for one public skill slug; it remains the stable mutable aggregation point rather than a version row. |
| `slug` | `text` | No | unique | Stable public identifier used by publish, list, exact fetch, and discovery candidate output. |
| `install_count` | `bigint` | No | default `0` | Mutable aggregate evaluation signal counting successful exact content fetches across all versions of the skill. |
| `created_at` | `timestamptz` | No | server default | Creation timestamp for the logical skill identity. |
| `updated_at` | `timestamptz` | No | server default / on update | Tracks last identity-level mutable change, including aggregate counter updates. |

### `skill_search_documents`

| Field | Type | Nullable | Default / Constraint | Role |
| --- | --- | --- | --- | --- |
| `skill_version_fk` | `bigint` | No | PK, FK | Ties one advisory search document back to one immutable version row without making the search document authoritative. |
| `slug` | `text` | No | indexed | Preserves the public skill identifier for exact-match and candidate-return behavior. |
| `published_at` | `timestamptz` | No | indexed | Supports deterministic ranking and the derived default-version ordering rule. |
| `content_size_bytes` | `bigint` | No | indexed | Provides advisory size information for ranking and filtering without joining raw markdown content. |
| `usage_count` | `bigint` | No | default `0` | Mirrors the skill-level aggregate install signal into the derived discovery document so ranking can use the same mutable evaluation state. |
| `lifecycle_status` | `text` | No | indexed | Keeps discovery visibility aligned with governance without consulting immutable content rows. |
| `trust_tier` | `text` | No | indexed | Preserves trust-aware filtering at the advisory search layer. |

## Verification Notes

- Migration coverage verifies the clean Alembic baseline upgrades to head with `skills.install_count` present and the canonical normalized tables still intact: [tests/integration/test_migrations.py](../../tests/integration/test_migrations.py), [alembic/versions/0002_skill_install_counts.py](../../alembic/versions/0002_skill_install_counts.py).
- Integration coverage proves exact content fetch increments the aggregate identity counter and mirrors the same value into discovery ranking state, while exact metadata exposes the updated value without mutating immutable version content: [tests/integration/test_skill_registry_endpoints.py](../../tests/integration/test_skill_registry_endpoints.py), [app/core/skills/fetch.py](../../app/core/skills/fetch.py), [app/persistence/skill_registry_repository_reads.py](../../app/persistence/skill_registry_repository_reads.py).
- Unit and integration coverage verify deterministic `is_current_default` selection across visible versions and lifecycle transitions, including tie-break behavior on equal publish timestamps: [tests/unit/test_skill_fetch_service.py](../../tests/unit/test_skill_fetch_service.py), [tests/integration/test_skill_registry_endpoints.py](../../tests/integration/test_skill_registry_endpoints.py), [app/core/skills/version_ordering.py](../../app/core/skills/version_ordering.py).
- Snapshotting remains intentionally unverified because it was not implemented. The branch adds no snapshot routes, no snapshot tables, and no snapshot-specific tests, which matches the deferred status in Plan 12: [.agents/plans/12-optional-evaluation-signals-and-snapshotting.md](../../.agents/plans/12-optional-evaluation-signals-and-snapshotting.md), [docs/reference/api-contract.md](../reference/api-contract.md).
