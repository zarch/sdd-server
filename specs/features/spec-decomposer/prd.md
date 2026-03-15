# Feature: Spec Decomposer

**Version:** 1.0
**Date:** 2026-03-15
**Status:** 🔵 Planned — Pending Implementation
**Parent PRD:** [specs/prd.md](../../prd.md) — Feature A (Specification Management)

---

## 1. Overview

### 1.1 Problem

As projects grow, the root spec files (`specs/prd.md`, `specs/arch.md`, `specs/tasks.md`) become large monolithic documents. This creates several problems:

- AI agents (Goose) receive too much context in a single session, leading to shallow analysis or context overflow
- Feature-scoped pipeline runs (e.g. "review only the auth feature") have no spec boundaries to operate within
- Teams onboarding existing projects have comprehensive but undivided specs with no feature-level granularity
- The SDD `specs/features/` convention is manual — there is no tool to bootstrap it from an existing monolithic PRD

### 1.2 Solution

An **on-demand MCP tool** (`sdd_decompose_specs`) that analyzes the root spec files, identifies logical feature boundaries, and creates a `specs/features/<slug>/` directory for each feature containing its own `prd.md`, `arch.md`, and `tasks.md`.

This is **not a pipeline role** — it runs explicitly when requested, not automatically on every cycle. The root spec files are not deleted; instead, a `## Feature Index` section is added pointing to the individual feature specs.

### 1.3 Scope

**In scope:**
- Detecting feature boundaries from prd.md (H2/H3 sections, AC groupings, explicit feature blocks)
- Creating `specs/features/<slug>/prd.md` with the relevant subset of user stories and ACs
- Creating `specs/features/<slug>/arch.md` stub referencing root arch.md
- Creating `specs/features/<slug>/tasks.md` stub with role checklist
- Patching root prd.md with a `## Feature Index` section
- Idempotency: re-runs detect existing feature dirs and skip or merge without clobbering
- Dry-run mode: report what would be created without writing any files

**Out of scope:**
- Automatic decomposition on every pipeline run (always explicit)
- Decomposing arch.md content into feature-level architecture (stub only — architect role populates it)
- Merging feature specs back into root specs (reverse operation not supported in v1)
- Splitting tasks.md by feature (too coupled to completion state)

---

## 2. User Stories

### 2.1 Decompose a Monolithic PRD

**User Story:**
> As a developer with a large PRD, I want to split it into feature-scoped specs, so that each SDD pipeline run operates on a focused, manageable context.

**Acceptance Criteria:**

- **AC-01:** Given a root `specs/prd.md` with multiple distinct feature sections, `sdd_decompose_specs` identifies each feature and creates `specs/features/<feature-slug>/prd.md` containing the relevant user stories and ACs.
- **AC-02:** Each generated `prd.md` preserves the original AC-XX numbering from the root PRD and includes a back-reference: `> Decomposed from [specs/prd.md](../../prd.md)`.
- **AC-03:** Feature slugs are derived from section headings: lowercase, spaces replaced with hyphens, non-alphanumeric characters removed. Example: "Feature A: Specification Management" → `specification-management`.
- **AC-04:** The root `specs/prd.md` is updated to include a `## Feature Index` section listing all decomposed features with links to their `specs/features/<slug>/prd.md`. The original content is preserved above this section.
- **AC-05:** If `sdd_decompose_specs` is run when `specs/features/<slug>/` already exists, it skips that feature and reports it as "already exists — skipped". Existing files are never overwritten without explicit `--force` flag.

**Technical Requirements:**
- Feature boundary detection uses heuristics: top-level `### Feature` headings, or groups of consecutive AC-XX entries that share a common prefix (e.g. AC-01 through AC-05 under "Authentication")
- Minimum viable feature: at least 2 ACs or 1 user story
- Maximum features in a single decomposition: 50 (to prevent runaway splitting)

---

### 2.2 Onboard Existing Project

**User Story:**
> As a developer starting SDD on an existing project that already has a structured PRD, I want to decompose it into feature specs in one command, so that I can immediately start running feature-scoped pipeline reviews.

**Acceptance Criteria:**

- **AC-06:** `sdd_decompose_specs` works on any project regardless of whether it was initialized with `sdd_init`. The only requirement is that `specs/prd.md` exists.
- **AC-07:** After decomposition, running `sdd_review_run` with `target="<feature-slug>"` uses the feature-scoped `specs/features/<feature-slug>/prd.md` as its primary input rather than the root PRD.
- **AC-08:** The spec-linter, when run after decomposition, validates the new feature directories and reports any structural issues.

---

### 2.3 Dry-Run Mode

**User Story:**
> As a developer, I want to preview what `sdd_decompose_specs` would create before it writes any files, so I can verify the feature boundary detection before committing.

**Acceptance Criteria:**

- **AC-09:** When called with `dry_run=True`, `sdd_decompose_specs` returns a structured report of what would be created (feature slugs, AC assignments, file paths) without writing any files.
- **AC-10:** The dry-run report includes: list of detected features, AC IDs assigned to each feature, total AC coverage (ACs assigned / total ACs in prd.md), and any ACs that could not be assigned to a feature.

---

### 2.4 Stub Generation for arch.md and tasks.md

**User Story:**
> As a developer, I want stub arch.md and tasks.md files created for each feature, so that the full role checklist is ready immediately without manual file creation.

**Acceptance Criteria:**

- **AC-11:** For each feature, `sdd_decompose_specs` creates `specs/features/<slug>/arch.md` with:
  - A title heading: `# Architecture: <Feature Name>`
  - A back-reference to root arch.md
  - A placeholder `## Architecture` section for the architect role to populate
- **AC-12:** For each feature, `sdd_decompose_specs` creates `specs/features/<slug>/tasks.md` with:
  - A title heading: `# Tasks: <Feature Name>`
  - A role review checklist (all 11 roles, all unchecked)
  - Empty Completed / In Progress / Pending tables

---

## 3. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Invocation | On-demand MCP tool only (never automatic) |
| Idempotency | Re-runs skip existing dirs; never clobber without `--force` |
| Safety | Never deletes files; only creates or appends |
| Dry-run | Supported via `dry_run=True` parameter |
| Performance | < 30 seconds for up to 50 features |
| Max features | 50 per decomposition run |

---

## 4. Dependencies

| Dependency | Type | Notes |
|------------|------|-------|
| `specs/prd.md` | Runtime input | Mandatory — error if missing |
| `specs/features/` | Runtime output | Created if not present |
| `SpecManager` | Internal | `src/sdd_server/core/spec_manager.py` — file read/write |
| `FileSystemClient` | Internal | `src/sdd_server/infrastructure/filesystem.py` — path safety |
| Spec Linter | Downstream | Run after decomposition to validate new feature dirs |
| Architect role | Downstream | Populates `arch.md` stubs after decomposition |
