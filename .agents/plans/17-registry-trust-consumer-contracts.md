# Plan 18 - Registry Trust Consumer Contracts

## Goal
Define the registry-owned facts and decision context that adjacent Aptitude
surfaces need for gateway enforcement, agent identity, and token/spend
attribution without moving those runtime responsibilities into the registry.

## Strategic Role
Plan 15 names gateway, identity, and token control as important product surfaces
for the broader Aptitude moat. This plan defines the registry side of those
integrations: which artifact, namespace, policy, provenance, and audit facts are
authoritative enough for other products to consume.

The registry remains the source of governed artifact truth. Adjacent products
own runtime interception, principal issuance, spend accounting, and execution
control.

## Scope
- Define a trust-consumer context for one exact artifact coordinate containing:
  - `slug`
  - `version`
  - content digest and artifact media type
  - namespace and organization ownership
  - lifecycle status
  - promotion channel eligibility
  - trust tier
  - policy-pack references
  - publisher identity and verification state
  - signature and attestation summary
  - audit correlation fields
- Define how a gateway can consume registry facts to decide whether a principal
  may load a specific approved artifact version.
- Define how an identity surface can bind agent principals to registry
  namespaces, scopes, and policy visibility.
- Define how a token/spend-control surface can attribute usage to agent,
  organization, artifact coordinate, trust tier, promotion channel, and policy
  context.
- Define audit handoff fields so downstream runtime events can be correlated
  back to registry publish, approval, and promotion evidence.

## Non-Goals
- No gateway runtime interception is implemented in the registry.
- No cryptographic agent identity issuance or identity-directory lifecycle is
  implemented in the registry.
- No token budget enforcement, billing ledger, or spend dashboard is implemented
  in the registry.
- No tool execution, egress enforcement, sandboxing, prompt interpretation,
  resolver reranking, dependency solving, or lock generation is implemented
  here.

## Recommended Architecture Direction
- Keep trust-consumer contracts exact-coordinate-based. Consumers should ask
  about `slug@version`, not fuzzy search results.
- Prefer a compact, stable trust context over leaking full internal schema
  shapes to downstream products.
- Include enough policy and audit identifiers for downstream products to make
  runtime decisions and emit traceable evidence without copying registry tables.
- Keep downstream runtime events append-only and correlatable to registry audit
  evidence. Do not make runtime products mutate immutable artifact records.
- Preserve the hard split:
  - registry owns artifact truth, visibility facts, and provenance evidence
  - gateway owns runtime access interception
  - identity owns agent principal lifecycle
  - token-control owns spend metering and budget enforcement
  - resolver owns final selection, solving, locks, and execution planning

## Acceptance Criteria
- A gateway can determine whether a specific principal may load one exact
  artifact version using registry-owned trust facts.
- An identity surface can map an agent principal to registry namespaces and
  policy visibility without the registry owning identity lifecycle.
- A token-control surface can attribute usage to an artifact version and policy
  context without the registry becoming a billing system.
- Audit records from adjacent products can reference registry artifact,
  promotion, policy, and approval evidence.
- Existing discovery, resolution, exact metadata, and exact content routes do
  not become runtime orchestration APIs.

## Assumptions and Defaults
- Gateway, identity, and token-control products should be able to evolve
  independently as long as they consume stable registry trust facts.
- Registry trust context should be small enough for runtime products to cache
  and reason about, but never treated as a mutable runtime plan.
- Exact immutable artifact identity remains the anchor for cross-product audit.
