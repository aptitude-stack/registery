# Aptitude Registry Roadmap

## Goal
Deliver a production-ready immutable registry service (`Aptitude Registry`) in Python/FastAPI through incremental, testable milestones.

## Alignment Sources
- Scope boundary and ownership: [`../../docs/architecture/server-resolver-boundary.md`](../../docs/architecture/server-resolver-boundary.md)
- Server requirements and KPIs: [`../../docs/roadmap/aptitude-registry-prd.md`](../../docs/roadmap/aptitude-registry-prd.md)
- Market positioning and moat research, used for strategy only: [`../../docs/roadmap/market-research.md`](../../docs/roadmap/market-research.md)
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
- Plans 09-18 keep the resolver-facing read route families fixed: publish, discovery, resolution, exact metadata fetch, exact content fetch, and lifecycle/governance operations.
- Enterprise control-plane milestones may add admin/governance surfaces when the current lifecycle/governance routes cannot represent the workflow cleanly, but they must not turn discovery, resolution, or exact fetch into runtime orchestration APIs.

## Enterprise Control-Plane Anchor

The market research shows a split between open developer marketplaces and enterprise agentic-governance platforms. `Aptitude Registry` should compete as the governed system of record and security airlock for enterprise skills and adjacent agentic artifacts.

The moat is:
- security-airlock control over what is admitted into the catalog
- verifiable provenance, signatures, attestations, and publisher trust
- governance over what is allowed, promoted, deprecated, or archived
- private namespace and organization ownership for enterprise catalog control
- policy packs for internal, imported, verified, and restricted artifacts
- audit lineage from publish through approval, resolution reads, and production use
- deployment sovereignty across hosted, private-cloud, self-hosted, and air-gapped environments

The moat is not:
- becoming a generic public skill marketplace
- becoming a broad managed integration platform
- collapsing registry, resolver, and runtime into one product surface
- owning runtime gateway interception, agent identity issuance, or token-budget enforcement inside the registry service
- prioritizing autonomous artifact optimization before the trust, governance, and audit foundation is concrete

Planning consequences:
- Plan 16 turns the enterprise control-plane direction into concrete registry governance: private namespaces, review, promotion, policy packs, trust evidence, and audit.
- Plan 17 defines registry-owned facts consumed by gateway, identity, and token-control surfaces without moving those runtime responsibilities into this repository.
- Plan 18 improves discovery quality only after the enterprise trust foundation is explicit; discovery relevance remains subordinate to lifecycle, trust, policy, and visibility.
- Redis caching remains an optional supporting plan, not part of the main enterprise moat sequence.

Future planning backlog:

| Area | Why It Matters | Promote To Plan When |
| --- | --- | --- |
| Deployment sovereignty packaging | Enterprise buyers may require hosted, private-cloud, self-hosted, or air-gapped deployment choices. | A target deployment model needs concrete packaging, upgrade, backup, and operational acceptance criteria. |
| Compliance reporting | Security teams need evidence over publish, approval, promotion, policy, and downstream runtime use. | Audit events and trust-consumer contracts are stable enough to define reporting schemas and retention rules. |

## Conceptual Milestone Sequence

| Sequence | Plan                                                        | Role |
|----------|-------------------------------------------------------------| --- |
| 01       | `01-foundation-service-skeleton.md`                         | Service skeleton |
| 02       | `02-immutable-skill-registry.md`                            | Immutable registry baseline |
| 03       | `03-deterministic-dependency-resolution.md`                 | Legacy filename; scope is dependency metadata contracts, not server-side solving |
| 04       | `04-repository-api-contract-v1.md`                          | Initial repository API contract |
| 05       | `05-metadata-search-ranking.md`                             | Metadata search baseline |
| 06       | `06-policy-conflict-governance.md`                          | Policy and conflict governance |
| 07       | `07-mvp-read-api-hard-cut.md`                               | Read API simplification |
| 08       | `08-canonical-postgres-storage-finalization.md`             | PostgreSQL storage finalization |
| 09       | `09-public-api-simplification-and-contract-freeze.md`       | Public API simplification and freeze |
| 10       | `10-governance-provenance-and-audit-completion.md`          | Governance, provenance, and audit completion |
| 11       | `11-operability-and-release-readiness.md`                   | Operability and release readiness |
| 12       | `12-full-skill-directory-bundle-support.md`                 | Bundle artifact model reset |
| 13       | `13-environment-profiles-and-runtime-separation.md`         | Runtime profile separation |
| 14       | `14-minimal-auth-boundary-and-token-governance.md`          | Security boundary hardening |
| 15       | `15-enterprise-security-airlock-and-promotion-workflows.md` | Concrete enterprise trust, review, promotion, and policy workflows |
| 16       | `16-registry-trust-consumer-contracts.md`                   | Registry facts consumed by gateway, identity, and token-control surfaces |
| 17       | `17-hybrid-semantic-and-co-usage-discovery.md`              | Optional governed discovery-quality expansion |

## Optional Supporting Plans

These plans are valid backlog items, but they are not part of the main
enterprise moat sequence.

| Plan | Role | Revisit Trigger |
| --- | --- | --- |
| `redis-caching-over-pg-read-models.md` | Optional Redis L1 cache over PostgreSQL read models | Revisit only after measured read latency, throughput, or exact-content cost pressure justifies another operational dependency |

## PRD Phase Mapping
- `MVP` (prd): milestones 01-04.
- `v1.1` (prd): milestones 05-06.
- `Read-contract simplification`: milestone 07.
- `v2.0` prep (prd): milestones 08-10.
- `Release readiness`: milestone 11.
- `Bundle artifact model reset`: milestone 12.
- `Environment profile separation`: milestone 13.
- `Security boundary hardening`: milestone 14.
- `Enterprise control plane and supply-chain trust`: sequence 15 strategic anchor in this roadmap, not a standalone implementation plan.
- `Enterprise security airlock and promotion workflows`: milestone 16, first implementation-facing enterprise trust plan.
- `Registry trust consumer contracts`: milestone 17, placed after milestone 16.
- `Post-launch hybrid semantic and co-usage discovery`: milestone 18, placed after the enterprise trust foundations.
- `Optional Redis L1 caching over PostgreSQL read models`: unnumbered supporting plan, kept outside the main flow until measured scale pressure justifies it.
- Resolver-specific initiatives (prompt interpretation, deterministic solving, reranking, plugin chains, and lock replay) are tracked in resolver planning and are out of scope for this roadmap.

## Roadmap Rules
- Roadmap numbering is append-only after the one-time pre-implementation renumbering that inserted Plan 07.
- The conceptual sequence may place strategy anchors and newer append-only plan files before older optional files when the product strategy requires it.
- The Plan 07 insertion and 07-13 to 08-14 shift are intentional cleanup to keep the MVP path simple before implementation work is finalized.
- Plan filenames and titles may be corrected before implementation when the existing milestone framing is architecturally wrong.
- Strategic direction should stay in this roadmap or `docs/roadmap/*`; create a standalone `.agents/plans/NN-*.md` file only when the work has concrete deliverables, acceptance criteria, and a verification path.
- Completed plans are never renamed or renumbered.
- Plans `01` through `11` and changelogs `01` through `11` are protected history. Clarifications must be appended as dated notes; do not rewrite existing body text.
- New scope changes create a new numbered plan file.
