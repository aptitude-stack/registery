# app.core module

Core domain logic and cross-layer contracts.

Use [docs/architecture/server-resolver-boundary.md](../../docs/architecture/server-resolver-boundary.md) for the canonical
server-vs-resolver boundary.

## Purpose

Defines business behavior for immutable skill catalog operations and the ports
that infrastructure layers implement.

## Structure

- `skills/`: skill-domain bounded context containing publish, discovery, exact
  fetch, resolution, advisory search, shared projections, and skill-domain
  models/errors.
- `audit_events.py`: typed audit-event builders shared by publish, discovery,
  list/fetch, resolution, and lifecycle flows.
- `ports.py`: protocol contracts for publish, identity-level version lists,
  exact version reads, relationship reads, discovery, artifacts, audit, and
  readiness.
- `dependencies.py`: FastAPI dependency providers and typed aliases
  (`SettingsDep`, `ReadinessServiceDep`, `SkillRegistryServiceDep`, `SkillDiscoveryServiceDep`, `SkillResolutionServiceDep`, `SkillFetchServiceDep`) that read process-scoped services from the typed runtime service container at `app.state.services`.
- `settings.py`: typed environment configuration.

## Boundaries

- Core must not import persistence implementations directly.
- Persistence and audit adapters implement core-defined protocols.
- Core publishes immutable manifest metadata but does not solve dependency
  graphs, generate locks, or build execution plans.
- Core discovery remains candidate retrieval only; ranking is advisory and not authoritative for resolver choice.
- Core resolution returns only direct authored dependency selectors; no transitive traversal or solving belongs here.
- Core fetch composes PostgreSQL-backed identity version lists plus metadata and
  markdown reads for immutable coordinates.
- Core publish normalizes publisher-supplied advisory provenance, derives server-owned trust context, and leaves resolver concerns out of the write path.
- The `skills/` package is an internal grouping inside core, not a separate
  architecture layer; top-level layering remains `interface -> core -> persistence`.
- Runtime logging, metrics, request context, and readiness helpers live in
  `app.observability`, not in the business-domain core.
- Core registry status updates derive `is_current_default` from canonical version ordering instead of a stored pointer on `skills`.
- Successful publish and lifecycle mutation audits are committed transactionally with the authoritative version write, while read and denied-action audits use the standalone audit adapter.
- Dependency providers in `dependencies.py` assume startup has initialized
  the typed process-scoped service container stored under `app.state.services`.
- Core treats `metadata.description` as the only canonical short summary field;
  content models expose checksum and size metadata only.
