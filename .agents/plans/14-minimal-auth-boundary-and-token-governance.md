# Plan 14 - Production Security Baseline and Service Token Governance

## Goal
After `dev` and `prod` are standardized in Plan 13, introduce a small but production-ready security baseline for `Aptitude Registry` that hardens the exposed HTTP surface and replaces raw opaque bearer-token settings with governed service tokens.

## Stack Alignment
- Runtime: Python 3.12+
- API and contracts: FastAPI + Pydantic v2
- Configuration: `pydantic-settings` plus environment overrides or secret-manager injection
- Architecture style: layered boundary between interface, core auth policy, token verification, and deployment security controls

## Scope
- Build the security baseline on top of the explicit `dev|prod` environment model from Plan 13.
- Keep the service token model small and machine-oriented:
  - only `read`, `publish`, and `admin` scopes
  - no end-user accounts or browser session auth
  - `Authorization: Bearer <token_id>.<token_secret>` as the only application auth transport for protected business routes
- Replace raw token-to-scope maps with a governed service-token registry that stores:
  - `token_id`
  - `secret_digest`
  - `scopes`
  - `active`
  - optional `expires_at`
- Keep FastAPI responsible only for extracting bearer credentials from HTTP requests and delegating verification.
- Move token parsing, constant-time secret verification, caller identity construction, revocation/expiry checks, and scope enforcement into a dedicated auth layer outside route dependencies.
- Add a small port/adapter boundary for token lookup so the initial implementation can remain settings-backed while allowing later replacement with a secret manager or database-backed token registry.
- Standardize auth error codes and request handling across publish, discovery, resolution, exact metadata fetch, exact content fetch, lifecycle routes, and any production-protected operational routes.
- Define explicit public-vs-protected surface rules:
  - public: `GET /healthz`, `GET /readyz`
  - production-protected: business routes and operational surfaces that expose internal detail
  - no route should become public by omission
- Keep auth behavior aligned across runtime profiles:
  - `prod`: auth required on all protected routes, no bypass
  - `dev`: same route protection model as `prod`, still no bypass
- Treat test execution as a harness concern:
  - tests that verify production auth and security behavior should run with `APP_ENV=prod`
  - tests may opt into `APP_ENV=dev` only when explicitly verifying local-runtime differences that do not weaken auth
- Add a minimal application-level production hardening baseline:
  - disable or explicitly protect OpenAPI/docs routes in `prod`
  - validate accepted host headers in `prod`
  - keep CORS disabled unless a concrete browser client requires it
  - protect `/metrics` in `prod` at the app or edge boundary
  - enforce upload/request size limits at the edge and validate them in app code where needed
  - define trusted proxy/forwarded-header behavior explicitly for non-local deployments
- Keep auth and security out of the public resource model entirely: no login, token introspection endpoint, token rotation endpoint, OAuth helper routes, or debug-only helper routes.
- Keep the security boundary aligned to the hard-cut API contract and avoid preserving old auth branches for deleted routes.

## Breaking Changes Accepted In This Milestone
- Raw `AUTH_TOKENS_JSON` maps keyed by the full bearer secret are no longer the target production contract.
- Existing local/demo tokens will need to be regenerated in the new `token_id + secret` format.
- `/docs`, `/redoc`, and `/openapi.json` should no longer be assumed available in `prod`.
- `/metrics` should no longer be assumed publicly scrapeable in `prod`.
- Host validation failures and malformed token-format failures become explicit rejected-request paths.

## Out of Scope
- OAuth2 authorization flows, login screens, refresh tokens, or browser session auth.
- JWT issuance, JWKS validation, external identity providers, or token introspection.
- Per-user RBAC, multitenancy, or organization-level authorization models.
- Fine-grained object permissions beyond the existing route-level scopes and governance policy.
- HSTS, custom certificate management inside FastAPI/Uvicorn, or application-managed TLS termination.

## Implementation Guardrails
- Start by checking existing code and infra before adding anything new:
  - `app/core/dependencies.py`
  - `app/core/settings.py`
  - `app/main.py`
  - `app/service_container.py`
  - `app/interface/api/operability.py`
  - current proxy/TLS/deployment guidance already present in the repo
- Reuse or rewrite existing auth wiring instead of layering parallel logic beside it.
- Prefer existing framework primitives first:
  - FastAPI/Starlette `HTTPBearer` and `HTTPAuthorizationCredentials` for HTTP credential extraction
  - `pydantic-settings` for token-registry and production-hardening configuration
  - Starlette middleware for `TrustedHostMiddleware`
  - existing service-container wiring for dependency ownership
- Recommended libraries and primitives for this milestone:
  - keep FastAPI `HTTPBearer` / `HTTPAuthorizationCredentials` as the request-parsing primitive
  - keep `pydantic-settings` as the configuration layer for token governance and production-hardening flags
  - use Starlette `TrustedHostMiddleware` for accepted-host enforcement in `prod`
  - use Python stdlib `secrets` to generate service-token secrets
  - use Python stdlib `hashlib` to persist secret digests instead of raw secrets
  - use Python stdlib `hmac.compare_digest` for constant-time secret verification
  - optionally use `slowapi` only if app-level rate limiting is needed beyond documented edge limits; it is not required for the baseline plan
- Do not add `fastapi-users`, `Authlib`, JWT tooling, password-hashing libraries, or browser-auth/session middleware in this milestone. The requirement is still machine-to-machine service tokens plus baseline HTTP hardening, not user management or human-password auth.

- Avoid inventing application-only protections when the edge should own them:
  - TLS termination belongs at the proxy/load balancer
  - coarse request size limits and rate limiting should be documented and enforced at the edge
  - app code should still validate route-specific upload and token constraints
- Do not weaken security for local convenience:
  - no `dev` bypass
  - no permissive CORS “just in case”
  - no secrets in query parameters
  - no logging of presented token secrets

## Architecture Impact
- Clarifies layer ownership by removing authentication decisions from the FastAPI transport boundary and centralizing them in a dedicated auth service.
- Replaces raw shared-secret maps with a more realistic pre-prod service-token contract without dragging in user-account abstractions.
- Makes production posture explicit at the app boundary by hardening docs exposure, host validation, metrics exposure, request handling, and proxy trust.
- Keeps transport security as an infrastructure concern by terminating TLS at the edge instead of embedding certificate management into the Python application process.

## Production Security Baseline
- Require HTTPS for any non-local environment because bearer service tokens must not traverse public or shared networks over plain HTTP.
- Keep local development on `http://127.0.0.1` unless a specific integration test requires TLS.
- Terminate TLS at an edge proxy or load balancer such as Caddy, Nginx, or a cloud ingress, and proxy to FastAPI/Uvicorn over private internal HTTP.
- Trust forwarded proto/host headers only from configured trusted proxies. Do not blindly trust `X-Forwarded-*` headers from arbitrary clients.
- Disable `/docs`, `/redoc`, and `/openapi.json` in `prod` by default unless an explicit protected operational need re-enables them.
- Use `TrustedHostMiddleware` or an equivalent edge control in `prod` to reject unexpected `Host` headers.
- Keep CORS disabled unless a specific browser-based client is introduced. If a browser client later requires it, use explicit allowlists and no wildcard-with-credentials configuration.
- Protect `/metrics` in `prod` either with app-level `admin` auth or by making it internal-only behind the edge. Do not assume public metrics exposure.
- Enforce strict request and multipart upload size limits:
  - edge-level body limits for all deployments
  - app-level validation for publish bundle size and related multipart constraints before expensive processing
- Treat security-sensitive dependencies as part of the baseline:
  - keep FastAPI, Starlette, and `python-multipart` on patched versions
  - document that multipart parsing remains security-sensitive due to historical DoS issues
- Ensure audit and observability surfaces record only non-secret auth metadata such as `token_id` and scopes, never the presented token secret.

## Deliverables
- Core auth service or policy module that authenticates governed service tokens into a `CallerIdentity`.
- Token lookup port with an initial settings-backed adapter using token ids and secret digests instead of raw bearer secrets.
- Thin FastAPI dependencies that only parse credentials and delegate auth decisions.
- Shared scope-enforcement helpers for `read`, `publish`, and `admin` across the final protected route set.
- Production app-wiring changes for docs exposure, trusted hosts, and protected metrics behavior.
- Environment/security policy note describing expected behavior in `dev` and `prod`.
- Architecture note describing why the service intentionally stays with service tokens instead of OAuth2/JWT at this stage.
- Deployment note describing the required edge pattern: `client -> TLS terminator / request limits / rate limits -> FastAPI`.

## Acceptance Criteria
- Route handlers and FastAPI dependencies no longer contain token lookup or authorization decision logic beyond request parsing and delegation.
- Protected routes require `Authorization: Bearer <token_id>.<token_secret>` in both `dev` and `prod`; there is no bypass mode.
- The app no longer treats full raw bearer secrets as stable configuration keys for the long-term production contract.
- Token verification uses a constant-time comparison path and supports inactive and expired token rejection.
- Auth failures remain deterministic with stable error codes for:
  - missing credentials
  - malformed credentials
  - invalid token id/secret
  - inactive or expired token
  - insufficient scope
- `/docs`, `/redoc`, and `/openapi.json` are disabled or explicitly protected in `prod`.
- `prod` enforces accepted host validation and documents trusted proxy behavior.
- `/metrics` is not treated as publicly open in `prod`.
- The milestone adds no new public HTTP endpoints and does not widen the simple route surface from Plans 07-09.
- No OAuth2, JWT, end-user identity, browser cookie auth, or app-managed TLS concepts are introduced into the runtime flow.
- Non-local deployment guidance requires HTTPS at the edge plus request-size and rate-limit controls appropriate for publish/admin surfaces.
- Logs and audit events never record presented token secrets.

## Test Plan
- Unit tests for auth service success and failure paths:
  - valid token id + secret
  - malformed token format
  - unknown token id
  - wrong secret
  - inactive token
  - expired token
- Unit tests for scope enforcement against `read`, `publish`, and `admin`.
- Interface tests confirming FastAPI dependencies translate auth failures into the expected HTTP responses across the final protected route set.
- Environment-specific tests:
  - `prod` requires valid bearer service tokens
  - `dev` uses the same auth requirements for protected routes
  - public health endpoints stay available without auth in both profiles
- Production-hardening tests:
  - docs/OpenAPI routes are disabled or protected in `prod`
  - invalid `Host` headers are rejected in `prod`
  - `/metrics` matches the chosen production protection posture
  - oversized publish requests or multipart payloads are rejected before expensive processing completes
- Regression tests showing all protected business routes still enforce the same scope semantics after the auth-layer refactor.
- Harness tests confirming production-like auth coverage runs with `APP_ENV=prod` instead of a dedicated `test` runtime profile.
- Deployment smoke tests or documented verification steps confirming:
  - requests arrive with the correct forwarded scheme behind the chosen TLS terminator
  - trusted proxy settings are correct
  - edge limits and scrape/access expectations match the documented production posture

## Assumptions and Defaults
- This milestone intentionally follows environment-profile separation so security rules can depend on explicit runtime profiles without creating new route families.
- The service continues to use one FastAPI app and one settings model, but that settings model now owns both token-governance inputs and production-hardening toggles.
- The service still targets machine-to-machine auth, not user identity.
- Because this is pre-prod, breaking token and operational-surface changes are preferred over preserving convenience semantics that weaken the production baseline.

## Plan 15 Follow-On Note (2026-04-18)
- Plan 15 does not widen the auth model introduced here. Semantic retrieval and
  co-usage ranking remain governed by the same route-level `read` access model
  and existing discovery-policy enforcement.
- Discovery enhancements must not become identity-personalized search behavior
  inside the server. Caller identity may still gate access, but final selection
  and user-specific ranking remain resolver-owned.
- Any credentials needed for embedding generation or aggregate refresh jobs are
  infrastructure/runtime concerns, not new public auth mechanisms, browser-auth
  flows, or endpoint families.
