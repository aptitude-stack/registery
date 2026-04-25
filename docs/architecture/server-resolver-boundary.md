# Server-Resolver Boundary

> Status: canonical ownership contract between `Aptitude Registry` and `aptitude-resolver`.
> Use [`../reference/api-contract.md`](../reference/api-contract.md) for the live route contract.

## Purpose

This document defines the hard split between registry responsibilities and resolver responsibilities.

The split exists so indexed retrieval and immutable storage stay close to the database, while prompt-sensitive decision-making stays close to the runtime context that actually needs it.

## Core Rule

- Registry owns data-local work.
- Resolver owns decision-local work.

## Registry Owns

- immutable publish
- discovery candidate generation
- exact dependency reads
- exact immutable metadata/content fetch
- lifecycle governance
- provenance capture
- audit and observability at the registry boundary

## Resolver Owns

- prompt interpretation
- discovery request construction
- reranking and pruning
- final skill selection
- dependency solving
- lock generation and replay
- execution planning

## Contract Consequences

- Discovery returns ordered candidate slugs only.
- Resolution returns direct authored `depends_on` selectors only.
- Exact fetch returns immutable metadata or the immutable stored bundle artifact for one coordinate.
- The registry never returns canonical solved bundles or runtime plans.

## Design Rationale

- Search belongs on the registry because it is an indexed retrieval problem.
- Final selection belongs on the resolver because it depends on prompt nuance, policy, environment, and installed state.
- Dependency solving belongs on the resolver because runtime reproducibility must be tied to a client-owned lock, not to mutable server-side solve state.
