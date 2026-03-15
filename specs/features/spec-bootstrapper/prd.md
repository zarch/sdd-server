# Feature: Spec Bootstrapper

**Version:** 1.0
**Date:** 2026-03-15
**Status:** 🔵 Planned — Pending Implementation
**Parent PRD:** [specs/prd.md](../../prd.md) — Feature A (Specification Management)
**Recipe:** [specs/recipes/spec-bootstrapper.yaml](../../recipes/spec-bootstrapper.yaml)

---

## 1. Overview

### 1.1 Problem

New users starting SDD on an already-running project have no specs. The existing pipeline
requires specs to exist before it can run:

- The spec-linter emits `blocked` when `specs/prd.md` is missing
- There is no automated way to derive specs from a codebase — users must write them by hand
- Writing SDD-compliant specs from scratch is time-consuming and error-prone for large projects
- Test suites encode acceptance criteria implicitly; that knowledge is inaccessible to the pipeline without manual extraction

### 1.2 Solution

An **on-demand Goose recipe** (`specs/recipes/spec-bootstrapper.yaml`) that reverse-engineers an
existing codebase into SDD-compliant specs. It surveys the source tree, reads package manifests,
mines test names for implied acceptance criteria, scans git history for feature timeline, and
generates `specs/prd.md`, `specs/arch.md`, and `specs/features/<slug>/` stubs.

It also supports **update mode**: if specs already exist, it extends them with an
`## Updated: <date>` subsection rather than replacing content.

The recipe is invoked:
- Directly: `goose run --recipe specs/recipes/spec-bootstrapper.yaml`
- Via MCP tool (future): `sdd_bootstrap_specs()`

### 1.3 Scope

**In scope:**
- Generating `specs/prd.md` with user stories and AC-XX entries inferred from tests and git history
- Generating `specs/arch.md` with component inventory, tech stack, and data flow
- Generating `specs/features/<slug>/prd.md` and `specs/features/<slug>/arch.md` stubs for each detected feature
- Update mode: extending existing specs while preserving all original content
- Detecting up to 20 feature boundaries from module/package groupings

**Out of scope:**
- Generating `specs/features/<slug>/tasks.md` (role checklists require a human decision on scope)
- Generating `specs/tasks.md` root file (pipeline state is not derivable from code)
- Replacing or deleting any existing spec content without explicit `update_existing=true`
- Automatic invocation during the pipeline (always on-demand)

---

## 2. User Stories

### 2.1 Generate Specs from Scratch

**User Story:**
> As a developer onboarding an existing project to SDD, I want to run a single command that reads my codebase and produces SDD-compliant spec files, so that I can immediately start the pipeline without writing specs by hand.

**Acceptance Criteria:**

- **AC-01:** Given a project with no `specs/` directory (or an empty one), the recipe creates `specs/prd.md` containing at least one user story and at least one `AC-XX` entry inferred from the codebase.
- **AC-02:** The recipe creates `specs/arch.md` containing a `## Architecture` section with a component inventory and the detected tech stack.
- **AC-03:** For each detected feature (up to 20), the recipe creates `specs/features/<slug>/prd.md` and `specs/features/<slug>/arch.md` stubs. Each `prd.md` contains a title, status, and placeholder AC section.
- **AC-04:** The recipe emits a `RoleCompletionEnvelope` as its final JSON line, with `"sdd_role": "spec-bootstrapper"`, `"status": "completed"`, a `generated` list of created file paths, and `stats` counts for `source_files_scanned`, `tests_analyzed`, `acs_generated`, and `features_detected`.

---

### 2.2 Update Existing Specs

**User Story:**
> As a developer whose codebase has grown since the specs were last written, I want to re-run the bootstrapper to extend existing specs with new discoveries, without losing any content I have already written.

**Acceptance Criteria:**

- **AC-05:** When `specs/prd.md` already exists and the recipe is run with the default `update_existing=false`, the recipe emits `"status": "blocked"` with summary `"specs already exist; pass update_existing=true to update"` and writes no files.
- **AC-06:** When run with `update_existing=true`, the recipe appends a new `## Updated: <date>` subsection to `specs/prd.md` and `specs/arch.md`, containing only newly discovered content. All original sections are preserved verbatim.
- **AC-07:** Update mode is idempotent: running the recipe twice with `update_existing=true` produces a second `## Updated: <date>` subsection but does not duplicate the first or alter existing content.
- **AC-08:** Feature directories (`specs/features/<slug>/`) that already exist are always skipped regardless of `update_existing` value. The envelope `skipped` list includes each skipped path and the reason `"feature_dir_exists"`.

---

### 2.3 Feature Boundary Detection

**User Story:**
> As a developer, I want the bootstrapper to identify natural feature boundaries from my module structure, so that the generated `specs/features/` tree reflects how my codebase is actually organized.

**Acceptance Criteria:**

- **AC-09:** The recipe identifies feature boundaries from directory structure: each top-level package or module under the primary source root (e.g. `src/`, `lib/`, `app/`) becomes a candidate feature if it contains at least one source file.
- **AC-10:** Feature slugs are kebab-case, derived from the module/directory name: lowercase, underscores replaced with hyphens, non-alphanumeric characters removed. Example: `user_auth` → `user-auth`, `APIClient` → `apiclient`.
- **AC-11:** The recipe detects at most 20 features per run. If more than 20 candidate features exist, it selects the 20 with the highest file count and reports the rest as `"omitted_features"` in the envelope.

---

### 2.4 Test Mining for Acceptance Criteria

**User Story:**
> As a developer, I want the bootstrapper to extract implied acceptance criteria from my test suite, so that the generated `prd.md` reflects what the code is verified to do rather than what I remember writing.

**Acceptance Criteria:**

- **AC-12:** The recipe scans all test files (any file matching `test_*.py`, `*_test.py`, `*.test.ts`, `*.spec.ts`, or similar patterns for detected languages). For each test function or `it()` block, it extracts the name, strips the `test_` prefix, and converts it to a human-readable AC entry in the format `**AC-XX:** <description>`.
- **AC-13:** The recipe includes at most 30 generated ACs in `specs/prd.md` to avoid overwhelming downstream roles. If more than 30 test-derived ACs are found, it selects the 30 whose names most closely resemble user-facing behavior (prefer names containing `should`, `can`, `returns`, `creates`, `deletes`, `validates`) and reports the total test count in the envelope `stats`.

---

## 3. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Invocation | On-demand only (direct recipe or MCP tool) |
| Safety | Never deletes or overwrites content without `update_existing=true` |
| Idempotency | Default run with no specs → generates; re-run with `update_existing=false` → blocked |
| Update safety | `update_existing=true` → appends only; original content never altered |
| Feature dir safety | `specs/features/<slug>/` always skipped if it exists |
| Max features | 20 per run |
| Max ACs | 30 generated ACs in prd.md |
| Timeout | 600 seconds (large codebases) |

---

## 4. Dependencies

| Dependency | Type | Notes |
|------------|------|-------|
| Goose `developer` extension | Runtime | File read/write, directory walk |
| `specs/` directory | Runtime output | Created if absent |
| Spec Linter | Downstream | Run after bootstrap to validate generated specs |
| Architect role | Downstream | Populates `arch.md` stubs after bootstrap |
| `sdd_bootstrap_specs` MCP tool | Future | Wraps this recipe for programmatic invocation |
