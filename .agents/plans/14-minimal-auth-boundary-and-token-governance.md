# Plan 14 - Minimal Auth Boundary and Token Governance

## Goal
After `dev` and `prod` are standardized in Plan 13, introduce a minimal, maintainable authentication boundary for `Aptitude Registry` that keeps opaque bearer-token auth simple while managing auth mechanisms explicitly by runtime posture.

## Stack Alignment
- Runtime: Python 3.12+
- API and contracts: FastAPI + Pydantic v2
- Configuration: `pydantic-settings` plus environment overrides or secret-manager injection
- Architecture style: layered boundary between interface, core auth policy, and token-source adapter

## Scope
- Build auth on top of the explicit `dev|prod` environment model from Plan 13.
- Keep authentication based on opaque bearer tokens and scope mapping such as `read`, `publish`, and `admin`.
- Keep FastAPI responsible only for extracting bearer credentials from HTTP requests.
- Move token validation, caller identity construction, and scope enforcement into a dedicated auth layer outside route dependencies.
- Add a small port/adapter boundary for token lookup so the initial implementation can remain settings-backed while allowing later replacement with a secret manager or identity adapter.
- Standardize auth error codes and request handling across publish, discovery, resolution, exact metadata fetch, exact content fetch, and lifecycle routes.
- Manage auth mechanisms explicitly by environment:
  - `prod`: auth required, opaque bearer tokens only, no bypass
  - `dev`: may support a controlled bypass mode for local iteration, but only through an explicit separate setting and without changing the public route surface
- Treat test execution as a harness concern:
  - tests that verify real auth behavior should run with `APP_ENV=prod`
  - tests for local shortcuts should opt into `APP_ENV=dev` deliberately
- Keep auth out of the public resource model entirely: no login, token introspection, token rotation, or auth-helper endpoint families.
- Keep the auth boundary aligned to the hard-cut contract and avoid preserving auth branches for deleted routes.

## Out of Scope
- OAuth2 authorization flows, login screens, refresh tokens, or browser session auth.
- JWT issuance, JWKS validation, external identity providers, or token introspection.
- Per-user RBAC, multitenancy, or organization-level authorization models.
- Fine-grained object permissions beyond the existing route-level scopes and governance policy.

## Implementation Guardrails
- Start by checking existing code and infra before adding anything new:
  - `app/core/dependencies.py`
  - `app/core/settings.py`
  - `app/main.py`
  - `app/service_container.py`
  - current proxy/TLS deployment guidance already present in the repo
- Reuse or rewrite existing auth wiring instead of layering new logic beside it.
- Prefer existing framework primitives first:
  - FastAPI/Starlette `HTTPBearer` and `HTTPAuthorizationCredentials` for HTTP credential extraction
  - `pydantic-settings` for token and bypass configuration
  - existing service-container wiring for dependency ownership
- Before writing custom auth plumbing from scratch, assess maintained PyPI options and only adopt one if it clearly reduces complexity without violating scope. Initial libraries to evaluate:
  - [Authlib](https://pypi.org/pypi/Authlib) for broader OAuth/OIDC support if requirements expand
  - [fastapi-users](https://pypi.org/project/fastapi-users/) for full user-management flows if the product later needs end-user auth
- Recommendation for this milestone: do not add a new auth library unless built-in FastAPI/Starlette security primitives prove insufficient. The current requirement is opaque machine bearer tokens, not user accounts or OAuth flows.

## Architecture Impact
- Clarifies layer ownership by removing authentication decisions from the FastAPI transport boundary.
- Builds on explicit environment boundaries instead of mixing environment and auth concerns in one step.
- Creates a clean replacement seam if the service later needs stronger machine-to-machine auth without rewriting route handlers.
- Keeps transport security as an infrastructure concern by terminating TLS at the edge instead of embedding certificate management into the Python application process.

## Transport Security
- Require HTTPS for any non-local environment because opaque bearer tokens must not traverse public or shared networks over plain HTTP.
- Keep local development on `http://127.0.0.1` unless a specific integration test requires TLS.
- Terminate TLS at an edge proxy or load balancer such as Caddy, Nginx, or a cloud ingress, and proxy to FastAPI/Uvicorn over private internal HTTP.
- Do not make FastAPI/Uvicorn the primary certificate termination point except for short-lived demos or constrained internal experiments.
- Trust forwarded proto/host headers only from the configured edge proxy so generated URLs, redirects, and scheme-aware behavior remain correct without opening header-spoofing risk.

## Deliverables
- Core auth service or policy module that authenticates opaque tokens into a `CallerIdentity`.
- Auth token lookup port with an initial settings-backed adapter.
- Thin FastAPI dependencies that only parse credentials and delegate auth decisions.
- Shared scope-enforcement helpers for `read`, `publish`, and `admin` across the final route set.
- Environment-auth policy note describing expected behavior in `dev` and `prod`.
- Architecture note describing why the service intentionally stays with opaque bearer tokens instead of OAuth2/JWT at this stage.
- Deployment note describing the minimal HTTPS pattern: `client -> TLS terminator -> FastAPI`.

## Acceptance Criteria
- Route handlers and FastAPI dependencies no longer contain token lookup or authorization decision logic beyond request parsing and delegation.
- Opaque bearer tokens remain the only supported auth mechanism in `prod`.
- Any optional `dev` bypass changes caller resolution only; it does not create alternate endpoint variants or dev-only helper routes.
- The settings-backed token map can be swapped behind a port without changing route handlers or core policy code.
- Auth failures remain deterministic with stable error codes for missing credentials, invalid tokens, and insufficient scope.
- The auth milestone adds no new public HTTP endpoints and does not widen the simple route surface from Plans 07-09.
- No OAuth2, JWT, or end-user identity concepts are introduced into the public API, configuration model, or runtime flow.
- Non-local deployment guidance requires HTTPS at the edge and does not depend on application-managed TLS certificates.

## Test Plan
- Unit tests for auth service success and failure paths.
- Unit tests for scope enforcement against `read`, `publish`, and `admin`.
- Interface tests confirming FastAPI dependencies translate auth failures into the expected HTTP responses across the final route set.
- Environment-specific auth tests:
  - `prod` requires valid bearer tokens
  - `dev` matches `prod` unless explicit bypass is enabled
  - optional `dev` bypass works only in `dev`
- Regression tests showing all protected routes still enforce the same access semantics after the auth-layer refactor.
- Harness tests confirming production-like auth coverage runs with `APP_ENV=prod` instead of a dedicated `test` runtime profile.
- Deployment smoke test or documented verification step confirming requests arrive with the correct forwarded scheme when running behind the chosen TLS terminator.

## Assumptions and Defaults
- This milestone intentionally follows environment-profile separation so auth rules can depend on explicit runtime profiles.
- There is no current evidence that the service needs a dedicated `test` auth mode distinct from deliberate `dev` or `prod` execution.
- The service continues to use one FastAPI app and one settings model.

## Plan 15 Follow-On Note (2026-04-16)
- Plan 15 does not widen the auth model introduced here. Semantic retrieval and
  co-usage ranking remain governed by the same route-level `read` access model
  and existing discovery-policy enforcement.
- Discovery enhancements must not become identity-personalized search behavior
  inside the server. Caller identity may still gate access, but final selection
  and user-specific ranking remain resolver-owned.
- Any credentials needed for embedding generation or aggregate refresh jobs are
  infrastructure/runtime concerns, not new public auth mechanisms or endpoint
  families.
