# Autonomous Neon Registry DB Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current Vercel-managed Neon database with a fresh autonomous Neon project for the Render-hosted registry API.

**Architecture:** Keep the app unchanged: FastAPI on Render reads `DATABASE_URL`, and Alembic owns schema creation. Create a Neon-owned project, run migrations into an empty `aptitude` database, update Render's `DATABASE_URL`, and verify `/readyz`.

**Tech Stack:** Neon Postgres, Render Web Service `srv-d7pqsd7avr4c73bfb8t0`, FastAPI, SQLAlchemy, Alembic, `uv`, Render API, Neon CLI.

---

## Final Execution Record

- [x] Confirmed the Vercel-managed Neon project was removed manually.
- [x] Created standalone Neon org/project resources:
  `org-wild-pond-20247201`, `bitter-night-16887852`, `br-calm-bonus-ambx0ki5`,
  database `aptitude`, role `aptitude_app`.
- [x] Ran schema-only Alembic migration to `0003_skill_bundle_storage (head)`.
- [x] Updated Render `DATABASE_URL` without printing the secret value.
- [x] Deployed Render deploy `dep-d7q5lqdckfvc739isqpg`.
- [x] Verified Render subdomain `/healthz`, `/readyz`, and production `/docs`
  behavior.
- [ ] Re-check `https://api.aptitude-registry.dev/healthz` after custom-domain
  TLS propagation; it still returned a TLS handshake failure from this
  environment during cutover.

## Acceptance Criteria

- Render service `https://aptitude-registry-api.onrender.com/readyz` returns
  `200` with database status `ok`.
- Alembic current against the new Neon production branch reports
  `0003_skill_bundle_storage (head)`.
- No secrets or connection strings are committed to the repository.
