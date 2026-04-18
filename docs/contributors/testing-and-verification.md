# Testing And Verification

Use this guide when deciding what to run before calling work complete.

## Default Commands

```bash
make quality
make test
```

For doc and contract sync work, the focused guardrails are:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest \
  tests/unit/test_public_contract_docs.py \
  tests/unit/test_api_contract_examples.py -q
```

## What Counts As Verification

- Doc-only changes: link/reference sweep plus manual review of the affected entrypoints.
- Behavior changes: relevant unit or integration coverage plus the default command set when feasible.
- Contract changes: update the canonical docs and run the tests that cover route surface, OpenAPI shape, and affected DTOs.
- Operability changes: verify the relevant Prometheus, Loki, Grafana, or smoke-test assets.

## Determinism Checks

When a change touches discovery ordering, exact fetch semantics, lifecycle visibility, or dependency-selector reads:

- verify stable ordering and tie-break assumptions
- verify no new hidden route aliases or compatibility surfaces were introduced
- verify discovery remains body-free and exact fetch remains coordinate-based

## Docs Sync Rule

If behavior changes, update the canonical documentation in the same change. Do not leave current implementation ahead of `docs/architecture/*` or `docs/reference/*`.
