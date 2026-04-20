# Registry Feature Rationale

> Status: explanatory rationale for the current `Aptitude Registry` feature surface.
> Use [`../reference/api-contract.md`](../reference/api-contract.md) for the canonical HTTP contract, [`../reference/schema.md`](../reference/schema.md) for the canonical schema baseline, and [`../architecture/server-resolver-boundary.md`](../architecture/server-resolver-boundary.md) for the hard registry-resolver split.

This document explains why each current registry feature exists, what it means, who it is for, and how to defend it in review.

The goal is not to justify every possible server capability. The goal is to keep the registry small and deliberate: every route, table, and policy rule should support at least one of these product values:

- immutable publication
- deterministic exact reads
- bounded discovery
- auditable governance
- operational simplicity
- a hard boundary between registry facts and resolver decisions

## Product Mental Model

`Aptitude Registry` is a package-registry-style backend for AI skills.

It is not a planner, not an agent runtime, and not a solver. It stores and serves governed, immutable skill facts so downstream clients can make their own decisions without scraping, guessing, or depending on mutable server-side state.

The registry owns facts:

- immutable skill identity and versions
- immutable bundle artifacts
- structured metadata
- authored dependency selectors
- lifecycle state
- trust tier
- provenance snapshots
- audit events
- search-facing derived documents

The resolver or client owns decisions:

- prompt interpretation
- discovery request construction
- reranking and pruning
- final candidate choice
- dependency solving
- lock generation and replay
- execution planning

This split matters because storage and indexed retrieval should stay close to the database, while decision-making should stay close to the caller’s prompt, policy, and runtime context.

## Completeness vs Boundary

“Why doesn’t the registry do more?” is usually the wrong question.

The correct question is whether the feature belongs on the data side or the decision side.

| Layer | Question | Example |
| --- | --- | --- |
| Registry fact | What immutable record or policy-gated read should exist? | Publish `python.lint@1.2.3`, fetch its bundle, or read its authored `depends_on`. |
| Resolver decision | What should happen for this caller right now? | Choose between several candidates, solve the full graph, or produce a lockfile. |

This is why the registry has a public `resolution` route but does not return solved bundles. Reading direct authored selectors is a fact. Solving them is a decision.

## Current Feature Rationale

### Immutable publish

What it does:

- Accepts a normalized publish payload for one `slug@version`.
- Validates request shape, governance inputs, and authored relationships.
- Persists immutable metadata, one immutable `.tar.zst` bundle artifact, and authored selectors.
- Rejects overwrite attempts for an existing `(slug, version)`.

Why it exists:

- Skills have to become durable shared artifacts before they are discoverable or reproducible.
- A mutable publish model would make downstream fetches and audits unreliable.
- The registry is the narrow enforcement point where immutability, provenance capture, and publish-time policy can be applied consistently.

Audience:

- publisher clients
- CI pipelines
- platform teams controlling intake into the catalog

Quality bar:

- Must reject duplicate immutable versions.
- Must not depend on Git at read time.
- Must persist enough publish-time context to support later audit and trust review.

### Discovery candidate generation

What it does:

- Accepts a structured discovery request.
- Searches indexed metadata and descriptions.
- Returns ordered candidate slugs only.
- Applies discovery visibility rules before returning results.

Why it exists:

- Consumers need a fast, indexed way to narrow the search space without crawling the whole catalog.
- Discovery belongs on the registry because it is a data-local retrieval problem over indexed metadata.
- Returning only slugs prevents the server from quietly turning discovery into “selection with explanation,” which would blur the registry-resolver boundary.

Audience:

- resolver clients
- CLI or MCP consumers
- operators debugging retrieval quality

Quality bar:

- Keep responses compact and deterministic.
- Do not return solved bundles, rationale prose, or final winner claims.
- Stay optimized for catalog lookup, not prompt interpretation.

### Exact identity read

What it does:

- Returns the visible immutable versions for one skill slug.
- Marks the derived current default among visible versions.
- Keeps ordering deterministic.

Why it exists:

- Clients often know the skill identity but not the exact version yet.
- Listing visible versions is a safe read surface that supports inspection and default-version behavior without duplicating the full metadata payload for every version.
- The current default is derived, not stored as mutable global state, which avoids a “latest pointer” becoming a second source of truth.

Audience:

- resolver and CLI clients
- reviewers validating lifecycle visibility
- operators debugging version state

Quality bar:

- Missing or invisible slugs should not leak hidden state.
- Default selection must be derived from visible immutable versions, not from an editable pointer.

### Exact dependency read

What it does:

- Returns direct authored `depends_on` selectors for one exact immutable version.
- Preserves version constraints, optionality, and markers as published.
- Does not recurse or solve.

Why it exists:

- Downstream resolvers need the authored dependency intent as input to solving.
- Preserving selectors exactly as authored keeps the registry honest: it stores declarations, not computed closures.
- Returning only first-degree selectors keeps the registry from becoming a hidden planner.

Audience:

- resolvers
- integration tests
- maintainers debugging dependency declarations

Quality bar:

- Must preserve author intent exactly.
- Must not synthesize transitive edges, lockfiles, or compatibility claims.

### Exact metadata fetch

What it does:

- Returns immutable metadata for one exact `slug@version`.
- Includes version and content digests, lifecycle state, trust tier, and advisory provenance when available.

Why it exists:

- Consumers need a machine-readable, exact description of what one immutable coordinate means before they use or materialize it.
- Metadata is valuable independently of the stored bundle artifact for policy evaluation, debugging, and UI or CLI inspection.
- Keeping metadata separate from artifact bytes avoids dragging large payloads into every exact-read path.

Audience:

- resolver clients
- reviewers
- admin and governance tooling

Quality bar:

- Response shape should stay stable and exact-coordinate-based.
- Metadata fetch must not become a fuzzy search or convenience bundle API.

### Exact content fetch

What it does:

- Returns the immutable stored `application/zstd` bundle for one exact `slug@version`.
- Emits digest-based cache validation headers.
- Increments usage/install counters through the exact fetch path.

Why it exists:

- Materialization and execution need the real published artifact, not just metadata.
- A separate content route lets discovery and metadata reads stay light while exact content fetch stays simple and cacheable.
- Digest-backed reads make immutable artifacts easy to verify and cheap to reuse.

Audience:

- resolvers and installers
- cache-aware clients
- operators debugging content delivery

Quality bar:

- Return the exact stored bundle only.
- Keep immutable cache semantics explicit.
- Avoid coupling content fetch to any search index or source repository checkout.

### Lifecycle update

What it does:

- Allows an admin caller to transition one immutable version between lifecycle states such as `published`, `deprecated`, and `archived`.

Why it exists:

- Immutability of content does not remove the need for governance over visibility and support status.
- Teams need a way to stop recommending or exposing risky versions without rewriting history.
- Lifecycle is how the registry supports safe evolution while preserving exact historical records.

Audience:

- admins
- governance and security teams
- operators handling incidents or retirement flows

Quality bar:

- Status transitions must be policy-controlled and auditable.
- Lifecycle must affect visibility, not mutate the artifact itself.

### Health, readiness, and metrics

What it does:

- Exposes `healthz`, `readyz`, and `metrics` as operational endpoints.

Why it exists:

- A registry is only useful if operators can tell whether it is alive, dependency-ready, and scrapeable.
- Operability should be a first-class server concern rather than an afterthought layered onto business routes.

Audience:

- platform and SRE teams
- local developers
- deployment automation

Quality bar:

- Keep operational routes simple, unauthenticated where appropriate, and separate from business semantics.

## Route Rationale

### `POST /skills/{slug}`

Why this route exists:

- The registry needs one clear immutable publish entrypoint.
- Using the slug in the path reinforces that publish is scoped to a stable skill identity, not an opaque artifact blob upload.

Why it should not become broader:

- It should not turn into a mutable update route.
- It should not accept partial patch semantics for existing versions.

### `POST /discovery`

Why this route exists:

- Discovery requests are structured search input, not a simple path lookup.
- A request body leaves room for metadata fields such as name, description, and tags without inventing fragile query-string mini-languages.

Why it stays body-based:

- The product wants discovery to be explicit, typed, and extensible.
- Path- or query-only search would push complexity into ad hoc parsing and make the contract harder to evolve.

### `GET /skills/{slug}`

Why this route exists:

- Identity reads and exact version reads are different jobs.
- Listing visible versions is a common inspection step that should not require clients to already know the version.

Why it stays narrow:

- It should not inline full bundle payloads or become a bulk catalog endpoint.

### `GET /resolution/{slug}/{version}`

Why this route exists:

- Clients need exact direct dependency declarations as a standalone read surface.
- Keeping `resolution` public makes the registry useful to deterministic clients without giving it solver responsibility.

Why it does not recurse:

- Recursive solving would create hidden server-side planning behavior and weaken lock ownership on the client side.

### `GET /skills/{slug}/{version}`

Why this route exists:

- Clients need exact immutable metadata for one coordinate.
- It is the right place for lifecycle, trust, checksum, and provenance fields.

Why it is separate from content:

- Metadata and bundle delivery have different access patterns, response sizes, and cache characteristics.

### `GET /skills/{slug}/{version}/content`

Why this route exists:

- Raw content delivery deserves its own exact, cacheable read path.
- It keeps content materialization simple and lets metadata reads stay cheap.

Why it returns the bundle directly:

- Wrapping the artifact in another JSON envelope would add overhead without adding meaning for the core use case.

### `PATCH /skills/{slug}/{version}/status`

Why this route exists:

- Lifecycle is mutable governance state scoped to an immutable version.
- A focused status route makes that distinction explicit.

Why it should remain limited:

- It should not become a generic mutable metadata patch endpoint.

### `GET /healthz`, `GET /readyz`, `GET /metrics`

Why these routes exist:

- Operators need standard service probes.
- Business correctness without operational visibility is not enough for a shared registry.

## Data Model Rationale

### Stable skill identity plus immutable versions

Why it exists:

- A skill slug is a long-lived identity.
- Each version is an immutable release under that identity.
- This mirrors package-registry expectations and keeps reads reproducible.

Why this is better than a mutable latest row:

- Mutable “current content” rows are easier to overwrite accidentally.
- Derived default version logic is safer than storing a manually edited pointer.

### Split metadata and content storage

Why it exists:

- Discovery and metadata-heavy reads should not touch large markdown bodies by default.
- Exact content fetches should stay direct and simple.

Why this is the right current tradeoff:

- The repo explicitly chose PostgreSQL-only storage with split query paths instead of filesystem or object storage because current artifact sizes are small and operational simplicity matters more than theoretical scale.

### Digest-addressed content deduplication

Why it exists:

- Identical markdown should be stored once and reused across versions.
- Digests support integrity, caching, and exact identity of content.

Why this is valuable even for small documents:

- The benefit is not only storage savings.
- It also gives a stable content identity that can be surfaced through checksums and cache headers.

### Authored relationship selectors

Why it exists:

- The registry should preserve what the author declared, not invent computed dependency edges.
- Resolver clients need direct authored selectors as the input to their own solving logic.

Why computed closures are out of scope:

- Server-owned solved graphs would become mutable derived decision state and would compete with client-owned lockfiles.

### Derived search documents

Why it exists:

- Search needs a read model optimized for ranking and filtering.
- The canonical source of truth should still remain the immutable version, metadata, and content rows.

Why this separation matters:

- Search indexes can be rebuilt.
- Canonical publication history should not depend on search projection state being perfect.

### Audit events

Why it exists:

- Shared registries need traceability for publishes, lifecycle changes, and policy decisions.
- Audit should be append-only and separate from business payload tables.

## Governance Rationale

### Read, publish, and admin scopes

Why they exist:

- Different operations carry different risk.
- Exact reads, publication, and lifecycle changes should not all share the same permission boundary.

Why this is intentionally simple:

- The current scope model is small enough to reason about operationally.
- It is better to start with a narrow capability split than to invent a large role matrix before the real pressure exists.

### Lifecycle states

Why they exist:

- Registry operators need to control visibility and support status without deleting history.

What they mean:

- `published`: normal visible state
- `deprecated`: still readable, but no longer preferred
- `archived`: preserved for admins, hidden from normal reads

Why lifecycle is version-scoped:

- The support status of `1.2.3` may differ from `2.0.0`.
- Governance needs to act at the exact release boundary, not only at the skill identity level.

### Trust tiers and provenance

Why they exist:

- Not every published artifact should be treated the same.
- Trust and provenance let the registry capture publish-time governance context that clients can later use in filtering or review.

Why the registry stores but does not overinterpret them:

- The registry should validate and persist this context.
- The resolver remains free to decide how strongly to rank or require it.

## Non-Goals

The registry should not become:

- a prompt interpreter
- a reranker that picks the final winner
- a dependency solver
- a lockfile generator
- an execution planner
- a runtime agent host
- a mutable artifact editing service

If a proposed feature crosses one of those lines, the burden of proof should be high. In most cases it belongs in the resolver or another downstream client.
