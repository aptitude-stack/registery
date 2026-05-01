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
- Do not remove or rewrite tests without explicit user approval; protect the TDD contract and avoid silent test drift.
- Before writing new code, look for an existing implementation in the repo and for a maintained PyPI library that already solves the problem.
- Prefer reuse, simplification, or replacement over parallel implementations that increase codebase size and debt.
- Keep plan files and changelogs aligned with implementation work when the task changes roadmap or milestone scope.
- Respect protected history: plans `01-12` and changelogs `01-12` are append-only.

## High-Value Paths

- `app/main.py`: composition root
- `app/interface/`: API routes and DTOs
- `app/core/`: domain services and ports
- `app/persistence/`: SQLAlchemy adapters and models
- `tests/`: unit and integration coverage

## Learned User Preferences

- Do not hardcode HTML, CSS, or other static assets in Python modules; load them from sibling `resource/` directories at import time via `Path(__file__).parent / "resource" / "<file>"`.
- Do not introduce undefined acronyms or initialisms (e.g. invented brand marks like "APR"); only use abbreviations that are documented elsewhere in the codebase.
- Do not install temporary dev dependencies (e.g. `uv add --dev playwright`) for one-off scripts; prefer simple manual verification (open the file in a browser, hit the running endpoint) and keep `pyproject.toml` / `uv.lock` clean.
- Prefer simple, low-friction verification flows; avoid building elaborate browser/Playwright harnesses just to preview HTML.
- For UI design feedback, lean bold and modern over gentle/soft (heavy display type, solid ink rules, strong contrast) when the user pushes back on a design.
- When a single sentence or element is asked to be removed, also remove related decorative scaffolding (orphan CSS, dead JS, unused selectors) rather than leaving it behind.

## Learned Workspace Facts

- Root status page lives at [`app/interface/api/resource/root.html`](../app/interface/api/resource/root.html) and is loaded by [`app/interface/api/root.py`](../app/interface/api/root.py) at import time; the page fetches `/healthz` and `/readyz` live and renders `liveness`, `readiness`, and one row per `ReadinessCheck`.
- `Dockerfile` already does `COPY app ./app`, so any file under `app/` (including `resource/`) ships with the image without packaging changes.
- `app/interface/api/__init__.py` exists, but `app/interface/api/resource/` has no `__init__.py`; load resources by filesystem path, not via `importlib.resources`.
- Standard lint/format invocation for changed Python files: `UV_CACHE_DIR=.uv-cache uv run --extra dev ruff check <path>` and `UV_CACHE_DIR=.uv-cache uv run --extra dev ruff format --check <path>`.
- Quick smoke test for FastAPI routes: instantiate `FastAPI()`, `include_router(...)`, and assert with `TestClient` rather than spinning up the full Docker/DB stack.
- Hooks state lives under `.cursor/hooks/state/`; the continual-learning incremental index is `.cursor/hooks/state/continual-learning-index.json` (separate from the existing `continual-learning.json` hook state).
