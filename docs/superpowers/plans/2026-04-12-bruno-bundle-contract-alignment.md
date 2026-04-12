# Bruno Bundle Contract Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the Bruno collection so publish and exact-content requests match the live bundle-based registry contract.

**Architecture:** Keep the existing Bruno scenario flow intact and only replace the retired wire-format assumptions. Publish requests move from JSON `content.raw_markdown` to multipart `metadata` plus zip `bundle`, while exact-content assertions move from markdown-body checks to zip artifact and cache-header checks.

**Tech Stack:** Bruno OpenCollection YAML, zip bundle fixtures, registry API contract docs

---

### Task 1: Add Bruno bundle fixtures

**Files:**
- Create: `bruno/fixtures/`
- Test: `docs/reference/publish-request-schema.md`

- [ ] **Step 1: Write the failing test**

Bruno publish requests currently assume inline markdown bodies and have no bundle fixtures to upload.

- [ ] **Step 2: Run test to verify it fails**

Read the current Bruno publish requests and confirm they still use `content.raw_markdown`.

- [ ] **Step 3: Write minimal implementation**

Add a small set of zip bundle fixtures with valid root directories and `SKILL.md` files for the positive and negative publish flows.

- [ ] **Step 4: Run test to verify it passes**

Confirm the fixtures exist under `bruno/fixtures/` and match the bundle rules in `docs/reference/publish-request-schema.md`.

- [ ] **Step 5: Commit**

Skip commit for this task unless requested.

### Task 2: Convert publish requests to multipart bundle uploads

**Files:**
- Modify: `bruno/collections/Positive/Publish Dependency Skill.yml`
- Modify: `bruno/collections/Positive/Publish Extension Skill.yml`
- Modify: `bruno/collections/Positive/Publish Overlap Skill.yml`
- Modify: `bruno/collections/Positive/Publish Skill v1.yml`
- Modify: `bruno/collections/Positive/Publish Skill v2.yml`
- Modify: `bruno/collections/Negative/Publish Invalid Request.yml`
- Modify: `bruno/collections/Negative/Seed Duplicate Skill Version.yml`
- Modify: `bruno/collections/Negative/Publish Duplicate Skill Version.yml`

- [ ] **Step 1: Write the failing test**

Identify every publish request that still sends JSON with `content.raw_markdown`.

- [ ] **Step 2: Run test to verify it fails**

Confirm the current files still specify `Content-Type: application/json` and JSON request bodies.

- [ ] **Step 3: Write minimal implementation**

Switch those requests to Bruno `multipart-form`, send the structured JSON in the `metadata` part, and upload the matching fixture zip in the `bundle` part.

- [ ] **Step 4: Run test to verify it passes**

Re-read the edited request files and confirm they use multipart bodies and no longer reference `content.raw_markdown`.

- [ ] **Step 5: Commit**

Skip commit for this task unless requested.

### Task 3: Align fetch assertions with zip content semantics

**Files:**
- Modify: `bruno/collections/Positive/Fetch Published Skill Content.yml`
- Modify: `bruno/collections/Negative/Fetch Missing Skill Content.yml`
- Modify: `bruno/collections/Positive/Fetch Published Skill Metadata.yml`

- [ ] **Step 1: Write the failing test**

Identify assertions that still expect `text/markdown`, markdown body text, or removed response fields.

- [ ] **Step 2: Run test to verify it fails**

Confirm the current files still assert markdown content or stale fields.

- [ ] **Step 3: Write minimal implementation**

Update the Accept header and assertions to reflect `application/zip`, immutable cache headers, persisted content digest/length metadata, and the current metadata envelope.

- [ ] **Step 4: Run test to verify it passes**

Re-read the edited request files and confirm the checks now match `docs/reference/api-contract.md`.

- [ ] **Step 5: Commit**

Skip commit for this task unless requested.
