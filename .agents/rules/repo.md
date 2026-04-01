# Repo Rules

Use this file for strict agent workflow rules, not for restating architecture.

## Approval Gates

- Any database schema change requires explicit user approval before implementation.
- Any public API contract change requires explicit user approval before implementation.

## Execution Discipline

- Prefer replacement and simplification over compatibility layers when cleanup is safe.
- Keep changes incremental and reviewable.
- Use `kebab-case` for new filenames and plan slugs unless tooling requires otherwise.
- Use portable repo-relative paths in docs, plans, and agent outputs.

## Documentation Sync

- Update canonical docs in `docs/` when behavior changes.
- Keep `.agents/*` thin and derivative.
- Keep `.agents/plans/roadmap.md` as the canonical implementation sequence.
- Do not rewrite protected history in plans `01-11` or changelogs `01-11`; append clarifications instead.
