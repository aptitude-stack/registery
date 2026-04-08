# Architecture Docs

This directory contains the normative technical description of `Aptitude Registry`.

## Reading Order

1. [`system-overview.md`](system-overview.md)
2. [`server-resolver-boundary.md`](server-resolver-boundary.md)
3. [`decision-rules.md`](decision-rules.md)
4. [`discovery-and-ranking.md`](discovery-and-ranking.md)

## Update Rules

- Update these files in the same change whenever live architecture, invariants, or ownership boundaries change.
- Prefer moving forward by editing canonical docs here rather than restating architecture in `README.md`, `.agents/*`, or module READMEs.
- When current implementation and old historical milestone docs disagree, this directory wins.
