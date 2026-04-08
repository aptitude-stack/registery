# Documentation Guidelines

## Canonical vs Derivative

- `docs/architecture/*`: canonical current-state architecture and invariants
- `docs/reference/*`: canonical stable reference and operations material
- `docs/contributors/*`: canonical workflow guidance for engineers
- `docs/roadmap/*`: forward-looking and explicitly non-normative
- `.agents/*`: derivative agent operating context only

## Update Expectations

- Update canonical docs in the same change when behavior, architecture, or reference truth changes.
- Do not duplicate architecture in `.agents/*` or module READMEs when a short link will do.
- Keep root `README.md` concise; push durable detail into `docs/`.

## Writing Rules

- Separate current-state docs from roadmap material.
- Mark drafts and future direction clearly.
- Prefer short, factual prose over milestone-story narration in canonical docs.
- Historical changelogs stay historical; do not use them as the live source of truth.
