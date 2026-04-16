# Plan 13 - Environment Profiles and Runtime Separation

## Summary
Standardize `dev` and `prod` as the only explicit runtime profiles before any auth-boundary refactor. This milestone defines how the same FastAPI service is configured and operated across local and deployed environments while keeping the public endpoint surface unchanged and simple.

## Key Changes
- Add explicit environment/profile settings in `app/core/settings.py`:
  - `APP_ENV`: `dev | prod`
  - keep one env-driven settings model; do not introduce separate applications or per-environment forks
  - default `APP_ENV` remains `dev`
- Define environment intent and runtime expectations:
  - `dev`: fast local iteration
  - `prod`: deployment profile for real traffic
- Treat test execution as a harness concern, not a runtime profile:
  - tests may boot the app under `APP_ENV=prod` to verify production auth behavior
  - tests may boot the app under `APP_ENV=dev` only when explicitly validating local-development behavior
- Keep environment handling runtime-only:
  - route names, route count, prefixes, request shapes, and response shapes remain identical across both environments
  - no `dev`/`prod`-specific endpoint variants or helper routes
- Add explicit runner guidance in `Makefile` and docs:
  - `make run`: `APP_ENV=dev`
  - production docs specify `APP_ENV=prod`
- Standardize non-auth environment behavior as needed:
  - config validation
  - startup defaults
  - logging and debug posture
  - dependency wiring expectations
  - migration and deployment guidance
- Do not redesign auth in this milestone beyond the minimum configuration plumbing needed so the next milestone can manage auth cleanly in `dev` and `prod`.

## Implementation Guardrails
- Start by checking existing code and infra before adding anything new:
  - `app/core/settings.py`
  - `app/main.py`
  - `app/core/dependencies.py`
  - `Makefile`
  - deployment and proxy docs/config already present in the repo
- Reuse or rewrite existing environment/configuration wiring instead of creating parallel abstractions.
- Prefer existing repo dependencies first:
  - `pydantic-settings` for validated runtime settings
  - existing FastAPI app/lifespan wiring
  - existing Make/Docker/test harness conventions
- Do not introduce a new environment/profile library unless the current stack cannot express the required `dev|prod` behavior cleanly.

## Public Interfaces and Configuration
- New or standardized environment variable:
  - `APP_ENV=dev|prod`
- Behavioral contract:
  - no HTTP API shape changes to the hard-cut public contract
  - both environments expose the same public endpoint surface
  - environment choice changes configuration and runtime posture, not the registry contract

## Acceptance Criteria
- `dev` and `prod` are explicit, validated runtime profiles.
- The same public route surface is exposed in both environments.
- Environment-profile work does not add auth endpoints, debug endpoints, or alternate route variants.
- Test execution is no longer modeled as a distinct runtime profile.
- The milestone leaves a clear foundation for the next plan to manage auth mechanisms in `dev` and `prod` without revisiting environment structure.

## Test Plan
- Unit tests for settings validation:
  - `APP_ENV=dev` is accepted
  - `APP_ENV=prod` is accepted
  - invalid environment values fail fast
- Startup/config tests:
  - each environment loads the expected runtime profile and defaults
  - environment selection does not alter route registration
- Regression tests:
  - existing API tests continue to target the same endpoint surface regardless of environment
  - no governance or route-shape changes occur solely because `APP_ENV` changes
  - tests that need production-like behavior explicitly run with `APP_ENV=prod`

## Assumptions and Defaults
- This milestone is intentionally placed before auth hardening so environment boundaries are explicit first.
- There is no current evidence that `test` needs its own runtime semantics.
- CI is not a runtime profile; it is an execution environment that selects `dev` or `prod` behavior intentionally.
- There is no separate `staging` profile in this milestone; staging should use `prod` semantics unless a later plan introduces a third profile for a concrete reason.
- The repo keeps one FastAPI app and one settings model; environment behavior is controlled by validated settings and runner commands, not separate codebases.

## Plan 15 Follow-On Note (2026-04-16)
- Plan 15 inherits the same `dev` and `prod` profile model; semantic indexing,
  embedding-provider configuration, co-usage aggregation jobs, and feature
  flags must fit inside these existing runtime profiles rather than introducing
  search-specific environments.
- Any future semantic-search configuration should remain environment-scoped
  settings only. It must not create route variants, separate apps, or
  profile-specific discovery contracts.
