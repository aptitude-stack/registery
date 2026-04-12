# Storage Strategy for Skill Content

> Status: current storage decision record for the live registry baseline.

## Recommendation

Use PostgreSQL as the only persistence layer, but split queryable metadata from exact artifact storage.

The live artifact shape is now one immutable zip bundle per version:

- metadata, governance, provenance, and relationships stay normalized and queryable
- exact artifact bytes are stored once per digest in `skill_contents`
- version rows bind immutably to one digest-addressed zip bundle
- discovery and ranking never inspect bundle contents beyond publish-time validation
- exact fetch returns the stored bundle bytes directly and emits the stored content digest as the bundle `ETag`

## Why

This is the simplest design that still preserves the right architectural boundary.

- Discovery stays fast because it reads normalized search documents only.
- Exact fetch stays precise because it returns the original `application/zip` artifact.
- Publish stays transactional because the registry still uses one storage system.
- Deduplication stays cheap because identical bundles share one digest-backed row.
- Version identity stays stable because version checksums are derived from the content digest plus structured version data instead of raw markdown text.

## Rejected Alternatives

- Filesystem storage: adds cross-store consistency problems for little value.
- Object storage: useful for larger artifacts, but unnecessary complexity for current workloads.
- Reconstructing bundles from normalized rows: wrong abstraction, loses artifact fidelity.

## Current Direction

The registry is no longer markdown-content-centric.

- New publishes do not send `content.raw_markdown`.
- Exact content fetch does not return `text/markdown`.
- The authoritative stored artifact is a zip bundle.
- Structured metadata remains separately queryable and independently evolvable.
- Search/document size fields now reflect stored bundle size, not extracted markdown length.
