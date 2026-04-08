# app module

Application package for the Aptitude Registry service.

For the repo-wide docs map, use [docs/README.md](../docs/README.md). For the
canonical HTTP contract, use [docs/reference/api-contract.md](../docs/reference/api-contract.md).

## Purpose

`app/` contains the runtime composition root, domain/core services, interface layer,
audit adapter, persistence adapters/models, and placeholders for future
metadata-oriented intelligence work.

## Module Map

- `app/main.py`: FastAPI application creation, startup/shutdown wiring, and dev server runner with shared logging config + startup banner.
- `app/service_container.py`: typed runtime service graph builder used by startup wiring and request-time dependency access.
- `app/audit/`: audit port adapters.
- `app/core/`: domain services for immutable catalog reads/writes, settings, ports,
  advisory search, provenance validation, transactional mutation audit, and dependency providers.
- `app/core/skills/`: skill-catalog bounded context inside the core layer,
  including publish, discovery, exact fetch, resolution, search, and shared
  skill-domain models.
- `app/observability/`: runtime logging, metrics, request context propagation,
  and dependency readiness helpers.
- `app/interface/`: API interface boundary for publish, discovery, exact dependency reads, and exact metadata/content fetch.
- `app/persistence/`: database/artifact adapters and ORM models for immutable
manifests, advisory provenance snapshots, dependency declaration projections, search read models, and transactional mutation audit writes.
- `app/intelligence/`: search-ranking helpers and future metadata/graph intelligence.

The canonical short summary for a skill now lives on `metadata.description`;
content rows store only markdown plus checksum/size metadata.

## Update Rule

When adding or changing modules under `app/`, update the matching module README
in the same commit.
