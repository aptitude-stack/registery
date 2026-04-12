# Publish Endpoint Schema

Live publish contract for `Aptitude Registry`.

This document describes the current `POST /skills/{slug}` request shape implemented by the server.

Canonical sources:

- `app/interface/api/skills.py`
- `app/interface/api/skill_api_support_publish.py`
- `app/interface/dto/skills_publish.py`
- `app/interface/validation/skill_bundle.py`
- `app/core/governance.py`

## Endpoint

- Method: `POST`
- Path: `/skills/{slug}`
- Required auth scope: `publish`
- Required header: `Authorization: Bearer <token>`
- Request content type: `multipart/form-data`

## Multipart Parts

The request has two required parts:

| Part | Type | Content Type | Meaning |
| --- | --- | --- | --- |
| `metadata` | string | `application/json` | Structured publish metadata, governance, and relationships |
| `bundle` | binary | `application/zip` | Immutable skill directory bundle |

## Path Parameter

### `slug`

- Required: yes
- Type: `string`
- Pattern: `^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,127})$`
- Meaning: stable public skill identifier

## `metadata` JSON Shape

```json
{
  "intent": "create_skill",
  "version": "1.2.3",
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
    "extends": [{"slug": "python.base", "version": "1.0.0"}],
    "conflicts_with": [],
    "overlaps_with": [{"slug": "python.format", "version": "1.0.0"}]
  }
}
```

Legacy `content.raw_markdown` is no longer accepted.

## Bundle Validation Rules

The uploaded `bundle` part must:

- be a valid zip archive
- unpack without absolute paths or path traversal
- contain exactly one root skill directory
- use a kebab-case root directory name
- contain `SKILL.md` at the root of that directory
- not contain `README.md` at the root
- only use these top-level children: `SKILL.md`, `scripts/`, `references/`, `assets/`
- stay within these server-enforced limits:
  - maximum bundle size: `5 MiB`
  - maximum file count: `200`
  - maximum archive path length: `240` bytes

## Field Reference

### Top-Level `metadata` JSON Fields

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `intent` | Yes | `string` | Must be `create_skill` or `publish_version`. |
| `version` | Yes | `string` | Must be valid semver. |
| `metadata` | Yes | `object` | Structured queryable metadata stored outside the bundle. |
| `governance` | No | `object` | Publish-time governance input. |
| `relationships` | No | `object` | Authored relationships preserved with the version. |

### `metadata.metadata`

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

### `metadata.governance`

| Field | Required | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| `trust_tier` | No | `string` | `untrusted` | Must be `untrusted`, `internal`, or `verified`. |
| `provenance` | No | `object \| null` | `null` | Additional publish-time provenance metadata. |

### `metadata.relationships.depends_on[]`

| Field | Required | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| `slug` | Yes | `string` | none | Must match the slug pattern. |
| `version` | Conditionally | `string \| null` | `null` | Must be valid semver. |
| `version_constraint` | Conditionally | `string \| null` | `null` | Comma-separated semver comparators. |
| `optional` | No | `boolean \| null` | `null` | Whether consumers may omit the dependency at runtime. |
| `markers` | No | `string[]` | `[]` | Marker pattern restricted. |

Rules:

- Exactly one of `version` or `version_constraint` must be provided.
- Unknown fields are rejected at every level of the JSON metadata payload.

## Common Errors

| Status | Code | When |
| --- | --- | --- |
| `201` | none | Publish succeeded. |
| `409` | `DUPLICATE_SKILL_VERSION` | The same `slug@version` already exists. |
| `409` | `SKILL_ALREADY_EXISTS` | `intent=create_skill` was used for an existing slug. |
| `404` | `SKILL_NOT_FOUND` | `intent=publish_version` was used for a missing slug. |
| `422` | `INVALID_REQUEST` | Path, metadata JSON, or bundle validation failed. |
| `500` | `CONTENT_STORAGE_FAILURE` | Persistence failed after request validation. |

## Practical Notes

- The `slug` belongs in the path, not in the JSON metadata part.
- The server stores the uploaded artifact as one immutable `application/zip` bundle.
- The server computes `content.checksum.digest` from the stored bundle bytes, not from extracted markdown.
- The server computes `version_checksum.digest` from the content checksum plus normalized metadata, governance, and authored relationships.
- Queryable metadata, governance, and relationships remain normalized outside the bundle.
- `content.raw_markdown` belongs to the retired contract and should be removed from publisher clients.
