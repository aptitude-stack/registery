# Stable Repo Facts

- Canonical docs entrypoint: [`../../docs/README.md`](../../docs/README.md)
- Canonical HTTP contract: [`../../docs/reference/api-contract.md`](../../docs/reference/api-contract.md)
- Canonical boundary doc: [`../../docs/architecture/server-resolver-boundary.md`](../../docs/architecture/server-resolver-boundary.md)
- Canonical implementation sequence: [`../plans/roadmap.md`](../plans/roadmap.md)

## Current Snapshot

- `Aptitude Registry` is the registry backend in the Aptitude ecosystem.
- PostgreSQL is the only authoritative runtime store.
- Discovery is body-free candidate generation.
- Resolution returns direct authored `depends_on` selectors only.
- Exact content fetch reads immutable markdown by exact coordinate.
