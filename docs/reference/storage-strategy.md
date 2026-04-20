# Storage Strategy for Skill Content

> Status: current storage decision record for the live registry baseline.

## Recommendation

Use PostgreSQL as the only persistence layer, but split queryable metadata from exact artifact storage.

The live artifact shape is now one immutable opaque artifact per version:

- metadata, governance, provenance, and relationships stay normalized and queryable
- exact artifact bytes are stored once per digest in `skill_contents`
- version rows bind immutably to one digest-addressed artifact blob
- discovery and ranking never inspect artifact contents beyond publish-time validation
- exact fetch returns the stored artifact bytes directly and emits the stored content digest as the artifact `ETag`

## Why

This is the simplest design that still preserves the right architectural boundary.

- Discovery stays fast because it reads normalized search documents only.
- Exact fetch stays precise because it returns the original `application/zstd` artifact.
- Publish stays transactional because the registry still uses one storage system.
- Deduplication stays cheap because identical artifacts share one digest-backed row.
- Version identity stays stable because version checksums are derived from the content digest plus structured version data instead of unpacked artifact content.

## Rejected Alternatives

- Filesystem storage: adds cross-store consistency problems for little value.
- Object storage: useful for larger artifacts, but unnecessary complexity for current workloads.
- Reconstructing artifacts from normalized rows: wrong abstraction, loses artifact fidelity.

## Current Direction

The registry is no longer markdown-content-centric.

- New publishes do not send `content.raw_markdown`.
- Exact content fetch does not return `text/markdown`.
- The authoritative stored artifact is a `.tar.zst` blob.
- Structured metadata remains separately queryable and independently evolvable.
- Search and document size fields now reflect stored artifact size, not extracted markdown length.
