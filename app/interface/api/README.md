# app.interface.api module

HTTP API routers for the service.

Use [docs/reference/api-contract.md](../../../docs/reference/api-contract.md) as the
canonical HTTP contract for route semantics.

## Purpose

Defines FastAPI routes, request validation, response schemas, and error
translation for the service's public HTTP contract. This package is the thin
adapter layer between FastAPI and core services.

## Key Files

- `health.py`: liveness/readiness endpoints (`/healthz`, `/readyz`).
- `dependencies.py`: FastAPI dependency providers and typed aliases that adapt
  request handlers to the process-scoped service container.
- `discovery.py`: body-based candidate lookup route at `/discovery`.
- `resolution.py`: exact first-degree dependency read route at
  `/resolution/{slug}/{version}`.
- `fetch.py`: identity-level version listing plus exact immutable metadata and
  artifact fetch routes under `/skills/{slug}` and `/skills/{slug}/{version}`.
- `skills.py`: publish and lifecycle-status routes.
- `errors.py`: stable JSON error envelope helpers and FastAPI exception
  handlers.
- `response_docs.py`: shared OpenAPI response fragments reused across route files.
- `skill_api_support_publish.py`: publish request-to-core command translation.
- `skill_api_support_fetch.py`: exact metadata response mapping.
- `skill_api_support_resolution.py`: dependency resolution response mapping.
- `skill_api_support_lifecycle.py`: lifecycle-status response mapping.
- `skill_api_support.py`: compatibility re-export for the split mapper modules.
- `__init__.py`: package marker.

## Route Surface

- `GET /healthz`: process liveness probe.
- `GET /readyz`: dependency readiness probe with a `503` response when the
  service is not ready.
- `POST /discovery`: discovery-only candidate lookup returning ordered slug
  candidates.
- `GET /skills/{slug}`: visible immutable versions for one skill identity.
- `GET /resolution/{slug}/{version}`: direct authored `depends_on`
  declarations for one immutable version.
- `GET /skills/{slug}/{version}`: immutable metadata fetch for one
  exact coordinate.
- `GET /skills/{slug}/{version}/content`: immutable artifact fetch for
  one exact coordinate.
- `POST /skills/{slug}`: immutable skill version publication.
- `PATCH /skills/{slug}/{version}/status`: lifecycle-status transition
  for one immutable version.

## Notes

Routers should stay thin. They validate HTTP input, call a core service, and
translate results into public DTOs without embedding business policy.
Routers that depend on the skill-domain core should import from
`app.core.skills.*` rather than assuming a flat `app.core` module layout.
Health and metrics routes should use `app.observability.*` helpers for runtime
concerns instead of treating logging, readiness, or metrics as skill-domain
core logic.
`errors.py` owns the public error envelope so request validation failures,
policy violations, and explicit API errors share one JSON shape.
The `skill_api_support_*.py` modules are split by API surface so route handlers
reuse mapping code without collecting every conversion function in one file.
`response_docs.py` centralizes repeated OpenAPI response fragments so request
validation and exact-version-not-found responses stay consistent across routes.
`POST /skills/{slug}` requires `intent=create_skill|publish_version`
so the API can distinguish first publication from publication to an existing
skill slug.
`POST /discovery` is candidate generation only and does not choose final
matches, solve dependencies, or plan execution.
`GET /resolution/{slug}/{version}` returns direct authored dependencies only;
it does not expand transitive graphs or select versions for constraints.
The exact fetch routes intentionally separate exact metadata responses from
immutable artifact bytes so metadata reads stay JSON-oriented while exact content
reads preserve cache-friendly artifact delivery headers.
`GET /skills/{slug}` returns a summary list only; callers still use the exact
metadata/content routes for per-version detail.
Publisher-supplied provenance may appear only on publish/exact metadata
responses as advisory data; discovery, resolution, and raw content routes remain
independent of Git, filesystem, or publisher-side state.
