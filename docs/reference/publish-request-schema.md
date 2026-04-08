# Publish Endpoint Schema

Live publish contract for `Aptitude Registry`.

This document describes the live publish request shape used by the repository's server code. It is based on the current route and DTOs, not older historical variants.

Canonical sources:

- `app/interface/api/skills.py`
- `app/interface/dto/skills_publish.py`
- `app/interface/validation.py`
- `app/core/governance.py`

## Endpoint

- Method: `POST`
- Path: `/skills/{slug}`
- Required auth scope: `publish`
- Required header: `Authorization: Bearer <token>`

## Path Parameter

### `slug`

- Required: yes
- Type: `string`
- Pattern: `^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,127})$`
- Meaning: stable public skill identifier

Examples:

- `python.lint`
- `acme_internal.skill-01`

## Request Body

Content type:

- `application/json`

Top-level shape:

```json
{
  "intent": "create_skill",
  "version": "1.2.3",
  "content": {
    "raw_markdown": "# Python Lint\n\nLint Python files consistently.\n"
  },
  "metadata": {
    "name": "Python Lint",
    "description": "Linting skill",
    "tags": ["python", "lint"],
    "inputs_schema": {"type": "object"},
    "outputs_schema": {"type": "object"},
    "token_estimate": 128,
    "maturity_score": 0.9,
    "security_score": 0.95
  },
  "governance": {
    "trust_tier": "internal",
    "provenance": {
      "repo_url": "https://github.com/example/skills",
      "commit_sha": "aabbccddeeff00112233445566778899aabbccdd",
      "tree_path": "skills/python.lint",
      "publisher_identity": "ci/acme-release"
    }
  },
  "relationships": {
    "depends_on": [
      {
        "slug": "python.base",
        "version_constraint": ">=1.0.0,<2.0.0",
        "optional": true,
        "markers": ["linux", "gpu"]
      }
    ],
    "extends": [
      {
        "slug": "python.base",
        "version": "1.0.0"
      }
    ],
    "conflicts_with": [],
    "overlaps_with": [
      {
        "slug": "python.format",
        "version": "1.0.0"
      }
    ]
  }
}
```

## Field Reference

### Top-Level Fields

| Field | Required | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| `intent` | Yes | `string` | none | Must be `create_skill` or `publish_version`. |
| `version` | Yes | `string` | none | Must be valid semver. |
| `content` | Yes | `object` | none | Contains the markdown body. |
| `metadata` | Yes | `object` | none | Contains structured metadata. |
| `governance` | No | `object` | `{ "trust_tier": "untrusted" }` | Publish-time governance input. |
| `relationships` | No | `object` | empty relationship groups | Authored relationships preserved with the version. |

### `content`

| Field | Required | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| `raw_markdown` | Yes | `string` | none | Canonical markdown body stored for the immutable version. |

Notes:

- `content` itself is mandatory.
- `raw_markdown` is mandatory.
- The DTO requires a string, but does not currently enforce a minimum length.

### `metadata`

| Field | Required | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| `name` | Yes | `string` | none | Human-readable skill name. |
| `description` | No | `string \| null` | `null` | Short summary. |
| `tags` | No | `string[]` | `[]` | Trimmed, deduplicated, empty entries removed. |
| `inputs_schema` | No | `object \| null` | `null` | Structured input contract. |
| `outputs_schema` | No | `object \| null` | `null` | Structured output contract. |
| `token_estimate` | No | `integer \| null` | `null` | Must be `>= 0`. |
| `maturity_score` | No | `number \| null` | `null` | Must be in `[0, 1]`. |
| `security_score` | No | `number \| null` | `null` | Must be in `[0, 1]`. |

### `governance`

| Field | Required | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| `trust_tier` | No | `string` | `untrusted` | Must be `untrusted`, `internal`, or `verified`. |
| `provenance` | No | `object \| null` | `null` | Additional publish-time provenance metadata. |

Important:

- `governance` is optional as a whole.
- If omitted, the server uses `trust_tier=untrusted`.
- Policy may require provenance for some trust tiers. That is not a JSON-schema requirement, but a governance rule evaluated by the server.

### `governance.provenance`

| Field | Required | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| `repo_url` | Yes, if `provenance` exists | `string` | none | Trimmed, cannot be blank. |
| `commit_sha` | Yes, if `provenance` exists | `string` | none | 7-64 hex chars, normalized to lowercase. |
| `tree_path` | No | `string \| null` | `null` | Trimmed if present, cannot be blank. |
| `publisher_identity` | No | `string \| null` | `null` | Trimmed if present, cannot be blank. |

### `relationships`

If omitted, all relationship groups default to empty arrays.

| Field | Required | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| `depends_on` | No | `object[]` | `[]` | Dependency selectors. |
| `extends` | No | `object[]` | `[]` | Exact version relationships. |
| `conflicts_with` | No | `object[]` | `[]` | Exact version relationships. |
| `overlaps_with` | No | `object[]` | `[]` | Exact version relationships. |

### `relationships.depends_on[]`

| Field | Required | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| `slug` | Yes | `string` | none | Must match the slug pattern. |
| `version` | Conditionally | `string \| null` | `null` | Must be valid semver. |
| `version_constraint` | Conditionally | `string \| null` | `null` | Comma-separated semver comparators. |
| `optional` | No | `boolean \| null` | `null` | Whether consumers may omit the dependency at runtime. |
| `markers` | No | `string[]` | `[]` | Marker pattern restricted. |

Rules:

- Exactly one of `version` or `version_constraint` must be provided.
- Supplying both is invalid.
- Supplying neither is invalid.

### `relationships.extends[]`, `relationships.conflicts_with[]`, `relationships.overlaps_with[]`

Each item has the same shape:

| Field | Required | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| `slug` | Yes | `string` | none | Must match the slug pattern. |
| `version` | Yes | `string` | none | Must be valid semver. |

## Validation Rules

### Unknown Fields

Unknown fields are rejected at every level of the request body.

That means clients must not send extra keys not defined in the schema.

### Semver

Fields validated as semver:

- top-level `version`
- `relationships.depends_on[].version`
- `relationships.extends[].version`
- `relationships.conflicts_with[].version`
- `relationships.overlaps_with[].version`

Examples:

- valid: `1.2.3`
- valid: `1.2.3-rc.1`
- valid: `1.2.3+build.5`
- invalid: `latest`

### Version Constraint

`relationships.depends_on[].version_constraint` must be a comma-separated list of semver comparators.

Examples:

- valid: `>=1.0.0,<2.0.0`
- valid: `==1.2.3`
- invalid: `1.x`

### Markers

Dependency markers must match:

`^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$`

Examples:

- valid: `linux`
- valid: `gpu`
- valid: `python:3.12`
- invalid: `linux amd64`

## Intent Semantics

### `intent=create_skill`

Use this when publishing the first version under a new slug.

If the slug already exists, the server returns:

- `409 Conflict`
- error code: `SKILL_ALREADY_EXISTS`

### `intent=publish_version`

Use this when publishing a new immutable version under an existing slug.

If the slug does not exist, the server returns:

- `404 Not Found`
- error code: `SKILL_NOT_FOUND`

## Defaults Summary

If omitted, the server applies these defaults:

- `governance.trust_tier = "untrusted"`
- `metadata.tags = []`
- `relationships.depends_on = []`
- `relationships.extends = []`
- `relationships.conflicts_with = []`
- `relationships.overlaps_with = []`

## Common Errors

| Status | Code | When |
| --- | --- | --- |
| `201` | none | Publish succeeded. |
| `409` | `DUPLICATE_SKILL_VERSION` | The same `slug@version` already exists. |
| `409` | `SKILL_ALREADY_EXISTS` | `intent=create_skill` was used for an existing slug. |
| `404` | `SKILL_NOT_FOUND` | `intent=publish_version` was used for a missing slug. |
| validation failure | `INVALID_REQUEST` | Path/body fields failed route or DTO validation. |
| `500` | `CONTENT_STORAGE_FAILURE` | Persistence failed after request validation. |

## Practical Notes

- The `slug` belongs in the path, not in the JSON body.
- The endpoint accepts JSON, not multipart form data.
- `provenance` is optional structurally, but governance policy may make it required for some trust tiers.
- Historical docs may mention older publish route shapes. This file describes the repo's current live contract only.
