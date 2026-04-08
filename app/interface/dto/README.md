# app.interface.dto module

Request and response DTOs for the public HTTP contract.

## Purpose

Defines Pydantic models and example payloads for publish, discovery,
identity-level version listing, exact metadata fetch, and
lifecycle-status APIs.

## Structure

- `skills_publish.py`: publish request models, authored relationship selectors,
  and governance/provenance input DTOs.
- `skills_discovery.py`: discovery request/response DTOs.
- `skills_fetch.py`: version-list and exact metadata response
  envelopes.
- `skills_resolution.py`: direct dependency response DTOs.
- `skills_lifecycle.py`: lifecycle-status request/response DTOs.
- `skills_shared.py`: shared normalization helpers and response submodels.
- `skills.py`: compatibility re-export for callers that still import the legacy
  aggregate module path.

## Notes

- DTOs should mirror the public contract only; they should not preserve deleted
  route shapes.
- DTOs that reuse core type aliases should import them from `app.core.skills.*`
  when they belong to the skill-domain bounded context.
- Publish body DTOs model only versioned content and metadata; the published
  skill `slug` is carried by the route path at `POST /skills/{slug}`,
  and `intent` declares whether the caller is creating a new skill slug or
  publishing a version to an existing one.
- Advisory provenance fields are publisher-supplied on publish, while
  server-derived trust context is returned only on immutable metadata reads.
- Raw markdown content fetch is modeled directly as an HTTP response, so this
  module keeps the exact metadata response model but not a markdown-body DTO.
