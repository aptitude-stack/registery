# Storage Strategy for Skill Content

> Status: current storage decision record for the live registry baseline.
> Use [`schema.md`](schema.md) for the implemented schema shape.

## Purpose

Evaluate storage strategies for skill artifacts in `Aptitude Registry` and recommend a design based on the current workload:

- Skill bodies average `4-6 KB`
- Skills are fetched as whole documents
- Discovery and exact fetch should remain independently optimizable
- The server should stay operationally simple unless scale forces more complexity

## Architectural Context

The key design pressure is not raw blob throughput. It is maintaining fast discovery queries while keeping exact fetch simple, deterministic, and cheap to operate.

Because skill payloads are small, the main risk in introducing multiple storage systems is architectural overhead rather than storage efficiency.

## Evaluation Criteria

- Query performance for discovery
- Read performance for exact fetch
- Publish consistency
- Operational simplicity
- Scalability headroom
- Backup and restore complexity
- Future flexibility

## Strategy 1 - PostgreSQL Only, Single Record per Version

Store metadata and full skill content in PostgreSQL in the same logical version record.

Example shape:

- `skills`
- `skill_versions`
  - `slug`
  - `version`
  - `metadata_json`
  - `content_text`
  - `sha256_digest`
  - `published_at`

### Pros

- Simplest architecture and operational model
- Single transactional boundary for publish
- No orphaned files or cross-store consistency failures
- Easy backup, restore, replication, and auditing
- Exact fetch by `slug + version` is cheap for `4-6 KB` payloads

### Cons

- Discovery and exact fetch share one persistence engine
- Table growth can affect storage and replication if artifact sizes increase later
- Requires care with indexing so content storage does not bloat discovery paths

### Best Fit

- Small immutable text artifacts
- Whole-document fetches
- Moderate catalog size
- Teams optimizing for simplicity and correctness first

## Strategy 2 - PostgreSQL Only, Split Metadata and Content Tables

Keep PostgreSQL as the only persistence layer, but separate discovery-facing metadata from fetch-facing content into different tables and query paths.

Example shape:

- `skills`
- `skill_versions`
  - version metadata, lifecycle state, provenance, checksum, `content_fk`
- `skill_contents`
  - `sha256_digest`
  - `content_text`
  - `size_bytes`
- `skill_metadata`
  - name, description, tags, structured metadata

### Pros

- Preserves one transactional system
- Gives clear logical separation between discovery and fetch
- Supports deduplication across versions
- Discovery queries can avoid touching the content table
- Scales better than Strategy 1 without adding another storage backend

### Cons

- Slightly more schema and service complexity
- Publish flow is more involved than a single-row insert
- Still limited by PostgreSQL if artifacts become much larger in the future

### Best Fit

- Small immutable documents
- Need to keep discovery and fetch independently optimized
- Want deduplication and future-proofing without polyglot storage

## Strategy 3 - PostgreSQL + Local Filesystem

Store metadata and indexes in PostgreSQL, but write skill content to local disk and keep only the file path and checksum in PostgreSQL.

### Pros

- Physical separation between discovery and content fetch
- Cheap storage for larger artifacts
- Simple file streaming
- Keeps large byte reads away from PostgreSQL

### Cons

- Two persistence systems instead of one
- No true transaction across DB row and file write
- Backup and restore become harder
- Orphaned-file and missing-file reconciliation is required
- Scaling across multiple app instances becomes awkward

### Best Fit

- Large artifacts
- Single-node deployments
- Systems where file IO dominates and operational simplicity is less important than cheap storage

## Strategy 4 - PostgreSQL + S3-Compatible Object Storage

Store metadata, discovery indexes, and digest mappings in PostgreSQL, but store skill content in S3-compatible object storage.

### Pros

- Strongest long-term scalability for large or numerous artifacts
- Natural separation of metadata and payload access paths
- Works well for multi-instance and cloud deployments
- Good durability and distribution options

### Cons

- Highest implementation and operational complexity
- Publish consistency becomes cross-system
- Requires retry, cleanup, and reconciliation logic
- Overbuilt for `4-6 KB` whole-document skills
- Usually slower end-to-end for tiny objects than a local PostgreSQL fetch

### Best Fit

- Large binary artifacts
- High-volume multi-region distribution
- Systems already standardized on object storage patterns

## Comparison Summary

| Strategy | Performance for Current Skills | Complexity | Consistency Risk | Scale Headroom | Recommendation Fit |
| --- | --- | --- | --- | --- | --- |
| PostgreSQL only, single record | High | Low | Low | Medium | Good |
| PostgreSQL only, split tables | High | Low-Medium | Low | Medium-High | Best |
| PostgreSQL + local filesystem | Medium | Medium | Medium | Medium | Weak |
| PostgreSQL + S3-compatible storage | Medium for current size | High | Medium-High | High | Weak for now |

## Recommendation

Use **Strategy 2: PostgreSQL only, split metadata and content tables**.

This gives the architectural benefit you want, separation between discovery and exact fetch, without paying the operational cost of separate storage systems.

Recommended design:

- Discovery reads query only metadata and search-indexed columns
- Exact fetch reads artifact content by `slug + version`
- Artifact content is stored once per digest in PostgreSQL
- Version rows bind immutably to one digest
- `ETag` and checksum are derived from the digest

## Why This Is the Best Current Tradeoff

For `4-6 KB` skills fetched as a whole:

- PostgreSQL is fully capable of serving the content efficiently
- The dominant cost is system complexity, not payload size
- Logical separation of query paths is enough to optimize discovery and fetch independently
- Physical separation into filesystem or object storage would add failure modes with limited performance benefit

## Decision Trigger for Revisit

Revisit this decision if one or more of the following become true:

- Average artifact size grows materially beyond the current `4-6 KB`
- Fetch traffic becomes overwhelmingly larger than discovery traffic
- Multi-region or CDN-style distribution becomes a hard requirement
- Artifact types expand from text documents to large binary payloads

## Proposed ADR Outcome

For the current product phase, `Aptitude Registry` should use PostgreSQL as the only persistence layer for skill metadata and skill content. Discovery and exact fetch should be separated at the API, service, query, and schema levels, not by introducing filesystem or object-storage backends.
