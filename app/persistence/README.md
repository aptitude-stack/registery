# app.persistence module

Persistence adapters and storage infrastructure.

Use [docs/reference/schema.md](../../docs/reference/schema.md) and
[docs/reference/storage-strategy.md](../../docs/reference/storage-strategy.md) as the canonical
persistence references.

## Purpose

Implements core persistence ports for:

- PostgreSQL metadata persistence (SQLAlchemy)
- digest-addressed immutable bundle storage in PostgreSQL
- authored relationship selector preservation for exact dependency reads
- identity-level version listing plus exact immutable metadata/content lookup
  for one `slug@version`
- advisory search read model and indexed candidate retrieval
- database lifecycle/readiness

## Key Files

- `db.py`: engine/session lifecycle and readiness probe adapter.
- `skill_registry_repository.py`: composed SQLAlchemy adapter that exposes the
  existing repository class name while delegating behavior to port-aligned
  mixins.
- `skill_registry_repository_base.py`: shared session and helper logic for the
  repository mixins.
- `skill_registry_repository_writes.py`: publish/write-side repository methods.
- `skill_registry_repository_reads.py`: version-list, exact version/content, and
  relationship read methods.
- `skill_registry_repository_search.py`: advisory search candidate retrieval.
- `skill_registry_repository_status.py`: lifecycle-status update methods.
- `skill_registry_repository_support.py`: shared projections, query helpers, and
  search SQL.
- `models/`: ORM models.

## Contracts

Adapters in this package implement protocols defined in `app.core.ports`.
The repository owns atomic publish/status writes, including audit rows that must
commit in the same transaction as authoritative lifecycle changes.
Persistence adapters that need skill-domain errors or service-facing models
should import them from `app.core.skills.*`, while preserving the same
layering boundary against the rest of core.
Canonical short summary text lives on `skill_metadata.description`; deduplicated
`skill_contents` rows persist the exact opaque artifact bytes plus checksum, media type,
and size metadata.
Current-default recomputation reuses the shared core ordering helper so slug
listing and lifecycle updates cannot drift on tie-break behavior.
