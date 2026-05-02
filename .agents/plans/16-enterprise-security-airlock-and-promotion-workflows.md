# Enterprise Security Airlock and Promotion Workflows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the registry into the enterprise security airlock for agentic skill artifacts: private ownership, artifact intake review, promotion channels, policy-pack visibility, trust evidence, and audit-backed workflow state.

**Architecture:** Extend the existing `GovernancePolicy`, service-token identity, SQLAlchemy repository, and PostgreSQL schema instead of adding a parallel enterprise subsystem. Immutable artifact coordinates stay unchanged; mutable enterprise workflow state controls visibility and eligibility through the same discovery, resolution, metadata, content, and lifecycle read paths. Generic policy engines are deferred until policy complexity proves they are needed; cryptographic verification uses maintained supply-chain libraries instead of handwritten crypto.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL/Neon, existing bearer service-token auth, optional `sigstore` for signature bundle verification, `uv`, Ruff, pytest.

---

## Current Repo Baseline

- Current branch: `feature/16-enterprise-security-airlock-and-promotion-workflows`.
- Current plan file had a title drift: it said "Plan 17" while the roadmap and filename identify this as Plan 16. This rewrite makes Plan 16 the source of truth.
- The live app already has the Plan 14 governance baseline:
  - `app/core/auth.py`: governed service-token authentication with `read`, `publish`, and `admin` scopes.
  - `app/core/governance.py`: lifecycle, trust-tier, provenance, publish policy, discovery/exact-read policy.
  - `app/core/skills/registry.py`: publish and lifecycle mutation orchestration.
  - `app/core/skills/search.py`, `app/core/skills/exact_read.py`, `app/core/skills/resolution.py`: current visibility enforcement.
  - `app/persistence/skill_registry_repository.py`: canonical SQLAlchemy persistence adapter.
  - `alembic/versions/0003_skill_bundle_storage.py`: current migration head.
- The live app does not yet have source files or schema for:
  - organizations
  - private namespaces
  - namespace grants
  - review workflow states
  - promotion channels
  - policy packs
  - trust-evidence rows
  - enterprise visibility over private namespaces and promotion channels

## Non-Goals

- Do not move resolver responsibilities into the registry: no solving, prompt interpretation, lock generation, final skill selection, or execution planning.
- Do not add a runtime gateway, egress control, agent identity issuer, or token-budget enforcement.
- Do not introduce a generic external policy engine in this milestone unless a task explicitly proves the existing policy model cannot express the required workflow.
- Do not rewrite the artifact contract or version identity. Governance changes must not mutate uploaded `.tar.zst` bytes or immutable `slug@version` identity.
- Do not update tests during execution without explicit user approval. This plan includes TDD test steps, but implementation workers must ask before editing tests in this repo.

## Library And Tooling Decision

Use existing code first:

- Keep FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, and PostgreSQL as the core stack.
- Reuse `GovernancePolicy`, `CallerIdentity`, `SkillCatalogRepository`, and the current route support modules.
- Prefer rewriting the current flat governance types and repository projections over appending `enterprise_*` code paths that duplicate visibility logic.

Library scan:

- `pycasbin` is a maintained Python authorization library for ACL/RBAC/ABAC. It is useful once the registry needs user/org/role policy languages, but adding it now would duplicate the small set of deterministic workflow rules already owned by `GovernancePolicy`.
- Oso's legacy open-source Python package is deprecated. Do not add it for new registry authorization work.
- Cedar Python bindings exist, but the currently visible packages are either unofficial or early. Do not make Plan 16 depend on Cedar.
- OPA is a strong general-purpose policy engine, but it is an external policy-decision service/runtime. It belongs in a later gateway or cross-service policy plan, not this data-local registry milestone.
- `sigstore` is appropriate when implementation verifies Sigstore bundles, GitHub Actions identities, or DSSE attestations. Add it only in the trust-evidence verification task, not for simple evidence storage.
- `in-toto` / `in-toto-attestation` are appropriate when validating in-toto or SLSA predicate shapes. Store raw evidence first; add strict predicate validation only if the accepted evidence format requires it.

Recommendation: implement Plan 16 with existing code plus PostgreSQL constraints. Add `sigstore` only if the worker implements actual signature bundle verification in this milestone. Do not add Casbin, Oso, Cedar, or OPA.

## Neon And PostgreSQL Execution Notes

- PostgreSQL remains the authoritative store for registry trust state.
- Use a direct Neon connection for Alembic migrations and migration rehearsal. Do not run schema migrations over a Neon pooled `-pooler` endpoint.
- Runtime traffic may continue using the pooled Neon connection string.
- For production-like migration rehearsals, use a Neon branch or local Dockerized Postgres. Neon branches are isolated copy-on-write clones and are suitable for testing schema changes without affecting the parent production branch.
- Do not depend on database-level RLS in this milestone. The app already has a service-token auth model and must enforce visibility consistently in core/repository code. RLS can be a later defense-in-depth plan once roles and session settings are deliberately designed.

## Target Workflow Semantics

### Namespace Ownership

- Every skill belongs to exactly one namespace.
- Existing rows are backfilled to a `public` namespace owned by a `public` organization.
- A namespace can be `public` or `private`.
- Private namespaces are visible only to:
  - admin callers
  - service tokens granted access to that namespace
  - service tokens that own/review that namespace

### Review State

Use a mutable review state on `skill_versions`:

```python
ReviewState = Literal["imported", "internal", "verified", "restricted", "rejected"]
```

Default:

- `untrusted` third-party publishes enter `imported`.
- `internal` publishes enter `internal`.
- `verified` publishes enter `verified` only when policy requirements pass.

Visibility:

- `rejected` versions are admin-only.
- `imported` versions are visible to admins and namespace reviewers, not default production discovery.
- `restricted` versions require explicit namespace or token grants.
- `internal` and `verified` versions follow namespace visibility plus policy-pack rules.

### Promotion Channels

Use a mutable promotion channel on `skill_versions`:

```python
PromotionChannel = Literal["dev", "staging", "prod"]
```

Rules:

- New versions default to `dev`.
- Promotion from `dev` to `staging` requires review not equal to `rejected`.
- Promotion from `staging` to `prod` requires `review_state in ("internal", "verified")`.
- `prod` discovery must exclude `dev`, `staging`, `imported`, and `rejected` unless the caller is admin or explicitly requests non-prod governance views with admin scope.
- These channels are artifact governance channels, not `APP_ENV` runtime profiles.

### Policy Packs

- A policy pack is a registry-owned reference that stores named visibility rules.
- The first implementation stores structured JSON rules and exposes deterministic app-side evaluation.
- Policy packs are not arbitrary executable policy language.
- Policy pack assignment is mutable version workflow state and must emit audit events.

### Trust Evidence

- Trust evidence rows attach to one immutable skill version.
- Evidence can include Sigstore bundles, in-toto/SLSA predicates, publisher verification references, CI workflow proof, manual review notes, or external ticket IDs.
- Evidence payloads must not store secrets.
- Store evidence payloads as JSONB with a compact normalized summary for filtering.
- If cryptographic verification is implemented, use `sigstore` instead of handwritten certificate or signature validation.

## File Structure

Modify existing files:

- `app/core/governance.py`: rewrite flat lifecycle/trust policy into governance workflow policy while preserving existing public types.
- `app/core/audit_events.py`: add builders for namespace, review, promotion, policy-pack, and trust-evidence events.
- `app/core/ports.py`: extend repository ports with namespace visibility context and enterprise governance mutations.
- `app/core/skills/models.py`: extend skill/version projections with namespace, review, promotion, policy-pack, and trust-evidence summaries.
- `app/core/skills/registry.py`: replace lifecycle-only workflow methods with shared governance mutation methods.
- `app/core/skills/search.py`: enforce enterprise visibility before repository search.
- `app/core/skills/exact_read.py`, `app/core/skills/fetch.py`, `app/core/skills/resolution.py`: enforce namespace/review/promotion/policy-pack visibility for exact reads.
- `app/interface/api/skills.py`: keep publish and lifecycle routes stable; add only minimal governance mutation endpoints that naturally belong to `slug@version`.
- `app/interface/dto/skills_lifecycle.py`: expand lifecycle DTOs or split into `skills_governance.py` if DTO size becomes unwieldy.
- `app/interface/dto/skills_fetch.py`, `app/interface/dto/skills_discovery.py`, `app/interface/dto/skills_resolution.py`: expose workflow state needed by consumers.
- `app/interface/api/skill_api_support_fetch.py`, `app/interface/api/skill_api_support_lifecycle.py`, `app/interface/api/skill_api_support_publish.py`: map new core models without duplicating policy logic.
- `app/persistence/models/skill.py`: add `namespace_fk`.
- `app/persistence/models/skill_version.py`: add `review_state`, `promotion_channel`, `policy_pack_fk`, timestamps.
- `app/persistence/models/skill_search_document.py`: add visibility projection columns.
- `app/persistence/skill_registry_repository.py`: implement visibility context reads and workflow mutations.
- `app/persistence/skill_registry_repository_support.py`: update projection helpers and `SEARCH_CANDIDATES_SQL`.
- `app/service_container.py`: wire any new core services through the existing container.
- `app/main.py`: include any new router if a separate governance router is required.
- `docs/reference/api-contract.md`: document new governance routes and response fields.
- `docs/reference/schema.md`: document the new relational tables and columns.
- `docs/reference/service-token-governance.md`: document namespace grants and admin/reviewer behavior.
- `docs/reference/enterprise-governance.md`: create as the canonical feature reference.
- `docs/changelog/16-enterprise-security-airlock-and-promotion-workflows-changelog.md`: create after implementation.

Create new files:

- `alembic/versions/0004_enterprise_security_airlock.py`
- `app/persistence/models/organization.py`
- `app/persistence/models/namespace.py`
- `app/persistence/models/policy_pack.py`
- `app/persistence/models/trust_evidence.py`
- `app/interface/dto/skills_governance.py` if the existing lifecycle DTO file becomes too broad.
- `tests/unit/test_enterprise_governance.py`
- `tests/unit/test_enterprise_audit_events.py`
- `tests/integration/test_enterprise_governance_endpoints.py`

## Task 1: Approve Test Edits And Lock The First Failing Tests

**Files:**
- Test: `tests/unit/test_enterprise_governance.py`
- Test: `tests/unit/test_enterprise_audit_events.py`

- [ ] **Step 1: Ask for explicit approval before editing tests**

Say:

```text
This repo has a TDD guardrail: I need explicit approval before adding or rewriting tests. Plan 16 requires new tests for enterprise governance. Approve test edits for this implementation?
```

Expected: user approves test edits before implementation continues.

- [ ] **Step 2: Write failing governance workflow tests**

Create `tests/unit/test_enterprise_governance.py` with tests for:

```python
from app.core.governance import (
    CallerIdentity,
    GovernancePolicy,
    GovernanceWorkflowState,
    NamespaceAccess,
    PolicyViolation,
    SkillGovernanceInput,
    build_default_policy_profile,
)


def test_imported_dev_artifact_is_hidden_from_plain_reader() -> None:
    policy = GovernancePolicy(profile=build_default_policy_profile())
    caller = CallerIdentity(token_id="reader-token", scopes=frozenset({"read"}))
    workflow = GovernanceWorkflowState(
        namespace_slug="acme-private",
        namespace_visibility="private",
        review_state="imported",
        promotion_channel="dev",
        policy_pack_slug=None,
        trust_tier="untrusted",
    )
    access = NamespaceAccess(
        caller_token_id="reader-token",
        readable_namespace_slugs=frozenset(),
        reviewable_namespace_slugs=frozenset(),
        owned_namespace_slugs=frozenset(),
    )

    assert not policy.is_enterprise_visible(
        caller=caller,
        workflow=workflow,
        namespace_access=access,
        requested_channel="prod",
    )
```

```python
def test_prod_promotion_requires_reviewed_artifact() -> None:
    policy = GovernancePolicy(profile=build_default_policy_profile())
    caller = CallerIdentity(token_id="admin-token", scopes=frozenset({"admin"}))

    try:
        policy.evaluate_promotion(
            caller=caller,
            current_review_state="imported",
            current_channel="staging",
            next_channel="prod",
        )
    except PolicyViolation as exc:
        assert exc.code == "POLICY_PROMOTION_FORBIDDEN"
    else:
        raise AssertionError("expected imported artifact promotion to prod to fail")
```

- [ ] **Step 3: Write failing audit-event tests**

Create `tests/unit/test_enterprise_audit_events.py` with tests for:

```python
from app.core.audit_events import build_promotion_audit_event
from app.core.governance import CallerIdentity


def test_promotion_audit_event_redacts_secret_material() -> None:
    event = build_promotion_audit_event(
        caller=CallerIdentity(token_id="admin-token", scopes=frozenset({"admin"})),
        slug="python.secure",
        version="1.0.0",
        previous_channel="staging",
        promotion_channel="prod",
        review_state="verified",
        policy_profile="default",
        outcome="allowed",
        note="approved for prod",
    )

    assert event.event_type == "skill_version.promotion.updated"
    assert event.payload is not None
    assert event.payload["actor_token_id"] == "admin-token"
    assert "secret" not in str(event.payload).lower()
```

- [ ] **Step 4: Run the focused tests and confirm failure**

Run:

```bash
uv run pytest tests/unit/test_enterprise_governance.py tests/unit/test_enterprise_audit_events.py -q
```

Expected: FAIL because `GovernanceWorkflowState`, `NamespaceAccess`, `is_enterprise_visible`, `evaluate_promotion`, and `build_promotion_audit_event` do not exist.

## Task 2: Rewrite Governance Policy Around Workflow State

**Files:**
- Modify: `app/core/governance.py`
- Test: `tests/unit/test_enterprise_governance.py`

- [ ] **Step 1: Add the workflow types to `app/core/governance.py`**

Add these types near the current lifecycle/trust definitions:

```python
ReviewState = Literal["imported", "internal", "verified", "restricted", "rejected"]
PromotionChannel = Literal["dev", "staging", "prod"]
NamespaceVisibility = Literal["public", "private"]
NamespaceRole = Literal["reader", "reviewer", "owner"]

ALL_REVIEW_STATES: tuple[ReviewState, ...] = (
    "imported",
    "internal",
    "verified",
    "restricted",
    "rejected",
)
ALL_PROMOTION_CHANNELS: tuple[PromotionChannel, ...] = ("dev", "staging", "prod")
ALL_NAMESPACE_VISIBILITIES: tuple[NamespaceVisibility, ...] = ("public", "private")
```

Add:

```python
@dataclass(frozen=True, slots=True)
class NamespaceAccess:
    """Namespace grants available to one authenticated service token."""

    caller_token_id: str
    readable_namespace_slugs: frozenset[str]
    reviewable_namespace_slugs: frozenset[str]
    owned_namespace_slugs: frozenset[str]

    def can_read(self, namespace_slug: str) -> bool:
        return namespace_slug in self.readable_namespace_slugs or self.can_review(namespace_slug)

    def can_review(self, namespace_slug: str) -> bool:
        return namespace_slug in self.reviewable_namespace_slugs or self.can_own(namespace_slug)

    def can_own(self, namespace_slug: str) -> bool:
        return namespace_slug in self.owned_namespace_slugs


@dataclass(frozen=True, slots=True)
class GovernanceWorkflowState:
    """Mutable enterprise workflow state attached to one immutable skill version."""

    namespace_slug: str
    namespace_visibility: NamespaceVisibility
    review_state: ReviewState
    promotion_channel: PromotionChannel
    policy_pack_slug: str | None
    trust_tier: TrustTier
```

- [ ] **Step 2: Add policy methods without duplicating route logic**

Add methods to `GovernancePolicy`:

```python
def evaluate_review_transition(
    self,
    *,
    caller: CallerIdentity,
    namespace_access: NamespaceAccess,
    namespace_slug: str,
    current_review_state: ReviewState,
    next_review_state: ReviewState,
) -> None:
    if not caller.has_scope("admin") and not namespace_access.can_review(namespace_slug):
        raise PolicyViolation(
            code="POLICY_REVIEW_FORBIDDEN",
            message="Caller is not allowed to review this namespace.",
            details={"required_scope": "admin", "namespace_slug": namespace_slug},
        )
    if current_review_state == "rejected" and next_review_state != "imported":
        raise PolicyViolation(
            code="POLICY_REVIEW_TRANSITION_FORBIDDEN",
            message="Rejected artifacts must be reopened before another review state is assigned.",
            details={
                "current_review_state": current_review_state,
                "next_review_state": next_review_state,
            },
        )

def evaluate_promotion(
    self,
    *,
    caller: CallerIdentity,
    current_review_state: ReviewState,
    current_channel: PromotionChannel,
    next_channel: PromotionChannel,
) -> None:
    if not caller.has_scope("admin"):
        raise PolicyViolation(
            code="POLICY_PROMOTION_FORBIDDEN",
            message="Caller is not allowed to promote artifacts.",
            details={"required_scope": "admin"},
        )
    allowed_targets: dict[PromotionChannel, tuple[PromotionChannel, ...]] = {
        "dev": ("staging",),
        "staging": ("prod",),
        "prod": ("staging",),
    }
    if next_channel not in allowed_targets[current_channel]:
        raise PolicyViolation(
            code="POLICY_PROMOTION_FORBIDDEN",
            message="The requested promotion transition is not allowed.",
            details={
                "current_channel": current_channel,
                "next_channel": next_channel,
            },
        )
    if next_channel == "prod" and current_review_state not in ("internal", "verified"):
        raise PolicyViolation(
            code="POLICY_PROMOTION_FORBIDDEN",
            message="Production promotion requires internal or verified review state.",
            details={"review_state": current_review_state},
        )

def is_enterprise_visible(
    self,
    *,
    caller: CallerIdentity,
    workflow: GovernanceWorkflowState,
    namespace_access: NamespaceAccess,
    requested_channel: PromotionChannel,
) -> bool:
    if caller.has_scope("admin"):
        return True
    if workflow.namespace_visibility == "private" and not namespace_access.can_read(
        workflow.namespace_slug
    ):
        return False
    if workflow.review_state == "rejected":
        return False
    if workflow.review_state == "imported" and not namespace_access.can_review(
        workflow.namespace_slug
    ):
        return False
    if workflow.review_state == "restricted" and not namespace_access.can_read(
        workflow.namespace_slug
    ):
        return False
    return workflow.promotion_channel == requested_channel
```

- [ ] **Step 3: Run focused unit tests**

Run:

```bash
uv run pytest tests/unit/test_enterprise_governance.py -q
```

Expected: governance tests pass or fail only on missing next-task code.

## Task 3: Add Audit Events For Enterprise Decisions

**Files:**
- Modify: `app/core/audit_events.py`
- Test: `tests/unit/test_enterprise_audit_events.py`

- [ ] **Step 1: Add explicit audit builders**

Add builders for:

```python
def build_namespace_grant_audit_event(
    *,
    caller: CallerIdentity,
    namespace_slug: str,
    grantee_token_id: str,
    role: NamespaceRole,
    outcome: AuditOutcome,
    reason_code: str | None = None,
) -> AuditEventRecord:
    """Build one namespace grant audit event."""

def build_review_audit_event(
    *,
    caller: CallerIdentity,
    slug: str,
    version: str,
    previous_review_state: ReviewState,
    review_state: ReviewState,
    policy_profile: str,
    outcome: AuditOutcome,
    note: str | None = None,
    reason_code: str | None = None,
) -> AuditEventRecord:
    """Build one review-state audit event."""

def build_promotion_audit_event(
    *,
    caller: CallerIdentity,
    slug: str,
    version: str,
    previous_channel: PromotionChannel,
    promotion_channel: PromotionChannel,
    review_state: ReviewState,
    policy_profile: str,
    outcome: AuditOutcome,
    note: str | None = None,
    reason_code: str | None = None,
) -> AuditEventRecord:
    """Build one promotion audit event."""

def build_policy_pack_assignment_audit_event(
    *,
    caller: CallerIdentity,
    slug: str,
    version: str,
    previous_policy_pack_slug: str | None,
    policy_pack_slug: str | None,
    outcome: AuditOutcome,
    reason_code: str | None = None,
) -> AuditEventRecord:
    """Build one policy-pack assignment audit event."""

def build_trust_evidence_audit_event(
    *,
    caller: CallerIdentity,
    slug: str,
    version: str,
    evidence_type: str,
    verification_status: str,
    outcome: AuditOutcome,
    reason_code: str | None = None,
) -> AuditEventRecord:
    """Build one trust-evidence audit event."""
```

Use this shape for promotion:

```python
def build_promotion_audit_event(
    *,
    caller: CallerIdentity,
    slug: str,
    version: str,
    previous_channel: PromotionChannel,
    promotion_channel: PromotionChannel,
    review_state: ReviewState,
    policy_profile: str,
    outcome: AuditOutcome,
    note: str | None = None,
    reason_code: str | None = None,
) -> AuditEventRecord:
    payload: dict[str, object] = {
        "actor_token_id": caller.token_id,
        "actor_scopes": sorted(caller.scopes),
        "slug": slug,
        "version": version,
        "previous_channel": previous_channel,
        "promotion_channel": promotion_channel,
        "review_state": review_state,
        "policy_profile": policy_profile,
        "outcome": outcome,
    }
    if note is not None:
        payload["note"] = note
    if reason_code is not None:
        payload["reason_code"] = reason_code
    return AuditEventRecord(event_type="skill_version.promotion.updated", payload=payload)
```

- [ ] **Step 2: Run focused audit tests**

Run:

```bash
uv run pytest tests/unit/test_enterprise_audit_events.py -q
```

Expected: audit tests pass.

## Task 4: Add PostgreSQL Schema For Namespaces And Workflow State

**Files:**
- Create: `alembic/versions/0004_enterprise_security_airlock.py`
- Create: `app/persistence/models/organization.py`
- Create: `app/persistence/models/namespace.py`
- Create: `app/persistence/models/policy_pack.py`
- Create: `app/persistence/models/trust_evidence.py`
- Modify: `app/persistence/models/skill.py`
- Modify: `app/persistence/models/skill_version.py`
- Modify: `app/persistence/models/skill_search_document.py`
- Modify: `app/persistence/models/__init__.py`
- Test: `tests/integration/test_migrations.py`

- [ ] **Step 1: Write the migration**

Migration must:

```python
revision = "0004_enterprise_security_airlock"
down_revision = "0003_skill_bundle_storage"
```

Create:

```sql
organizations(id, slug, display_name, created_at)
namespaces(id, slug, organization_fk, visibility, created_at)
namespace_service_token_grants(namespace_fk, token_id, role, created_at)
policy_packs(id, slug, display_name, rules_json, active, created_by_token_id, created_at)
trust_evidence(id, skill_version_fk, evidence_type, subject_digest, issuer, identity, verification_status, payload_json, created_at)
```

Backfill:

```sql
INSERT INTO organizations (slug, display_name) VALUES ('public', 'Public');
INSERT INTO namespaces (slug, organization_fk, visibility)
SELECT 'public', organizations.id, 'public'
FROM organizations
WHERE organizations.slug = 'public';
```

Add:

```sql
ALTER TABLE skills ADD COLUMN namespace_fk bigint;
UPDATE skills SET namespace_fk = (SELECT id FROM namespaces WHERE slug = 'public');
ALTER TABLE skills ALTER COLUMN namespace_fk SET NOT NULL;
ALTER TABLE skills ADD CONSTRAINT fk_skills_namespace_fk FOREIGN KEY (namespace_fk) REFERENCES namespaces(id) ON DELETE RESTRICT;

ALTER TABLE skill_versions ADD COLUMN review_state text NOT NULL DEFAULT 'imported';
ALTER TABLE skill_versions ADD COLUMN promotion_channel text NOT NULL DEFAULT 'dev';
ALTER TABLE skill_versions ADD COLUMN policy_pack_fk bigint NULL REFERENCES policy_packs(id) ON DELETE SET NULL;
ALTER TABLE skill_versions ADD COLUMN review_changed_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE skill_versions ADD COLUMN promoted_at timestamptz NULL;
```

Add check constraints for all enum-like fields.

- [ ] **Step 2: Add ORM models**

Use SQLAlchemy typed `Mapped[...]` models matching the migration. Use `JSONB` for `rules_json` and `payload_json`.

- [ ] **Step 3: Rehearse migration**

Run locally:

```bash
uv run alembic upgrade head
uv run alembic downgrade 0003_skill_bundle_storage
uv run alembic upgrade head
```

Expected: all commands complete without schema errors.

For Neon rehearsal, use a direct non-pooled migration connection and a branch, not the runtime pooled endpoint.

## Task 5: Extend Repository Ports And Projections

**Files:**
- Modify: `app/core/ports.py`
- Modify: `app/core/skills/models.py`
- Modify: `app/persistence/skill_registry_repository.py`
- Modify: `app/persistence/skill_registry_repository_support.py`

- [ ] **Step 1: Add port dataclasses**

Add:

```python
@dataclass(frozen=True, slots=True)
class NamespaceAccessRecord:
    caller_token_id: str
    readable_namespace_slugs: frozenset[str]
    reviewable_namespace_slugs: frozenset[str]
    owned_namespace_slugs: frozenset[str]


@dataclass(frozen=True, slots=True)
class GovernanceWorkflowRecord:
    slug: str
    version: str
    namespace_slug: str
    namespace_visibility: NamespaceVisibility
    review_state: ReviewState
    promotion_channel: PromotionChannel
    policy_pack_slug: str | None
    trust_tier: TrustTier
```

Extend `SkillCatalogRepository` with:

```python
def get_namespace_access(self, *, token_id: str) -> NamespaceAccessRecord:
    """Return namespace grants available to a service token."""

def update_version_review_state(
    self,
    *,
    slug: str,
    version: str,
    review_state: ReviewState,
    audit_events: tuple[AuditEventRecord, ...] = (),
) -> SkillVersionGovernanceUpdate | None:
    """Update review state and emit audit events atomically."""

def update_version_promotion_channel(
    self,
    *,
    slug: str,
    version: str,
    promotion_channel: PromotionChannel,
    audit_events: tuple[AuditEventRecord, ...] = (),
) -> SkillVersionGovernanceUpdate | None:
    """Update promotion channel and emit audit events atomically."""

def assign_policy_pack(
    self,
    *,
    slug: str,
    version: str,
    policy_pack_slug: str | None,
    audit_events: tuple[AuditEventRecord, ...] = (),
) -> SkillVersionGovernanceUpdate | None:
    """Assign a policy pack and emit audit events atomically."""

def add_trust_evidence(
    self,
    *,
    slug: str,
    version: str,
    evidence: TrustEvidenceInput,
    audit_events: tuple[AuditEventRecord, ...] = (),
) -> TrustEvidenceSummary:
    """Attach trust evidence to one immutable version and emit audit events atomically."""
```

- [ ] **Step 2: Update projection helpers**

Ensure `SkillVersionDetail`, `SkillVersionListEntry`, `SkillContentRecord`, `SkillRelationshipSource`, and search candidates carry enough workflow state for `GovernancePolicy` to make one decision.

- [ ] **Step 3: Keep SQL visibility centralized**

Update `SEARCH_CANDIDATES_SQL` to filter by:

- lifecycle status
- trust tier
- namespace visibility or namespace grant
- review state
- promotion channel
- policy-pack visibility once implemented

Do not copy this SQL into route handlers.

## Task 6: Implement Governance Mutation Service Methods

**Files:**
- Modify: `app/core/skills/registry.py`
- Modify: `app/service_container.py`

- [ ] **Step 1: Add review mutation**

Add a service method:

```python
def update_version_review_state(
    self,
    *,
    caller: CallerIdentity,
    slug: str,
    version: str,
    review_state: ReviewState,
    note: str | None = None,
) -> SkillVersionGovernanceUpdate:
    stored = self._repository.get_version_detail(slug=slug, version=version)
    if stored is None:
        raise SkillVersionNotFoundError(slug=slug, version=version)
    namespace_access = self._repository.get_namespace_access(token_id=caller.token_id)
    self._governance_policy.evaluate_review_transition(
        caller=caller,
        namespace_access=namespace_access.to_domain(),
        namespace_slug=stored.namespace_slug,
        current_review_state=stored.review_state,
        next_review_state=review_state,
    )
    updated = self._repository.update_version_review_state(
        slug=slug,
        version=version,
        review_state=review_state,
        audit_events=(
            build_review_audit_event(
                caller=caller,
                slug=slug,
                version=version,
                previous_review_state=stored.review_state,
                review_state=review_state,
                policy_profile=self._governance_policy.profile_name,
                outcome="allowed",
                note=note,
            ),
        ),
    )
    if updated is None:
        raise SkillVersionNotFoundError(slug=slug, version=version)
    return updated
```

- [ ] **Step 2: Add promotion mutation**

Use `GovernancePolicy.evaluate_promotion` before persistence. Emit denied and allowed audit events like publish and lifecycle already do.

- [ ] **Step 3: Add policy-pack assignment**

Require admin scope for first implementation. Keep policy-pack evaluation deterministic and data-local.

- [ ] **Step 4: Add trust-evidence attachment**

Require admin scope or namespace reviewer access. Store evidence after validation. If verifying Sigstore bundles in this task, add `sigstore` with `uv add sigstore` and use its verification APIs rather than handwritten cryptography.

## Task 7: Add FastAPI Governance DTOs And Routes

**Files:**
- Modify: `app/interface/api/skills.py`
- Create or modify: `app/interface/dto/skills_governance.py`
- Modify: `app/interface/dto/examples.py`
- Modify: `app/interface/api/response_docs.py` only if shared response docs need new examples.

- [ ] **Step 1: Define request and response DTOs with `extra="forbid"`**

Create DTOs:

```python
class SkillVersionReviewStateUpdateRequest(BaseModel):
    review_state: ReviewState
    note: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")


class SkillVersionPromotionUpdateRequest(BaseModel):
    promotion_channel: PromotionChannel
    note: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")
```

- [ ] **Step 2: Add routes with existing dependency aliases**

Use `AdminCallerDep` where the action is admin-only. Use `Annotated` for path parameters.

Routes:

```text
PATCH /skills/{slug}/{version}/review
PATCH /skills/{slug}/{version}/promotion
PATCH /skills/{slug}/{version}/policy-pack
POST /skills/{slug}/{version}/trust-evidence
```

Keep one HTTP operation per function.

- [ ] **Step 3: Keep errors stable**

Map domain failures through `error_response` and existing `PolicyViolation` handling. Do not return raw exceptions.

## Task 8: Enforce Enterprise Visibility Across All Read Paths

**Files:**
- Modify: `app/core/skills/search.py`
- Modify: `app/core/skills/exact_read.py`
- Modify: `app/core/skills/fetch.py`
- Modify: `app/core/skills/resolution.py`
- Modify: `app/persistence/skill_registry_repository_support.py`

- [ ] **Step 1: Discovery**

Discovery must only return versions visible under:

```text
namespace + lifecycle + trust_tier + review_state + promotion_channel + policy_pack
```

Default discovery channel is `prod` for non-admin callers.

- [ ] **Step 2: Exact metadata and content reads**

Exact reads must reject private/rejected/non-promoted artifacts unless the caller has admin or namespace grant.

- [ ] **Step 3: Resolution reads**

Resolution must preserve the current server boundary: exact first-degree authored dependency reads only. Hidden dependency targets must remain hidden rather than becoming solver decisions.

## Task 9: Add Integration Tests After Approval

**Files:**
- Test: `tests/integration/test_enterprise_governance_endpoints.py`
- Test: `tests/integration/test_skill_registry_endpoints.py`

- [ ] **Step 1: Confirm test-edit approval still applies**

If approval in Task 1 was only for unit tests, ask again before editing integration tests.

- [ ] **Step 2: Cover private namespace visibility**

Test:

- admin creates/grants a private namespace
- publisher publishes into that namespace
- ungranted reader cannot discover or exact-read it
- granted reader can exact-read it when review/promotion policy allows

- [ ] **Step 3: Cover review and promotion**

Test:

- imported `dev` artifact is hidden from production discovery
- admin moves it to `internal` or `verified`
- admin promotes `dev -> staging -> prod`
- production discovery returns it only after eligible promotion

- [ ] **Step 4: Cover audit persistence**

Assert audit events exist for review, promotion, policy-pack assignment, and trust evidence.

## Task 10: Update Canonical Docs And Changelog

**Files:**
- Create: `docs/reference/enterprise-governance.md`
- Modify: `docs/reference/api-contract.md`
- Modify: `docs/reference/schema.md`
- Modify: `docs/reference/service-token-governance.md`
- Create: `docs/changelog/16-enterprise-security-airlock-and-promotion-workflows-changelog.md`

- [ ] **Step 1: Document the enterprise governance model**

Include:

- namespace ownership
- namespace service-token grants
- review states
- promotion channels
- policy packs
- trust evidence
- audit events
- route list
- non-goals and resolver boundary

- [ ] **Step 2: Update schema reference**

Document every new table/column and whether it is immutable or mutable workflow state.

- [ ] **Step 3: Update API contract**

Document request/response bodies and stable error codes:

```text
POLICY_REVIEW_FORBIDDEN
POLICY_REVIEW_TRANSITION_FORBIDDEN
POLICY_PROMOTION_FORBIDDEN
POLICY_NAMESPACE_VISIBILITY_FORBIDDEN
POLICY_PACK_FORBIDDEN
TRUST_EVIDENCE_INVALID
```

- [ ] **Step 4: Write the milestone changelog**

Use the changelog-writer skill. Include an architecture snapshot, runtime flow, schema reference, and verification notes.

## Task 11: Verification

**Files:**
- No source edits unless verification exposes a bug.

- [ ] **Step 1: Run focused unit tests**

Run:

```bash
uv run pytest tests/unit/test_enterprise_governance.py tests/unit/test_enterprise_audit_events.py -q
```

Expected: PASS.

- [ ] **Step 2: Run focused integration tests**

Run:

```bash
uv run pytest tests/integration/test_enterprise_governance_endpoints.py tests/integration/test_skill_registry_endpoints.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full repo quality gate**

Run:

```bash
uv run ruff check app tests
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 4: Rehearse migration against production-like Postgres**

Use local Docker Postgres or a Neon branch. For Neon, use the direct migration URL.

Run:

```bash
uv run alembic upgrade head
uv run alembic downgrade 0003_skill_bundle_storage
uv run alembic upgrade head
```

Expected: PASS without pooled-connection migration errors.

## Definition Of Done

- Plan title and roadmap numbering agree: this is Plan 16.
- Enterprise governance extends the existing core/repository seams rather than creating a duplicate policy subsystem.
- Existing immutable artifact coordinates and bundle bytes remain unchanged.
- Private namespace ownership and service-token grants work.
- Review state and promotion channel are enforced across discovery, resolution, metadata exact read, and content exact read.
- Policy-pack assignment is stored, audited, and enforced for first-pass visibility rules.
- Trust evidence is stored without secrets; Sigstore verification uses the maintained `sigstore` library if cryptographic verification is included.
- Every namespace, review, promotion, policy-pack, and trust-evidence decision emits audit evidence.
- Canonical docs and milestone changelog describe the live implementation.
- Verification commands pass.
