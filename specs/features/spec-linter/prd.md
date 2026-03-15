# Feature: Spec Linter

**Version:** 1.0
**Date:** 2026-03-15
**Status:** ✅ Implemented
**Parent PRD:** [specs/prd.md](../../prd.md) — Feature B (Role-Based Workflow Engine)
**Recipe:** [specs/recipes/spec-linter.yaml](../../recipes/spec-linter.yaml)

---

## 1. Overview

### 1.1 Problem

The SDD pipeline assumed specs were always well-formed before any role ran. In practice:

- Teams onboarding existing projects had no way to verify SDD compliance before starting the pipeline
- Missing required sections silently degraded downstream agent output (architect, security-analyst, etc.)
- AC ID inconsistencies between prd.md, arch.md, and tasks.md went undetected until a human noticed
- Broken relative links in specs caused agents to silently skip referenced material
- There was no canonical entry point for "is this project ready to run SDD?"

### 1.2 Solution

A pre-flight spec auditor that runs as the **first role in every pipeline cycle** (priority 5, before architect at priority 10). It validates the specs/ folder structure, required sections, cross-references, naming conventions, and links — then writes its findings to `specs/arch.md` so all downstream roles can see the audit trail.

It also serves as an **onboarding gate**: run it against an existing project to get a compliance report before wiring up SDD.

### 1.3 Scope

**In scope:**
- Folder structure and file existence checks
- Required section validation per file type
- Acceptance Criteria ID cross-referencing
- File and directory naming convention enforcement (kebab-case)
- Broken relative markdown link detection
- Feature subdirectory consistency (`specs/features/<slug>/`)
- Writing `## Spec Audit` section to `specs/arch.md`
- Emitting a structured `RoleCompletionEnvelope`

**Out of scope:**
- Rewriting or restructuring specs (that is spec-decomposer's responsibility)
- Validating spec content quality (that is the architect's responsibility)
- Checking code-spec alignment (that is the alignment checker's responsibility)

---

## 2. User Stories

### 2.1 Pre-flight Validation

**User Story:**
> As a developer starting a new SDD cycle, I want the pipeline to validate my specs before any agent runs, so that I catch structural issues early and don't waste an expensive Goose session on broken input.

**Acceptance Criteria:**

- **AC-01:** If `specs/prd.md` does not exist, the spec-linter emits a `blocked` status envelope and the pipeline halts. All other checks are skipped.
- **AC-02:** If `specs/arch.md` does not exist, the spec-linter records a `medium` severity finding (expected on first run — the architect creates it). The pipeline is not blocked.
- **AC-03:** If `specs/tasks.md` does not exist, the spec-linter records a `medium` severity finding. The pipeline is not blocked.
- **AC-04:** On completion, the spec-linter writes a `## Spec Audit` section to `specs/arch.md` (creating a minimal stub if the file does not yet exist) containing a findings table and summary.
- **AC-05:** The spec-linter always emits a `RoleCompletionEnvelope` as the final line of stdout, including `"clean": true` when no findings exist and `"clean": false` otherwise.

**Technical Requirements:**
- Blocking condition is only AC-01 (missing prd.md). All other findings are informational.
- The `## Spec Audit` section must be idempotent: updated in-place if it already exists.
- Must complete within 120 seconds.

---

### 2.2 Spec Structure Validation

**User Story:**
> As a developer, I want to know if my spec files are missing required sections, so that downstream agents receive complete, well-structured input.

**Acceptance Criteria:**

- **AC-06:** The spec-linter checks `specs/prd.md` for a `## Acceptance Criteria` section and at least one `AC-\d+` entry. Missing section → `high` severity. No AC entries → `high` severity.
- **AC-07:** If `specs/arch.md` exists, the spec-linter checks for a `## Architecture` or `## System Architecture` section. Missing → `medium` severity.
- **AC-08:** If `specs/tasks.md` exists, the spec-linter checks for a `## Tasks` or `# Tasks` heading. Missing → `medium` severity.
- **AC-09:** For each feature in `specs/features/<slug>/`, if a `prd.md` exists but has no Acceptance Criteria section → `high` severity finding referencing the specific feature file.

---

### 2.3 AC ID Cross-Reference

**User Story:**
> As a developer, I want to know when task files or arch docs reference acceptance criteria that don't exist in the PRD, so I can keep specs consistent as they evolve.

**Acceptance Criteria:**

- **AC-10:** The spec-linter extracts all `AC-\d+` IDs from `specs/prd.md` and compares them against IDs found in `specs/arch.md` and `specs/tasks.md`.
- **AC-11:** Any AC ID found in arch.md or tasks.md but not defined in prd.md → `medium` severity finding ("stale reference").
- **AC-12:** Any AC ID defined in prd.md with no corresponding reference anywhere else → `low` severity finding ("unreferenced AC").
- **AC-13:** For each feature in `specs/features/<slug>/prd.md`, AC IDs are validated against the root prd.md (must be a subset or explicitly scoped extension).

---

### 2.4 Naming Convention Enforcement

**User Story:**
> As a developer, I want spec file and directory names to follow a consistent convention, so that recipe template substitutions and feature routing work reliably.

**Acceptance Criteria:**

- **AC-14:** All files and directories under `specs/` must use lowercase kebab-case names. Uppercase letters → `high` severity.
- **AC-15:** Words must be separated by hyphens, not underscores or spaces. Underscores or spaces in names → `medium` severity.
- **AC-16:** Only `.md`, `.yaml`, `.yml`, and `.json` file extensions are allowed under `specs/`. Any other extension → `low` severity.

---

### 2.5 Broken Link Detection

**User Story:**
> As a developer, I want broken relative links in my specs to be flagged, so that agents don't silently skip referenced material.

**Acceptance Criteria:**

- **AC-17:** The spec-linter scans all `.md` files in `specs/` for relative markdown links (`[text](./path)` or `[text](../path)`).
- **AC-18:** For each relative link, it resolves the path relative to the containing file. If the target does not exist → `medium` severity finding with the broken link and resolved path.

---

### 2.6 Feature Directory Consistency

**User Story:**
> As a developer, I want feature subdirectories under `specs/features/` to follow a consistent structure, so that feature-scoped pipeline runs work reliably.

**Acceptance Criteria:**

- **AC-19:** Each subdirectory of `specs/features/` must be kebab-case. Non-conforming names → `high` severity.
- **AC-20:** Each feature directory must contain a `prd.md`. Missing → `high` severity.
- **AC-21:** Missing `arch.md` in a feature directory → `low` severity (stub can be created by architect).
- **AC-22:** Missing `tasks.md` in a feature directory → `low` severity.

---

## 3. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Execution time | < 120 seconds |
| Idempotency | Safe to re-run; Spec Audit section updated in-place |
| Output stability | Same inputs always produce same findings |
| Pipeline integration | Runs as RolePlugin (priority 5, stage: SPEC_AUDIT) |
| Onboarding support | Works on projects not yet configured for SDD |

---

## 4. Dependencies

| Dependency | Type | Notes |
|------------|------|-------|
| `specs/prd.md` | Runtime input | Mandatory — pipeline blocks if missing |
| `specs/arch.md` | Runtime output | Created as stub if missing |
| Goose CLI | External | Executes the spec-linter recipe |
| `specs/recipes/spec-linter.yaml` | Recipe | Goose recipe for agent instructions |
| `SpecLinterRole` plugin | Internal | `src/sdd_server/plugins/roles/spec_linter.py` |
| Architect role | Downstream | `architect` declares `dependencies: ["spec-linter"]` |
