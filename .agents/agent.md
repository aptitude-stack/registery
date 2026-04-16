# Aptitude Registry Agent Contract

Use this file as the thin operating contract for agents working in this repo.

## Required Reading Order

1. [`../docs/README.md`](../docs/README.md)
2. [`../docs/architecture/README.md`](../docs/architecture/README.md)
3. [`../docs/reference/api-contract.md`](../docs/reference/api-contract.md)
4. [`../docs/architecture/server-resolver-boundary.md`](../docs/architecture/server-resolver-boundary.md)
5. [`rules/repo.md`](rules/repo.md)
6. [`plans/roadmap.md`](plans/roadmap.md)
7. [`memory/meta.md`](memory/meta.md)

## Agent-Specific Expectations

- Keep `.agents/*` derivative; do not restate architecture that already lives in `docs/`.
- Use the smallest relevant doc set for the task.
- Do not add, remove, or rewrite tests without explicit user approval; protect the TDD contract and avoid silent test drift.
- Before writing new code, look for an existing implementation in the repo and for a maintained PyPI library that already solves the problem.
- Prefer reuse, simplification, or replacement over parallel implementations that increase codebase size and debt.
- Keep plan files and changelogs aligned with implementation work when the task changes roadmap or milestone scope.
- Respect protected history: plans `01-11` and changelogs `01-11` are append-only.

## High-Value Paths

- `app/main.py`: composition root
- `app/interface/`: API routes and DTOs
- `app/core/`: domain services and ports
- `app/persistence/`: SQLAlchemy adapters and models
- `tests/`: unit and integration coverage
