# Aptitude PRD - Registry Subsystem Perspective

## 1. What is this part of the product?

`Aptitude Registry` is the governed catalog and retrieval backend for AI skills inside the Aptitude system.

Its role is to be the system of record for published skills. It stores immutable skill versions, searchable metadata, raw skill content, dependency declarations, lifecycle status, provenance, and audit history, then exposes that information through a stable API so the rest of Aptitude can publish skills, discover candidates, and retrieve exact versions safely.

## 2. What problems does it help solve?

### Accessibility for agents

AI agents should not need to browse repositories, scrape documentation, or infer which skill version is safe to use. This subsystem makes skills agent-accessible by turning them into structured, exact, API-readable artifacts. It provides discovery for finding candidates, exact fetch for retrieving the chosen artifact, and exact dependency reads for understanding authored relationships.

This matters because agents work best when capabilities are exposed as stable contracts rather than loose files and conventions.

### Quality and security of skills

This subsystem addresses trust and quality by enforcing immutability, storing provenance, tracking trust tiers, and separating published, deprecated, and archived states. It also records audit events around key operations.

This matters because a skill catalog becomes risky very quickly if published artifacts can change silently, if provenance is unclear, or if unsafe skills remain discoverable without controls.

### Governance and controlled usage

The registry acts as the enforcement point for policy at the catalog boundary. It controls who can publish, who can read, which lifecycle states are visible, and which actions require elevated privileges.

This matters because Aptitude needs a central place where platform teams can govern skill availability without embedding policy logic into every consumer.

### Dependency management and modularity

The subsystem preserves direct authored dependency selectors instead of solving them itself. That gives Aptitude a clean split: the registry stores declared modular relationships, while another subsystem decides how to resolve them in context.

This matters because it keeps skills composable without turning the catalog into a runtime planner or introducing hidden server-side behavior.

## 3. What solution does it provide?

The general solution is a registry-first backend for AI skills.

It provides:

- A publish pipeline for turning authored skills into immutable versioned artifacts.
- Structured storage for metadata, content, provenance, lifecycle, and relationships.
- Indexed discovery so consumers can ask for likely candidates without scanning the whole catalog.
- Exact-read APIs so downstream systems can retrieve a precise skill version and its direct dependencies.
- Governance and audit controls around what can be published, read, deprecated, or archived.

Conceptually, this is the authoritative catalog plus policy layer for Aptitude skills.

## 4. Who uses this?

### Infrastructure and governance users

Platform, operations, and governance teams use this subsystem to control publication, enforce trust and lifecycle policy, monitor the catalog, and audit activity.

### End users

Skill authors and CI or publishing pipelines use it when releasing new skills or new versions of existing skills.

### AI agents

AI agents are consumers of this subsystem indirectly through resolver, CLI, or MCP-style clients. They rely on it as the source of discoverable, exact, governed skill artifacts, even if they do not interact with it as humans do.

## 5. What is the experience?

In practice, this subsystem participates in a few simple flows:

1. A publisher submits a new skill version with content, metadata, governance fields, and declared relationships.
2. The registry validates policy, immutability, and structure, then stores the result as a new immutable version.
3. A consuming system sends a discovery request and receives ordered candidate skill slugs.
4. The consuming system selects a specific `(slug, version)` and fetches exact metadata or exact content.
5. If needed, the consumer asks for the skill's direct authored dependencies.
6. Governance users can deprecate or archive versions, which changes visibility and read behavior.
7. Operators use health, readiness, metrics, and audit outputs to keep the service reliable.

Inputs are published skill artifacts and structured search requests. Outputs are candidate identifiers, exact metadata, raw content, dependency selectors, lifecycle outcomes, and operational telemetry.

## 6. Features and why they exist

### Immutable skill publishing

What it does:
Accepts versioned skill publication and stores it as a permanent artifact.

Why it exists:
Consumers need exact, repeatable references. Silent mutation would make skills unsafe to reuse and impossible to audit.

How it contributes:
Creates the trustworthy foundation for everything else in Aptitude.

### Searchable discovery

What it does:
Returns ordered candidate skill slugs based on metadata-driven search.

Why it exists:
Consumers need a practical way to find relevant skills without traversing the full catalog.

How it contributes:
Makes the catalog usable at scale, especially for agent-driven retrieval flows.

### Exact metadata and content fetch

What it does:
Returns the exact metadata or exact raw skill content for a chosen version.

Why it exists:
Discovery is not enough; downstream systems need a precise artifact they can inspect, cache, and execute against.

How it contributes:
Turns the registry from a catalog into an operational source of truth.

### Direct dependency reads

What it does:
Returns the first-degree `depends_on` declarations authored with the skill.

Why it exists:
Skills need to remain modular, but the registry should expose declared relationships without becoming the runtime dependency solver.

How it contributes:
Supports composability while preserving architectural separation.

### Lifecycle governance

What it does:
Supports `published`, `deprecated`, and `archived` states with visibility and access rules.

Why it exists:
Not every skill version should remain equally visible or usable forever.

How it contributes:
Lets Aptitude evolve safely without deleting history or exposing outdated artifacts by default.

### Provenance and trust metadata

What it does:
Captures origin information and associates versions with trust-related context.

Why it exists:
Consumers and governance teams need to know where a skill came from and how much confidence to place in it.

How it contributes:
Improves security posture and makes the registry suitable for enterprise or controlled environments.

### Audit and operational telemetry

What it does:
Records registry-side events and exposes health, readiness, and metrics surfaces.

Why it exists:
A central catalog needs accountability and operability, not just storage.

How it contributes:
Makes the subsystem manageable in production and usable as infrastructure rather than just a database-backed app.

## 7. How it fits in the system

This subsystem depends on:

- PostgreSQL as the authoritative runtime store.
- Publisher or CI workflows to submit skills.
- Auth and policy configuration to enforce controlled access.

What depends on it:

- Resolver-like components that need discovery candidates and exact skill reads.
- CLI, MCP, or other clients that publish or retrieve skills.
- Governance and operations workflows that need lifecycle control and auditability.

How it connects to other parts:

- It sits upstream of the resolver for catalog access.
- It does not choose the final skill, solve dependencies, or generate execution plans.
- It is the registry and storage boundary, while the resolver remains the runtime decision boundary.
- A publisher subsystem likely packages and submits artifacts into this service rather than storing them directly elsewhere.

## 8. Gaps and future direction

Based on the docs, roadmap, and app structure, the likely gaps are:

- Discovery is intentionally lexical and metadata-driven today. More advanced semantic or co-usage discovery appears planned.
- Cache semantics are present, but full conditional read behavior looks like an area still being hardened.
- Observability exists, but richer production-grade instrumentation and release readiness are still being matured.
- Governance is strong at a basic level, but deeper policy packs, signatures, and attestations appear to be future work.
- Environment separation and token governance are recognized as important next steps.
- The subsystem is intentionally not yet a full agent-facing resolution layer; it stops at governed storage and exact reads, leaving richer decision-making to other parts of Aptitude.

The next likely steps are to harden the public contract, improve discovery quality, strengthen trust and provenance guarantees, and mature the operational surface for production use.

## 9. Summary

`Aptitude Registry` is the subsystem that turns AI skills into governed, immutable, searchable product artifacts. It gives Aptitude a reliable way to publish skills, discover likely candidates, retrieve exact versions, preserve modular relationships, and enforce lifecycle and trust policy at the catalog boundary.

It matters because Aptitude cannot scale safely if skills are just scattered files or informal conventions. This subsystem makes skills accessible to agents, governable by platform teams, and stable enough for the rest of the system to build on.
