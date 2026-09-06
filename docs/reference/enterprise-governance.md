# Enterprise Governance

> Status: canonical reference for namespace ownership, promotion workflow, policy packs, trust evidence, and enterprise visibility.

Enterprise governance is a registry control-plane layer over immutable versions. It does not add resolver/runtime execution behavior and it does not rewrite stored `.tar.zst` artifacts.

## State Model

| State | Owner | Mutability | Purpose |
| --- | --- | --- | --- |
| `lifecycle_status` | admin lifecycle route | mutable | General registry support state: `published`, `deprecated`, or `archived`. |
| `namespace` | admin ownership route | mutable identity ownership | Namespace grant boundary for skill identities. |
| `artifact_origin` | publish input | immutable after publish | Declares `internal`, `imported`, `verified`, or `restricted` origin. |
| `review_state` | review route | mutable | Review workflow: `pending_review`, `approved`, or `rejected`. |
| `promotion_channel` | review route | mutable | Enterprise channel: `dev`, `staging`, or `prod`. |
| `trust_tier` | publish/review route | mutable | Trust classification: `untrusted`, `internal`, or `verified`. |
| `policy_pack_slug` | publish/review route | mutable reference | Optional registry-enforced policy-pack reference. |
| `trust_evidence` | trust-evidence route | append-only | Evidence metadata attached to one immutable version. |

These fields stay independent. Promotion does not imply lifecycle, review does not imply trust, and trust evidence does not imply approval.

## Admin Routes

| Method | Path | Scope | Namespace grant | Purpose |
| --- | --- | --- | --- | --- |
| `POST` | `/admin/organizations` | `admin` | global/admin | Create an organization. |
| `POST` | `/admin/namespaces` | `admin` | global/admin | Create a namespace owned by an organization. |
| `PUT` | `/admin/policy-packs/{slug}` | `admin` | global/admin | Create or update a policy-pack reference. |
| `PATCH` | `/admin/skills/{slug}/ownership` | `admin` | global/admin | Move a skill identity to a namespace. |
| `PATCH` | `/admin/skills/{slug}/{version}/governance` | `review` | namespace `review` | Update review, promotion, trust-tier, or policy-pack state. |
| `POST` | `/admin/skills/{slug}/{version}/trust-evidence` | `review` | namespace `review` | Append trust evidence. |

Global `*` namespace grants are intended for bootstrap and administrative automation, not normal service tokens.

## Publish Defaults

Publish accepts optional `governance.namespace`, `governance.artifact_origin`, and `governance.policy_pack_slug`.

Defaults preserve the existing public catalog behavior:

- omitted namespace defaults to `public`
- `artifact_origin=internal` defaults to `review_state=approved` and `promotion_channel=prod`
- `artifact_origin=imported` defaults to `review_state=pending_review` and `promotion_channel=dev`

Imported artifacts are therefore accepted into the airlock but hidden from production readers until a reviewer approves and promotes them.

## Visibility

The registry applies the same enterprise visibility model to:

- discovery
- version listing
- exact metadata fetch
- exact content fetch
- exact dependency resolution

Normal readers must satisfy all of these checks:

- route-level `read` scope
- namespace `read` grant
- allowed promotion channel
- lifecycle status visible to readers
- `review_state=approved`
- policy-pack rules allow the token or namespace

Reviewers with a namespace `review` grant may inspect non-approved review states in that namespace. Discovery remains candidate-slug only. Resolution remains direct authored `depends_on` only.

## Policy Packs

Policy packs are registry-enforced visibility and promotion references first, not arbitrary runtime policy execution.

Current enforced rules:

| Rule | Meaning |
| --- | --- |
| `visibility: "restricted"` | Requires the caller token id to appear in `allowed_token_ids` or the version namespace to appear in `allowed_namespaces`. |
| `allowed_token_ids` | Token-id allowlist for restricted packs. |
| `allowed_namespaces` | Namespace allowlist for restricted packs. |
| `requires_verified_publisher: true` | Requires current `trust_tier=verified`. |

Rules are stored as `jsonb` so the reference can grow, but only documented rules are enforced.

## Audit Coverage

Enterprise workflow decisions write audit events with redacted actor context and request ids where HTTP request context is available.

Events include:

- `enterprise.organization_created`
- `enterprise.namespace_created`
- `enterprise.policy_pack_upserted`
- `enterprise.skill_ownership_updated`
- `enterprise.version_governance_updated`
- `enterprise.trust_evidence_added`
- `enterprise.version_visibility_denied`

Audit state is the source of truth for post-publish governance history. `version_checksum.digest` is not recomputed for review, promotion, trust-tier, policy-pack, ownership, or trust-evidence changes.

## Persistence alignment

Revision 0013 keeps namespace ownership, policy-pack deletion behavior, trust
evidence, and workflow authorization unchanged. Published metadata lives on its
version; mutable governance changes still refresh searchable governance fields
transactionally and do not recompute historical publication checksums.
