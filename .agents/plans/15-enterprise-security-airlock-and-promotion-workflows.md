# Plan 15 - Enterprise Security Airlock and Promotion Workflows

## Goal
Turn the registry moat from strategy into concrete enterprise control-plane
capabilities: private ownership, artifact intake review, promotion channels,
policy packs, and audit-backed trust state.

## Strategic Role
This is the first implementation-facing milestone after the enterprise
control-plane anchor in `roadmap.md`. It makes the registry the security airlock
for agentic artifacts rather than only an immutable storage service.

The registry still does not become a solver, planner, gateway, identity
directory, or execution runtime. It owns the governed facts and approval state
that those adjacent products can consume.

## Scope
- Add organization and private-namespace ownership for skills and published
  versions.
- Add reviewer/admin roles for trust and lifecycle decisions.
- Add promotion channels for artifact governance, such as `dev`, `staging`, and
  `prod`. These are artifact promotion channels, not `APP_ENV` runtime profiles.
- Add approval workflow state for imported, internal, verified, restricted, and
  rejected artifacts.
- Add policy-pack references that can express catalog-level rules such as:
  - internal-only artifacts
  - verified-publisher-only artifacts
  - third-party imported artifacts requiring review
  - restricted artifacts visible only to approved namespaces or service tokens
- Add evidence-backed trust fields for publisher verification, signatures,
  attestations, review records, and build-pipeline proofs.
- Add audit events for review decisions, promotion changes, trust-tier changes,
  policy-pack assignment, and namespace ownership changes.

## Non-Goals
- No resolver-owned solving, lock generation, prompt interpretation, or final
  skill selection moves into the registry.
- No runtime gateway interception, egress enforcement, token budgeting, or agent
  identity issuance is implemented here.
- No broad public marketplace surface is prioritized over private enterprise
  governance.
- No automated artifact-evolution loop may bypass review, provenance,
  promotion, or lifecycle controls.

## Recommended Architecture Direction
- Model namespace ownership and promotion state as registry-controlled facts
  close to skill versions and lifecycle state.
- Keep immutable artifact bytes and version coordinates unchanged. Promotion and
  approval state controls visibility and eligibility, not artifact contents.
- Extend admin/control-plane APIs only where the existing lifecycle/governance
  route family cannot represent enterprise workflow decisions cleanly.
- Keep resolver-facing discovery, resolution, exact metadata, and exact content
  semantics stable. Enterprise governance may filter eligibility, but must not
  return solved bundles or runtime plans.
- Treat policy packs as references and registry-enforced visibility rules first.
  Deeper runtime policy enforcement belongs to gateway-facing follow-on work.

## Acceptance Criteria
- A private namespace can own a skill without changing immutable artifact
  coordinates.
- An imported third-party artifact can be held for review before becoming
  discoverable to a production namespace.
- A reviewed artifact can be promoted between governance channels without
  rewriting metadata or bundle content.
- Discovery and exact reads consistently enforce namespace, lifecycle, trust,
  promotion, and policy-pack visibility.
- Every review, promotion, policy, and ownership decision emits audit evidence.
- Existing resolver-facing route behavior remains data-local and execution-free.

## Assumptions and Defaults
- Enterprise adoption depends more on controlled artifact admission than on
  public catalog size.
- Promotion channels are governance concepts, not app runtime environments.
- PostgreSQL remains the authoritative store for registry trust state.
- Future gateway, identity, and token-control products consume this trust state
  rather than owning registry artifact truth.
