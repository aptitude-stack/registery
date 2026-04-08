# Module Guide

This is the shortest useful map from architecture to the actual package tree under `app/`.

## Top-Level Ownership

- `app/interface/`: FastAPI routes, DTOs, validation, auth, and HTTP error mapping. Must not reach into persistence directly.
- `app/core/`: domain services, ports, governance, fetch, discovery, and lifecycle behavior. Owns business rules.
- `app/intelligence/`: pure search and ranking support logic. Supports discovery but does not turn the registry into a resolver.
- `app/persistence/`: SQLAlchemy models, repositories, and storage projections. Implements core ports.
- `app/audit/`: audit recording and audit-facing storage logic.
- `app/observability/`: metrics, logging, request correlation, and telemetry helpers.

## Practical Reading Order

1. [`../../app/README.md`](../../app/README.md)
2. [`../../app/interface/README.md`](../../app/interface/README.md)
3. [`../../app/core/README.md`](../../app/core/README.md)
4. [`../../app/persistence/README.md`](../../app/persistence/README.md)

## Boundary Reminders

- Interface must not import persistence internals.
- Core must not import persistence internals directly.
- Persistence exists to support the canonical registry contract, not to define it.
