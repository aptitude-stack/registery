---
name: task-doc-navigator
description: Navigate Aptitude tasks by using `.agents/agent.md` as the entrypoint, especially its Task-to-Doc Map and relevant path lists, to gather the smallest set of sources needed for implementation, review, debugging, planning, or documentation work. Use when Codex should identify the most relevant docs, plans, changelogs, tests, and code paths before acting on a task.
---

# Task Doc Navigator

Use `.agents/agent.md` as the primary navigation contract.

## Workflow

1. Read `.agents/agent.md` first.
2. Classify the task before opening more files:
   - architecture or product intent
   - API or contract behavior
   - persistence, discovery, or schema work
   - milestone delivery history
   - implementation in a specific module
   - verification or test failure
3. Open only the matching docs from the `Task-to-Doc Map` and `Relevant Paths for Task Execution`.
4. Expand into code only after the minimal doc set is loaded.
5. If the task touches behavior, check the matching tests, active plan file, and prior changelog entries before editing.

## Source Selection

Start small and add sources only when they change the decision.

### Architecture and scope

Open:
- `docs/architecture/system-overview.md`
- `docs/architecture/server-resolver-boundary.md`
- `docs/roadmap/requirements-and-phases.md`

Use for:
- new features
- boundary questions
- architecture tradeoffs
- requirement clarification

### API and contract work

Open:
- `docs/reference/api-contract.md`
- `postman/collections/`
- `app/interface/`
- relevant integration tests in `tests/integration/`

Use for:
- endpoint behavior
- request or response shape
- error mapping
- manual validation flows

### Persistence and discovery

Open:
- `docs/reference/schema.md`
- `docs/reference/storage-strategy.md`
- `docs/architecture/discovery-and-ranking.md`
- `app/persistence/`
- `alembic/versions/`

Use for:
- schema or migration changes
- repository behavior
- ranking, filtering, or candidate selection

### Delivery history and sequencing

Open:
- active `.agents/plans/XX-*.md`
- `.agents/plans/roadmap.md`
- `docs/changelog/`
- `memory/meta.md`

Use for:
- milestone alignment
- acceptance criteria
- earlier design decisions
- avoiding duplicate work

### Code-path lookup

Use the path lists in `.agents/agent.md` to jump to the smallest likely module:
- `app/main.py` for composition and wiring
- `app/interface/` for routes and DTOs
- `app/core/` for domain logic and governance
- `app/intelligence/` for ranking and search logic
- `app/persistence/` for models and repositories
- `app/audit/` for audit-facing behavior

### Verification lookup

Open only the matching verification surface:
- `tests/unit/` for pure logic and service behavior
- `tests/integration/` for API, repository, and migration behavior
- `.github/workflows/` for CI command patterns
- `scripts/` when repo tooling is part of the task

## Output

Report the source map before substantial implementation when the task is non-trivial.

Use this compact format:

```text
Task class: <one line>
Primary docs: <paths>
Primary code paths: <paths>
Verification paths: <paths>
Deferred sources: <paths not opened yet>
```

## Guardrails

- Prefer the smallest relevant set of files over broad repo scans.
- Read `rules/repo.md` when approval gates, repo rules, or process constraints may matter.
- If a task clearly maps to one section in `.agents/agent.md`, do not open unrelated docs “just in case”.
- If the task spans multiple areas, load sources in this order: rules, active plan, task-mapped docs, code paths, tests, changelog.
- When reporting file references or source maps, use repo-relative paths or GitHub links only.
- Never emit workstation-specific absolute paths such as `/path/to/repo/...`.
