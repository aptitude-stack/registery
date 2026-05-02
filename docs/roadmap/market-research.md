# Market Research - Enterprise Agentic Registry Moat

> Status: strategic research synthesis for roadmap planning.
> This is not a live API, schema, runtime, or operations reference.

## Core Finding

The agentic-artifact market is splitting into two shapes:

- open developer marketplaces that optimize for discovery and installation
  speed
- enterprise governance platforms that optimize for trust, approval,
  provenance, policy, and auditability

`Aptitude Registry` should compete in the second category. The registry moat is
not public marketplace breadth. The moat is becoming the governed system of
record and security airlock for enterprise skills and adjacent agentic
artifacts.

## Registry-Relevant Insights

Agentic artifacts are becoming package-like units of release. A skill is not
just prompt text; it can include instructions, references, templates, scripts,
metadata, provenance, and operational constraints. That makes it closer to a
software artifact than a loose document.

Enterprise buyers need control over artifact admission before runtime use:

- what was published
- who published it
- which source or build produced it
- who reviewed it
- which policy allowed it
- which immutable version was later loaded or executed

This favors a registry design built around immutable coordinates, signed or
attested artifacts, private ownership, policy-controlled visibility, and audit
lineage.

## Competitive Landscape

Open marketplaces such as skills directories are useful for ecosystem growth,
but they do not provide enough enterprise control on their own. They emphasize
developer velocity, shared community packages, and broad discovery.

Infrastructure incumbents are moving toward governed AI artifact systems:

- GitHub and OCI-style distribution treat skills as supply-chain artifacts.
- Microsoft-style policy-as-code emphasizes deterministic runtime governance.
- Google-style agent platforms emphasize gateway, identity, and sandboxed
  execution inside a cloud ecosystem.
- JFrog-style platforms emphasize artifact provenance, scanning, promotion, and
  supply-chain trust.

The gap for Aptitude is sovereign interoperability: enterprise governance over
agentic artifacts without forcing the organization into one cloud, one IDE, one
agent framework, or one runtime.

## Product Positioning

`Aptitude Registry` should be the governed source of truth for enterprise
agentic artifacts. Its primary product promise is:

- admit only reviewed or policy-eligible artifacts
- preserve immutable versions and content digests
- attach provenance, signatures, attestations, and trust evidence
- control lifecycle, promotion, and visibility
- expose compact facts that downstream resolver, gateway, identity, and
  token-control products can consume
- provide audit lineage from publish through approval and later runtime use

The broader Aptitude product may include gateway interception, agent identity,
and token/spend control, but those should consume registry-owned trust facts
rather than moving runtime execution authority into the registry service.

## Moat Pillars

### Security Airlock

The registry is the controlled intake point for internal and imported agentic
artifacts. Third-party skills should be imported, reviewed, and governed inside
enterprise namespaces before production availability.

### Verifiable Provenance

Trust should move beyond publisher claims. Future trust tiers should be backed
by signatures, attestations, source/build evidence, and reviewer decisions.

### Governance Workflows

Enterprise adoption needs private namespaces, reviewer/admin roles, promotion
channels, lifecycle controls, policy packs, and audit trails.

### Deployment Sovereignty

The product should support hosted, private-cloud, self-hosted, and eventually
air-gapped deployment models. This matters because regulated enterprises often
cannot rely only on a vendor-hosted control plane.

### Cross-Product Trust Facts

Gateway, identity, and token-control products need stable registry facts:
artifact coordinate, digest, namespace, lifecycle, promotion state, trust tier,
policy references, provenance summary, and audit correlation identifiers.

## Planning Implications

- The enterprise control-plane anchor in `.agents/plans/roadmap.md` should
  remain the market-backed product/moat anchor.
- Plan 16 should turn the moat into concrete registry governance: security
  airlock, private namespaces, promotion workflows, policy packs, verified
  publishers, signatures, attestations, and audit.
- Plan 17 should define registry trust-consumer contracts for gateway, identity,
  and token/spend surfaces without moving those runtime responsibilities into
  the registry.
- Plan 18 hybrid discovery and Redis caching are useful supporting capabilities,
  but they should follow the enterprise trust foundation instead of being
  treated as the moat.

## Explicit Non-Goals

- Do not optimize first for public-catalog growth.
- Do not turn the registry into a solver, planner, gateway, identity directory,
  token-budget system, or execution runtime.
- Do not let automated artifact evolution bypass publish, review, provenance,
  promotion, lifecycle, or audit controls.
- Do not make broad SaaS integration coverage the registry identity.
