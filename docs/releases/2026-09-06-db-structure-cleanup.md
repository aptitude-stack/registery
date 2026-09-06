# Database cleanup release evidence

## Rehearsal

The approved rehearsal ran on Neon project `bitter-night-16887852`, child
`br-green-hill-amqzwaxj` (`db-cleanup-0013-rehearsal-20260906`), copied from production
`br-calm-bonus-ambx0ki5`, database `aptitude`. The direct endpoint was
`ep-royal-fog-amdh7t7m.c-5.us-east-1.aws.neon.tech`.

| Check | Result |
| --- | --- |
| Initial revision and canonical preflight | `0012_remove_metadata_schemas`; no blockers or advisories |
| Upgrade to 0013 | Passed; 15.245 seconds |
| Application reads | Health, readiness, 46-entry catalog, nested metadata, resolution, and lexical search passed |
| Artifact read | Repository content bytes matched checksum and size; no install-counter write |
| Downgrade to 0012 | Passed; 13.632 seconds; canonical fingerprints match |
| Re-upgrade to 0013 | Passed; 15.297 seconds; canonical fingerprints match |

The combined canonical SHA-256 remained
`6667edb5f96c10cf46a84fe603f771da897750e00e558c5676370bdfe6a0370c`.
The comparison covered 46 skills/versions/artifacts/search documents/embedding
rows, 38 selectors and graph edges, 172 audit events, one user-star row, and all
retained governance and signal tables. Empty production tables were also included.
Populated synthetic local fixtures separately covered co-usage and trust evidence.

Application smoke used database read-only transactions, an ephemeral local read
identity, and disabled audit persistence. It did not call an embedding provider.
Ordinary integration fixtures were never pointed at the clone or production.
Operator reports are retained locally under
`/private/tmp/aptitude-db-cutover-20260906/`; they contain counts and digests, not
credentials or artifact bodies. The rehearsal branch is retained.

## Application verification

- Local registry: 391 tests passed; quality and type checks passed.
- Local website: 152 tests passed; typecheck passed.
- Registry commit `d3791651780fd868e741d9669958cc189e866e84`: Master PR Gate,
  Docker Build and Smoke, and Docker Publish all passed.
- Registry release PR: https://github.com/aptitude-stack/registery/pull/145.
- Website commit `f2fe653`: pushed to `master`; Vercel deployment status succeeded.
- No PyPI client changed in this database cleanup, so no package release is required.

## Production cutover

Pending execution. The user approved a brief service outage because the live API
uses Render's Free plan. Automatic `master-push-ci.yml` deployment was temporarily disabled, then restored
to its prior `active` state while suspension access is pending. Disable it again
before merging the release PR. The legacy Render pre-deploy migration command was
cleared. The API remains on previous commit
`611ce49938a86c9a06a71545c460e5bbb33bfdd2` and database revision 0012.

Live Render inventory contained the API only: no cron, workflow service, or
one-off job was present. Recheck these facts and database activity immediately
before the final backup/preflight. Restore the deployment workflow's prior state
after the controlled release or if execution is deferred.
