# Plan 17 - Enterprise Control Plane and Skill Supply Chain Trust

## Goal
Define the post-launch product direction that turns `Aptitude Registry` from a
governed immutable catalog into an enterprise control plane for trusted AI
capabilities, without collapsing the existing registry-resolver boundary.

## Positioning
This is a strategy and planning milestone, not an immediate implementation
milestone. It exists to clarify where the long-term moat should come from before
the repository accumulates optional discovery, caching, or marketplace-style
work that improves the product tactically but does not strengthen its strategic
position.

This plan is intentionally numbered after existing plans to preserve append-only
roadmap history, but it should be read conceptually after Plan 14 and before
optional discovery/caching expansion plans.

## Strategic Thesis
`Aptitude Registry` should compete as the governed system of record for
enterprise skills and agent capabilities.

The moat is not:
- becoming a generic public skill marketplace
- becoming a broad managed integration platform
- collapsing registry, resolver, and runtime into one product surface

The moat is:
- trust in what is published
- governance over what is allowed
- sovereignty over where it runs
- lineage over how a capability moved from publish to production use

## Relationship to Earlier Plans

### Builds On
- Plan 10, which established governance, provenance capture, and audit as core
  registry responsibilities.
- Plan 12, which established immutable bundle artifacts and exact immutable
  fetch semantics.
- Plan 13, which clarified runtime posture and environment separation.
- Plan 14, which established the auth-boundary direction and the need for a
  stronger production security posture.

### Should Guide Later Optional Work
- Plan 15 should be treated as discovery-quality work, not as the primary moat.
- Plan 16 should be treated as scale and latency work, not as the primary moat.
- Future milestones should prioritize enterprise trust/governance surfaces
  before broad public-marketplace optimization.

## Scope
- Define the enterprise product posture for the registry:
  - primary wedge: enterprise control plane
  - preferred deployment posture: SaaS plus private-cloud/self-hosted
    compatibility
- Define the core moat pillars:
  - trust
  - governance
  - sovereignty
  - lineage
- Define the future capability families that belong in the moat:
  - private namespaces and organization ownership
  - approval and promotion workflows across environments such as `dev`,
    `staging`, and `prod`
  - verified publishers, signed bundles, and attestations
  - policy packs for internal-only, verified-only, or imported third-party
    skills
  - end-to-end traceability from publish through approval, resolution, and
    execution
  - deployment models that satisfy hosted, private-cloud, self-hosted, and
    air-gapped requirements
- Define which adjacent areas should be integrated with rather than treated as
  the registry's core identity:
  - public marketplace distribution
  - broad OAuth/connectivity aggregation
  - runtime orchestration and final skill selection

## Non-Goals
- No new public route families are defined in this milestone.
- No immediate schema or implementation work is mandated by this plan.
- No attempt to turn the registry into a solver, planner, or execution runtime.
- No attempt to match integration-platform breadth from products focused on
  managed auth and external SaaS connectivity.
- No attempt to prioritize public-catalog growth over enterprise governance.

## Recommended Architecture Direction
- Keep the current hard boundary:
  - registry owns governed facts, immutable artifacts, trust state, lifecycle,
    and audit
  - resolver/runtime owns interpretation, ranking, solving, and execution
- Add future enterprise features around the registry boundary rather than
  inside resolver logic:
  - organization and tenant controls
  - approval and promotion state
  - evidence-backed trust evaluation
  - compliance and audit reporting
- Treat provenance as insufficient on its own. Future trust tiers should be
  backed by verifiable evidence such as signatures, attestations, publisher
  verification, or build-pipeline proofs.
- Treat third-party ecosystems as import sources to be governed internally, not
  as the primary product surface to compete on directly.

## Follow-On Planning Areas
This plan should lead to concrete follow-on implementation plans for:
- organization and private-namespace ownership
- promotion channels and approval workflows
- signed artifacts and attestation verification
- enterprise policy packs and reviewer/admin roles
- execution-lineage and compliance reporting
- private-cloud, self-hosted, and air-gapped deployment packaging

## Decision Criteria
Future work should be favored when it strengthens one or more of these:
- stronger trust in artifact origin and integrity
- stronger governance over skill availability and lifecycle
- stronger deployment sovereignty for enterprise buyers
- stronger traceability from publication to real usage

Future work should be deprioritized when it only improves:
- public discovery vanity metrics
- generic marketplace breadth
- broad integration coverage better served by dedicated connectivity platforms

## Assumptions and Defaults
- The primary buyer is an enterprise platform, security, or AI-governance team
  rather than a casual public marketplace user.
- Hybrid and self-hosted compatibility matters enough to shape roadmap
  decisions now, not only after SaaS growth.
- Discovery quality remains important, but it is table stakes rather than the
  core moat.
- This repository should continue to optimize for a small, durable server
  contract rather than expanding into agent-runtime behavior.
