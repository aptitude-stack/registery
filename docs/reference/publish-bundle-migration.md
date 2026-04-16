# Publish Artifact Migration

This is a breaking change for publishers and exact-content consumers.

## What Changed

Old publish contract:

- request content type: `application/json`
- exact artifact field: `content.raw_markdown`

New publish contract:

- request content type: `multipart/form-data`
- required `metadata` JSON part
- required `bundle` binary part with filename suffix `.tar.zst`
- required `bundle` media type: `application/zstd`
- enforced artifact limit: `5 MiB` max size

Old exact content fetch:

- `GET /skills/{slug}/{version}/content`
- response type: `text/markdown`

New exact content fetch:

- `GET /skills/{slug}/{version}/content`
- response type: `application/zstd`

## What Did Not Change

- `GET /skills/{slug}` still lists visible versions for one skill identity.
- `GET /skills/{slug}/{version}` still returns exact structured metadata.
- `POST /discovery` still operates on normalized metadata only.
- `GET /resolution/{slug}/{version}` still returns structured authored dependency declarations only.

## Compatibility Stance

- Recommended path: hard cut to bundle-based publishing for all new publishes.
- No backward compatibility is preserved for zip uploads.
- Publisher clients should stop sending `content.raw_markdown`.
- Exact-content consumers must stop assuming markdown and start handling `application/zstd`.
- Historical versions are stored and served through the current repository implementation, but publishers should republish legacy skills as full bundles if they need canonical directory fidelity.

## Publisher Migration Steps

1. Stop sending JSON-only publish requests.
2. Build the publisher artifact as a `.tar.zst` file.
3. Ensure all mandatory structured metadata fields are present in the `metadata` JSON part.
4. Send the `.tar.zst` file in the `bundle` part with media type `application/zstd`.

## Consumer Migration Steps

1. Stop treating `/content` responses as markdown text.
2. Expect `application/zstd`.
3. Handle or unpack the returned artifact as needed.
4. Continue using the exact metadata route for queryable fields and checksums.
5. Treat `content.checksum.digest` as the digest of the exact stored artifact and `version_checksum.digest` as the digest of the canonical version payload.

## Why The Contract Broke

The registry now stores one immutable artifact per version instead of reconstructing skill content from a markdown body. That keeps discovery, governance, and dependency resolution relational and queryable while making the exact artifact fetch precise and cacheable without unpacking publisher-owned archive structure.

The checksum model changed with that storage shape:

- content checksums are now `sha256` over stored artifact bytes
- version checksums are recomputed from the artifact content digest plus normalized metadata, governance, and authored relationships
- search-document `content_size_bytes` now reflects stored artifact size rather than extracted markdown length
