# Governance Denials

## Symptoms

- publish or lifecycle transitions return `403`
- governance and lifecycle failure panels spike

## Checks

1. Search audit rows for denied events using `request_id`.
2. Review `reason_code`, `trust_tier`, `actor_scopes`, and `policy_profile`.
3. Confirm the active policy profile from settings.

## Actions

1. Fix caller scopes or use an admin token when required.
2. Supply provenance for trust tiers that require it.
3. If policy configuration changed unexpectedly, restore the previous profile or roll back the deployment.
