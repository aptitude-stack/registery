# Decision Rules

> Status: normative implementation rules and invariants for `Aptitude Registry`.

## Product Invariants

- Skill versions are immutable.
- Discovery is candidate generation only and returns ordered slugs.
- Resolution returns direct authored `depends_on` selectors only.
- Exact fetch is coordinate-based and immutable.
- The registry remains execution-agnostic.

## Boundary Rules

- Registry owns data-local work.
- Resolver owns decision-local work.
- The registry must not own prompt interpretation, reranking, final selection, dependency solving, lock generation, or execution planning.
- The public route families stay limited to publish, discovery, resolution, exact fetch, lifecycle updates, and operability endpoints.

## Layering Rules

- `interface -> core`
- `core -> intelligence` only when using pure ranking/search support logic
- `core` depends on persistence through core-defined ports
- `persistence` implements core ports and may import core abstractions
- `app/main.py` is the composition-root exception

Forbidden imports:

- `app/interface/**` must not import `app/persistence/**`
- `app/core/**` must not import `app/persistence/**`

## Persistence Rules

- PostgreSQL is the only authoritative runtime store.
- Discovery stays body-free.
- Exact content fetch reads the immutable stored `application/zstd` bundle from digest-backed content rows.
- Derived search documents are rebuildable read models, not the source of truth.

## Documentation Sync Rules

- `docs/architecture/*` is the canonical source of architectural truth.
- `docs/reference/*` is the canonical source of stable API/schema/reference truth.
- `.agents/*` is derivative and must not become a second architecture source.
- If behavior changes, update the canonical doc in the same change.
- Historical milestone docs may preserve prior wording, but they do not override current canonical docs.
