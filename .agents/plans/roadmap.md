# Aptitude Registry Roadmap

## Goal
Deliver a production-ready immutable registry service (`Aptitude Registry`) in Python/FastAPI through incremental, testable milestones.

## Alignment Sources
- Scope boundary and ownership: [`../../docs/architecture/server-resolver-boundary.md`](../../docs/architecture/server-resolver-boundary.md)
- Server requirements and KPIs: [`../../docs/roadmap/requirements-and-phases.md`](../../docs/roadmap/requirements-and-phases.md)
- Resolver ownership and dependency-solving responsibilities are out of scope for this repository and tracked in the resolver repository.

## Platform Defaults
- Database: PostgreSQL (primary from the first milestone).
- Migrations: versioned SQL migrations (up/down), no manual schema changes.
- Search: PostgreSQL-native indexing and full-text capabilities.

## Boundary Guardrails
- This roadmap covers `Aptitude Registry` only.
- Server owns data-local registry work: publish, discovery candidate generation, exact first-degree dependency reads, exact immutable metadata fetch, exact immutable content fetch, lifecycle enforcement, provenance capture, and audit.
- Resolver owns decision-local work: MCP/CLI prompt interfaces, prompt interpretation, reranking, final candidate selection, recursive dependency solving, lock generation, plugin orchestration, and execution planning.
- Server remains execution-agnostic and exposes governed APIs for publish, discovery, resolution, exact fetch, lifecycle, and provenance.
- Server contracts are slug candidates, authored direct dependency declarations, immutable metadata/content envelopes, and governance results; the server does not return canonical solved bundles.
- Discovery remains candidate generation only; resolution remains exact first-degree dependency retrieval only; resolver choice and lock output remain authoritative.
- Plans 09-15 keep the public route families fixed: publish, discovery, resolution, exact metadata fetch, exact content fetch, and lifecycle/governance operations.
- Later milestones extend behavior inside that route set instead of adding new public read route families, compatibility aliases, or batch-fetch detours.

## Milestones
1. `01-foundation-service-skeleton.md`
2. `02-immutable-skill-registry.md`
3. `03-deterministic-dependency-resolution.md` (legacy filename; scope is dependency metadata contracts, not server-side solving)
4. `04-repository-api-contract-v1.md`
5. `05-metadata-search-ranking.md`
6. `06-policy-conflict-governance.md`
7. `07-mvp-read-api-hard-cut.md`
8. `08-canonical-postgres-storage-finalization.md`
9. `09-public-api-simplification-and-contract-freeze.md`
10. `10-governance-provenance-and-audit-completion.md`
11. `11-operability-and-release-readiness.md`
12. `12-optional-evaluation-signals-and-snapshotting.md`
13. `13-environment-profiles-and-runtime-separation.md`
14. `14-minimal-auth-boundary-and-token-governance.md`
15. `15-hybrid-semantic-and-co-usage-discovery.md`

## PRD Phase Mapping
- `MVP` (prd): milestones 01-04.
- `v1.1` (prd): milestones 05-06.
- `Read-contract simplification`: milestone 07.
- `v2.0` prep (prd): milestones 08-10.
- `Release readiness`: milestone 11.
- `Post-launch optional discovery enhancements`: milestone 12.
- `Environment profile separation`: milestone 13.
- `Security boundary hardening`: milestone 14.
- `Post-launch hybrid semantic and co-usage discovery`: milestone 15.
- Resolver-specific initiatives (prompt interpretation, deterministic solving, reranking, plugin chains, and lock replay) are tracked in resolver planning and are out of scope for this roadmap.

## Roadmap Rules
- Roadmap numbering is append-only after the one-time pre-implementation renumbering that inserted Plan 07.
- The Plan 07 insertion and 07-13 to 08-14 shift are intentional cleanup to keep the MVP path simple before implementation work is finalized.
- Plan filenames and titles may be corrected before implementation when the existing milestone framing is architecturally wrong.
- Completed plans are never renamed or renumbered.
- Plans `01` through `11` and changelogs `01` through `11` are protected history. Clarifications must be appended as dated notes; do not rewrite existing body text.
- New scope changes create a new numbered plan file.
