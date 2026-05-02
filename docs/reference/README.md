# Reference Docs

Use this directory for canonical technical reference.
It should answer exact questions about the current contract without retelling the product story.

## What Belongs Here

- route and payload contracts
- settings, env vars, and runtime posture
- schema and storage baselines
- operational runbooks

## What Does Not

- setup tutorials
- architecture rationale
- future design proposals

## Contents

- [`api-contract.md`](api-contract.md): canonical HTTP contract
- [`runtime-profiles.md`](runtime-profiles.md): `APP_ENV`, Compose profiles, and env-var roles
- [`render-neon-deployment.md`](render-neon-deployment.md): production API deployment on Render with Neon Postgres
- [`service-token-governance.md`](service-token-governance.md): governed bearer-token auth contract
- [`enterprise-governance.md`](enterprise-governance.md): namespaces, promotion workflow, policy packs, trust evidence, and visibility rules
- [`publish-request-schema.md`](publish-request-schema.md): publish request reference
- [`schema.md`](schema.md): canonical PostgreSQL schema baseline
- [`storage-strategy.md`](storage-strategy.md): current storage decision
- [`operations/README.md`](operations/README.md): operational runbook index
