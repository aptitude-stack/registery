# Architecture Docs

This directory contains the canonical current-state explanation of `Aptitude Registry`.

## What Belongs Here

- system shape and layering
- hard ownership boundaries
- implementation invariants that should survive refactors

## What Does Not

- endpoint-by-endpoint payload reference
- step-by-step setup or operator recipes
- future design proposals or historical delivery notes

## Reading Order

1. [`system-overview.md`](system-overview.md)
2. [`server-resolver-boundary.md`](server-resolver-boundary.md)
3. [`decision-rules.md`](decision-rules.md)
4. [`discovery-and-ranking.md`](discovery-and-ranking.md)

## Update Rules

- Update these files in the same change whenever live architecture, invariants, or ownership boundaries change.
- Prefer moving forward by editing canonical docs here rather than restating architecture in `README.md`, `.agents/*`, or module READMEs.
- When current implementation and old historical milestone docs disagree, this directory wins.
