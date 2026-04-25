# Documentation Guidelines

## Canonical Homes

- `docs/architecture/*`: canonical current-state explanation and invariants
- `docs/reference/*`: canonical contracts, schema, settings, and runbooks
- `docs/contributors/*`: canonical tutorials and how-to workflow guidance
- `docs/roadmap/*`: canonical PRD plus forward-looking explanation
- `docs/drafts/*`: non-canonical working analysis only
- `docs/changelog/*`: implementation history only
- `.agents/*`: derivative agent operating context only

## Edit The Canonical Doc When

- Update canonical docs in the same change when behavior, architecture, or reference truth changes.
- Keep one canonical home per truth. Link instead of repeating the same explanation in multiple places.
- Keep root `README.md` concise; push durable detail into `docs/`.

## Create A Draft Only When

- The design is unresolved and should not yet be treated as current truth.
- The document is exploratory context, not a live contract or workflow.
- The file starts with a status line and links to the live canonical sources.

## Promote, Merge, Or Delete

- Promote by moving settled truth into `docs/architecture/*`, `docs/reference/*`, `docs/contributors/*`, or `docs/roadmap/*`.
- Merge when a draft overlaps a canonical doc but still contains useful framing that should survive.
- Delete when the draft is duplicated, superseded, abandoned, or misleading.

## Writing Rules

- Separate current-state docs from roadmap material.
- Mark drafts and future direction clearly.
- Prefer short, factual prose over milestone-story narration in canonical docs.
- Historical changelogs stay historical; do not use them as the live source of truth.
