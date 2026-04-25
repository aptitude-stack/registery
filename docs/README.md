# Aptitude Registry Docs

Use this directory as the canonical documentation entrypoint for contributors, reviewers, and operators.

## Taxonomy

- `architecture/`: current-state explanation of system shape, boundaries, and invariants
- `contributors/`: tutorials and how-to guides for engineers and operators working in the repo
- `reference/`: canonical technical reference for routes, schema, settings, storage, and runbooks
- `roadmap/`: product requirements and forward-looking explanation; non-normative unless promoted
- `drafts/`: working design analysis and context docs that are intentionally not canonical
- `changelog/`: protected implementation history only

Related entrypoints outside this directory:

- [`../README.md`](../README.md): cold-start repo overview
- [`../TODO.md`](../TODO.md): intentionally small near-term backlog
- [`../.agents/README.md`](../.agents/README.md): agent-only derivative context
- [`../.agents/plans/roadmap.md`](../.agents/plans/roadmap.md): canonical implementation sequence

## Read By Goal

### Understand the system

- [`architecture/README.md`](architecture/README.md): architecture reading order and normative docs
- [`architecture/system-overview.md`](architecture/system-overview.md): high-level system shape
- [`architecture/server-resolver-boundary.md`](architecture/server-resolver-boundary.md): hard ownership split with the resolver
- [`architecture/decision-rules.md`](architecture/decision-rules.md): implementation invariants and doc-sync rules

### Make or review changes

- [`contributors/README.md`](contributors/README.md): contributor entrypoint
- [`contributors/development-setup.md`](contributors/development-setup.md): environment setup and common commands
- [`contributors/testing-and-verification.md`](contributors/testing-and-verification.md): verification expectations
- [`contributors/module-guide.md`](contributors/module-guide.md): practical package ownership map
- [`contributors/documentation-guidelines.md`](contributors/documentation-guidelines.md): canonical vs derivative docs rules

### Check live technical facts

- [`reference/README.md`](reference/README.md): reference index
- [`reference/api-contract.md`](reference/api-contract.md): canonical HTTP contract
- [`reference/runtime-profiles.md`](reference/runtime-profiles.md): runtime profiles, Compose profiles, and env-var roles
- [`reference/service-token-governance.md`](reference/service-token-governance.md): bearer-token auth contract and prod auth posture
- [`reference/publish-request-schema.md`](reference/publish-request-schema.md): publish request schema
- [`reference/schema.md`](reference/schema.md): canonical PostgreSQL schema baseline
- [`reference/storage-strategy.md`](reference/storage-strategy.md): current storage decision
- [`reference/operations/README.md`](reference/operations/README.md): operational runbook index

### Review roadmap and history

- [`roadmap/README.md`](roadmap/README.md): forward-looking documentation index
- [`roadmap/requirements-and-phases.md`](roadmap/aptitude-registry-prd.md): canonical registry PRD
- [`roadmap/near-term-evolution.md`](roadmap/near-term-evolution.md): next hardening and capability themes
- [`roadmap/registry-feature-rationale.md`](roadmap/registry-feature-rationale.md): why the current registry feature surface exists and where its boundary should stay
- [`drafts/README.md`](drafts/README.md): working draft index and classification
- [`changelog/`](changelog/): protected implementation history

## Ownership Rules

- `docs/architecture/*`: canonical current-state explanation and invariants
- `docs/contributors/*`: canonical how-to and workflow guidance
- `docs/reference/*`: canonical contracts, schema, settings, and operations reference
- `docs/roadmap/*`: product requirements and forward-looking rationale, explicitly non-normative unless promoted
- `docs/drafts/*`: non-canonical working analysis; promote, merge, or delete when the idea settles
- `docs/changelog/*`: implementation history, not canonical current-state truth
- `.agents/*`: derivative agent operating context only

Historical milestone docs in [`changelog/`](changelog/) may mention old paths or the former product name. Treat them as implementation history, not as the current source of truth. Human canonical docs live under `docs/`, while implementation sequencing intentionally remains anchored in [`../.agents/plans/roadmap.md`](../.agents/plans/roadmap.md).
