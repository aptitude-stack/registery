# Publish Bundle Migration

This is a breaking change for publishers and exact-content consumers.

## What Changed

Old publish contract:

- request content type: `application/json`
- exact artifact field: `content.raw_markdown`

New publish contract:

- request content type: `multipart/form-data`
- required `metadata` JSON part
- required `bundle` binary part with media type `application/zip`
- enforced bundle limits: `5 MiB` max size, `200` files, `240`-byte max path length

Old exact content fetch:

- `GET /skills/{slug}/{version}/content`
- response type: `text/markdown`

New exact content fetch:

- `GET /skills/{slug}/{version}/content`
- response type: `application/zip`

## What Did Not Change

- `GET /skills/{slug}` still lists visible versions for one skill identity.
- `GET /skills/{slug}/{version}` still returns exact structured metadata.
- `POST /discovery` still operates on normalized metadata only.
- `GET /resolution/{slug}/{version}` still returns structured authored dependency declarations only.

## Compatibility Stance

- Recommended path: hard cut to bundle-based publishing for all new publishes.
- Publisher clients should stop sending `content.raw_markdown`.
- Exact-content consumers must stop assuming markdown and start handling `application/zip`.
- Historical versions are stored and served through the current repository implementation, but publishers should republish legacy skills as full bundles if they need canonical directory fidelity.

## Publisher Migration Steps

1. Stop sending JSON-only publish requests.
2. Build a skill directory bundle with one kebab-case root directory.
3. Put `SKILL.md` at the root of that directory.
4. Move auxiliary files under `scripts/`, `references/`, and `assets/`.
5. Send structured metadata in the `metadata` JSON part and the zip file in the `bundle` part.

## Consumer Migration Steps

1. Stop treating `/content` responses as markdown text.
2. Expect `application/zip`.
3. Validate or unpack the returned bundle as needed.
4. Continue using the exact metadata route for queryable fields and checksums.
5. Treat `content.checksum.digest` as the digest of the exact stored zip bundle and `version_checksum.digest` as the digest of the canonical version payload.

## Why The Contract Broke

The registry now stores one immutable bundle artifact per version instead of reconstructing skill content from a markdown body. That keeps discovery, governance, and dependency resolution relational and queryable while making the exact artifact fetch precise, cacheable, and extensible to full skill directories.

The checksum model changed with that storage shape:

- content checksums are now `sha256` over stored bundle bytes
- version checksums are recomputed from the bundle content digest plus normalized metadata, governance, and authored relationships
- search-document `content_size_bytes` now reflects stored bundle size rather than extracted markdown length
