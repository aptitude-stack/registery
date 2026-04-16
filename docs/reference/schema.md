# Database Schema

> Status: canonical PostgreSQL schema baseline for the live registry.
> Use [`api-contract.md`](api-contract.md) for the live HTTP contract.

## Purpose

This document describes the canonical PostgreSQL baseline for the registry data model.

It reflects the current runtime shape created by [`alembic/versions/0001_initial_schema.py`](../../alembic/versions/0001_initial_schema.py) and evolved by [`alembic/versions/0003_skill_bundle_storage.py`](../../alembic/versions/0003_skill_bundle_storage.py):

- PostgreSQL is the only authoritative store.
- versions are immutable.
- discovery queries stay body-free.
- exact content is stored as digest-deduplicated opaque artifacts.
- identity, versioning, content, metadata, selectors, search projection, and audit records are modeled separately.

## Canonical Baseline

The live schema is centered on immutable version rows, digest-backed bundle rows, authored selector rows, and a derived search projection.

- `skills` stores the logical identity row and mutable install aggregate.
- `skill_versions` binds immutable artifact, metadata, and governance state together.
- `skill_contents` stores the canonical `application/zstd` artifact bytes plus digest and size metadata.
- authored selectors live in `skill_relationship_selectors` and remain the only persisted dependency source of truth.
- discovery uses `skill_search_documents` as a derived, governance-aware read model.
- `audit_events` remains the append-only audit sink for registry actions.

Removed compatibility artifacts:

- `skill_dependencies`
- `skill_relationship_edges`
- `skill_version_checksums`
- legacy markdown-only content assumptions

## Design Principles

- Keep `skills` as the stable identity row.
- Keep `skill_versions` immutable after publish.
- Store exact artifacts in `skill_contents.payload` as opaque bytes.
- Reuse identical artifacts through `skill_contents.checksum_digest`.
- Keep high-cardinality filters and ranking fields in typed columns.
- Use `jsonb` only for flexible structured metadata.
- Keep discovery/list/search APIs off the bundle table by default.
- Keep search read models derived and rebuildable.

## Storage Guidance

Use PostgreSQL row storage and TOAST implicitly for artifact payloads.

- `skill_contents.payload` is a `bytea`/`LargeBinary` column.
- do not use Postgres large objects or reconstruct artifacts from normalized rows.
- the main optimization is still query-path separation so metadata-heavy reads never touch artifact bytes unless exact content is requested.

## Entity Overview

```mermaid
erDiagram
    skills ||--o{ skill_versions : has
    skill_contents ||--o{ skill_versions : backs
    skill_metadata ||--o{ skill_versions : describes
    skill_versions ||--o{ skill_relationship_selectors : preserves
    skill_versions ||--|| skill_search_documents : projects
```

`audit_events` is intentionally separate from the skill publication graph.

## Runtime Tables

### `audit_events`

Append-only audit log for registry-side events.

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `id` | `integer` | PK | Internal audit event key. |
| `event_type` | `varchar(100)` | `NOT NULL` | Audit event discriminator. |
| `payload` | `json` | nullable | Event-specific structured metadata. |
| `created_at` | `timestamptz` | `NOT NULL`, server default | Event creation timestamp. |

### `skills`

Stable identity row.

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `id` | `bigint` | PK | Internal identity key. |
| `slug` | `text` | `NOT NULL`, unique | Stable public skill identifier. |
| `install_count` | `bigint` | `NOT NULL`, default `0` | Mutable aggregate install/download count across all versions of the skill. |
| `created_at` | `timestamptz` | `NOT NULL`, server default | Row creation time. |
| `updated_at` | `timestamptz` | `NOT NULL`, server default | Last identity-state update. |

Constraints and indexes:

- unique index on `slug`
- no `current_version_id` pointer is stored on this table

### `skill_versions`

Immutable version rows binding identity, content, metadata, and governance together.

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `id` | `bigint` | PK | Internal immutable version key. |
| `skill_fk` | `bigint` | `NOT NULL`, FK -> `skills.id` | Parent skill identity. |
| `version` | `text` | `NOT NULL` | Semantic version string. |
| `content_fk` | `bigint` | `NOT NULL`, FK -> `skill_contents.id` | Immutable artifact row. |
| `metadata_fk` | `bigint` | `NOT NULL`, FK -> `skill_metadata.id` | Immutable metadata row. |
| `checksum_digest` | `varchar(64)` | `NOT NULL` | Version-level digest returned in exact metadata reads. |
| `lifecycle_status` | `text` | `NOT NULL`, default `published` | `published`, `deprecated`, or `archived`. |
| `lifecycle_changed_at` | `timestamptz` | `NOT NULL`, server default | Most recent lifecycle transition time. |
| `trust_tier` | `text` | `NOT NULL`, default `untrusted` | `untrusted`, `internal`, or `verified`. |
| `provenance_repo_url` | `text` | nullable | Minimal source repository provenance. |
| `provenance_commit_sha` | `text` | nullable | Commit associated with the published version. |
| `provenance_tree_path` | `text` | nullable | Optional repository subpath for the skill. |
| `provenance_publisher_identity` | `text` | nullable | Advisory publisher or CI identity collected at publish time. |
| `policy_profile_at_publish` | `text` | nullable | Server-derived policy profile snapshot for advisory trust context. |
| `created_at` | `timestamptz` | `NOT NULL`, server default | Insert time. |
| `published_at` | `timestamptz` | `NOT NULL`, server default | Publish timestamp. |

Checksum rule:

- `checksum_digest` is derived from the content checksum plus normalized metadata, governance, and authored relationships.
- changing artifact bytes, metadata, governance, or relationships creates a new immutable version row.

### `skill_contents`

Authoritative immutable artifact storage.

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `id` | `bigint` | PK | Internal content key. |
| `payload` | `bytea` | `NOT NULL` | Canonical stored artifact bytes returned by exact content fetch. |
| `media_type` | `text` | `NOT NULL` | Stored artifact media type, currently `application/zstd`. |
| `storage_size_bytes` | `bigint` | `NOT NULL` | Stored bundle size used by exact fetch metadata and search-document projection. |
| `checksum_digest` | `varchar(64)` | `NOT NULL`, unique | Artifact digest for deduplication, exact content identity, and `ETag` emission. |

Storage notes:

- identical artifacts are deduplicated by `checksum_digest`
- exact content fetches read this table directly
- list/search/rank queries should not join this table unless explicitly needed

### `skill_metadata`

Structured, queryable metadata for discovery and ranking.

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `id` | `bigint` | PK | Internal metadata key. |
| `name` | `text` | `NOT NULL` | Display name. |
| `description` | `text` | nullable | Canonical author-owned short description used for discovery and exact metadata reads. |
| `tags` | `text[]` | `NOT NULL`, default empty array | Primary categorical filters. |
| `inputs_schema` | `jsonb` | nullable | Structured input contract. |
| `outputs_schema` | `jsonb` | nullable | Structured output contract. |
| `token_estimate` | `integer` | nullable | Approximate token footprint. |
| `maturity_score` | `float` | nullable | Quality or stability ranking input. |
| `security_score` | `float` | nullable | Security or trust ranking input. |

### `skill_relationship_selectors`

Authored relationship selectors preserved exactly as published.

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `id` | `bigint` | PK | Internal selector key. |
| `source_skill_version_fk` | `bigint` | `NOT NULL`, FK -> `skill_versions.id` | Source immutable version. |
| `edge_type` | `text` | `NOT NULL` | `depends_on`, `extends`, `conflicts_with`, `overlaps_with`. |
| `ordinal` | `integer` | `NOT NULL` | Publish-order position within one edge family. |
| `target_slug` | `text` | `NOT NULL` | Authored dependency target slug. |
| `target_version` | `text` | nullable | Authored exact version selector. |
| `version_constraint` | `text` | nullable | Authored version range selector. |
| `optional` | `boolean` | nullable | Optional execution hint for `depends_on`. |
| `markers` | `text[]` | `NOT NULL` | Authored environment/runtime markers. |
| `created_at` | `timestamptz` | `NOT NULL`, server default | Selector insertion timestamp. |

### `skill_search_documents`

Derived read model for fast advisory search.

This table is derived from `skills`, `skill_versions`, `skill_metadata`, and `skill_contents`.

| Column | Type | Purpose |
| --- | --- | --- |
| `skill_version_fk` | `bigint` | PK and FK to `skill_versions.id`. |
| `slug` | `text` | Canonical/original identifier for direct matching. |
| `normalized_slug` | `text` | Lowercased/normalized identifier for exact matching. |
| `version` | `text` | Candidate version. |
| `name` | `text` | Display name. |
| `normalized_name` | `text` | Lowercased display name. |
| `description` | `text` | Searchable summary. |
| `tags` | `text[]` | Stored tags. |
| `normalized_tags` | `text[]` | Lowercased tags for containment filters. |
| `lifecycle_status` | `text` | Discovery visibility filter. |
| `trust_tier` | `text` | Trust filter. |
| `search_vector` | `tsvector` | Full-text index target. |
| `published_at` | `timestamptz` | Freshness ranking input. |
| `content_size_bytes` | `bigint` | Ranking/filtering input based on stored bundle size. |
| `usage_count` | `bigint` | Ranking tie-break input. |
| `created_at` | `timestamptz` | Projection insert timestamp. |

Rule:

- do not store artifact payload bytes in this table

## Query Path Separation

The schema is intentionally optimized around three read paths.

Discovery path:

- hit `skill_search_documents`
- rely on canonical `skills`, `skill_versions`, `skill_metadata`, and `skill_contents` only through the derived projection refresh path
- do not hit `skill_contents.payload`

Resolution path:

- resolve exact authored relationship selectors from `skill_relationship_selectors`
- preserve relationship payloads as authored instead of materializing solved edges

Exact fetch path:

- resolve `(slug, version)` through `skills` and `skill_versions`
- load `skill_contents.payload`
- return checksum metadata from `skill_versions.checksum_digest` and `skill_contents.checksum_digest`

## Migration Direction

The canonical bundle transition is captured by [`alembic/versions/0003_skill_bundle_storage.py`](../../alembic/versions/0003_skill_bundle_storage.py):

1. add `payload` and `media_type` to `skill_contents`
2. rewrite legacy markdown rows into artifact blobs
3. recompute content checksums from stored artifact bytes
4. recompute version checksums from the artifact-aware canonical payload
5. backfill `skill_search_documents.content_size_bytes` from stored bundle size
6. drop `skill_contents.raw_markdown`

## Non-Goals

- storing exact artifacts as markdown text
- using Postgres large objects for skill artifacts
- joining the content table for every search/list request
- making derived search tables the source of truth
- persisting compatibility tables or legacy markdown-only read semantics
