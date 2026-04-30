# Plan 15 - Enterprise Control Plane and Skill Supply Chain Trust

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

## Market Research Synthesis
The market research in
[`../../docs/roadmap/market-research.md`](../../docs/roadmap/market-research.md)
shows a clear split between open developer marketplaces and enterprise
agentic-governance platforms. Open catalogs optimize for distribution and
developer velocity. Enterprise buyers need a controlled system of record that
can prove which artifact was admitted, who approved it, which policy allowed it,
and which immutable version was later used.

For this repository, the actionable insight is narrow: `Aptitude Registry`
should be the enterprise security airlock and governed source of truth for
agentic artifacts. Gateway interception, cryptographic agent identity, and
token/spend controls are important Aptitude product surfaces, but they should
consume registry facts instead of moving runtime execution ownership into this
server.

## Strategic Thesis
`Aptitude Registry` should compete as the governed system of record for
enterprise skills and agent capabilities.

The moat is not:
- becoming a generic public skill marketplace
- becoming a broad managed integration platform
- collapsing registry, resolver, and runtime into one product surface
- owning runtime gateway interception, agent identity issuance, or token-budget
  enforcement inside the registry service
- making LLM-driven artifact optimization the near-term registry wedge

The moat is:
- security-airlock control over what is admitted into the catalog
- verifiable provenance, signatures, attestations, and publisher trust
- governance over what is allowed, promoted, deprecated, or archived
- private namespace and organization ownership for enterprise catalog control
- policy packs for internal, imported, verified, and restricted artifacts
- audit lineage from publish through approval, resolution reads, and production
  use
- deployment sovereignty across hosted, private-cloud, self-hosted, and
  air-gapped environments

## Relationship to Earlier Plans

### Builds On
- Plan 10, which established governance, provenance capture, and audit as core
  registry responsibilities.
- Plan 12, which established immutable bundle artifacts and exact immutable
  fetch semantics.
- Plan 13, which clarified runtime posture and environment separation.
- Plan 14, which established the auth-boundary direction and the need for a
  stronger production security posture.

## Scope
- Define the enterprise product posture for the registry:
  - primary wedge: enterprise control plane
  - preferred deployment posture: SaaS plus private-cloud/self-hosted
    compatibility
- Define the core moat pillars:
  - security airlock
  - verifiable provenance
  - promotion and governance workflows
  - policy packs
  - private namespaces
  - audit lineage
  - deployment sovereignty
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
  - runtime gateway enforcement
  - agent identity directory ownership
  - token and spend controls
  - runtime orchestration and final skill selection

## Non-Goals
- No new public route families are defined in this milestone.
- No immediate schema or implementation work is mandated by this plan.
- No attempt to turn the registry into a solver, planner, or execution runtime.
- No attempt to match integration-platform breadth from products focused on
  managed auth and external SaaS connectivity.
- No attempt to prioritize public-catalog growth over enterprise governance.
- No attempt to make runtime gateway interception, cryptographic agent identity
  issuance, or token-budget enforcement registry-owned responsibilities.
- No attempt to prioritize autonomous artifact evolution or LLM-driven
  optimization before the trust, governance, and audit foundation is concrete.

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
- Treat gateway, identity, and token-control products as downstream consumers of
  registry trust state:
  - gateway decisions should ask whether a specific agent can load a specific
    approved artifact version
  - identity systems should bind agent principals to registry visibility and
    policy scopes
  - token and spend controls should attribute usage to agent, artifact version,
    organization, and policy context
- Keep artifact optimization and evaluation loops behind governance. Improved
  artifacts should re-enter the same publish, approval, provenance, and
  lifecycle flow instead of bypassing the security airlock.

## Follow-On Planning Areas
This plan decomposes into concrete follow-on plans:
- Plan 17: enterprise security airlock and promotion workflows, covering
  organization ownership, private namespaces, approval workflows, policy packs,
  reviewer/admin roles, evidence-backed trust, and audit.
- Plan 18: registry trust consumer contracts, covering the exact registry facts
  that gateway, identity, and token-control surfaces consume without moving
  their runtime responsibilities into this repository.

Remaining future planning areas after those two plans:
- private-cloud, self-hosted, and air-gapped deployment packaging
- compliance reporting over publish, approval, promotion, and downstream runtime
  evidence

## Decision Criteria
Future work should be favored when it strengthens one or more of these:
- stronger trust in artifact origin and integrity
- stronger governance over skill availability and lifecycle
- stronger deployment sovereignty for enterprise buyers
- stronger traceability from publication to real usage
- stronger ability for adjacent Aptitude surfaces to consume registry trust
  state without weakening the registry-resolver boundary

Future work should be deprioritized when it only improves:
- public discovery vanity metrics
- generic marketplace breadth
- broad integration coverage better served by dedicated connectivity platforms
- runtime orchestration breadth better owned by gateway, resolver, or execution
  products
- autonomous optimization loops that are not first constrained by enterprise
  promotion, approval, and audit policy

## Assumptions and Defaults
- The primary buyer is an enterprise platform, security, or AI-governance team
  rather than a casual public marketplace user.
- Hybrid and self-hosted compatibility matters enough to shape roadmap
  decisions now, not only after SaaS growth.
- Discovery quality remains important, but it is table stakes rather than the
  core moat.
- This repository should continue to optimize for a small, durable server
  contract rather than expanding into agent-runtime behavior.
- Gateway, identity, and token-control surfaces are part of the broader Aptitude
  product definition, but this registry repository should define the governed
  facts those surfaces consume rather than implement their runtime authority.
