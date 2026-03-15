# Tasks: Spec Decomposer

**Feature:** spec-decomposer
**Date:** 2026-03-15
**Based on:** [prd.md](./prd.md) v1.0, [arch.md](./arch.md) v1.0
**Parent Tasks:** [specs/tasks.md](../../tasks.md)

---

## Role Review Checklist

Run each role recipe against this feature before moving implementation tasks to "In Progress".

- [ ] **Spec Linter** — `goose run --recipe specs/recipes/spec-linter.yaml`
- [ ] **Architect** — `goose run --recipe specs/recipes/architect.yaml`
- [ ] **UI/UX Designer** — `goose run --recipe specs/recipes/ui-designer.yaml`
- [ ] **Interface Designer** — `goose run --recipe specs/recipes/interface-designer.yaml`
- [ ] **Security Analyst** — `goose run --recipe specs/recipes/security-analyst.yaml`
- [ ] **Edge Case Analyst** — `goose run --recipe specs/recipes/edge-case-analyst.yaml`
- [ ] **Senior Developer** — `goose run --recipe specs/recipes/senior-developer.yaml`
- [ ] **QA Engineer** — `goose run --recipe specs/recipes/qa-engineer.yaml`
- [ ] **Tech Writer** — `goose run --recipe specs/recipes/tech-writer.yaml`
- [ ] **DevOps Engineer** — `goose run --recipe specs/recipes/devops-engineer.yaml`
- [ ] **Product Owner** — `goose run --recipe specs/recipes/product-owner.yaml`

---

## Phase Overview

| Phase | Title | Status |
|-------|-------|--------|
| 1 | Feature specs written (this file) | ✅ Complete |
| 2 | Role reviews (all 11 roles) | ⬜ Pending |
| 3 | Core decomposer engine (`SpecDecomposer` class) | ⬜ Pending |
| 4 | MCP tool registration (`sdd_decompose_specs`) | ⬜ Pending |
| 5 | Unit and integration tests | ⬜ Pending |

---

## Completed

| ID | Title | Role | Completed |
|----|-------|------|-----------|
| tb2f0001 | Write feature specs: `specs/features/spec-decomposer/prd.md`, `arch.md`, `tasks.md` | developer | 2026-03-15 |

---

## In Progress

| ID | Title | Role | Started |
|----|-------|------|---------|

---

## Pending

<!-- Phase 2 — Role Reviews -->

| ID | Title | Role | Priority |
|----|-------|------|----------|
| tb2f0010 | Run all 11 role recipes against spec-decomposer feature specs | developer | high |

<!-- Phase 3 — Core Engine -->

| ID | Title | Role | Priority |
|----|-------|------|----------|
| tb2f0020 | Create `src/sdd_server/core/spec_decomposer.py` — `SpecDecomposer` class with `detect_features()` and `decompose()` | developer | high |
| tb2f0021 | Implement `FeatureBoundary` and `DecompositionResult` Pydantic models in `src/sdd_server/models/` | developer | high |
| tb2f0022 | Implement heading-based feature boundary detection (Pass 1) | developer | high |
| tb2f0023 | Implement AC-grouping fallback feature detection (Pass 2) | developer | medium |
| tb2f0024 | Implement `_slugify()` with feature prefix stripping and kebab-case normalization | developer | high |
| tb2f0025 | Implement `_write_feature_prd()` with back-reference and AC preservation | developer | high |
| tb2f0026 | Implement `_write_feature_arch_stub()` with placeholder section | developer | medium |
| tb2f0027 | Implement `_write_feature_tasks_stub()` with full 11-role checklist | developer | medium |
| tb2f0028 | Implement `_patch_root_prd()` — add/update `## Feature Index` section (non-destructive) | developer | high |
| tb2f0029 | Implement idempotency: detect existing feature dirs, skip without `--force` | developer | high |
| tb2f0030 | Implement dry-run mode: return `DecompositionResult` without writing files | developer | medium |
| tb2f0031 | Cap maximum features at 50; report unassigned ACs and coverage percentage | developer | medium |

<!-- Phase 4 — MCP Tool -->

| ID | Title | Role | Priority |
|----|-------|------|----------|
| tb2f0040 | Create `src/sdd_server/mcp/tools/decompose.py` — `sdd_decompose_specs` tool handler | developer | high |
| tb2f0041 | Register `sdd_decompose_specs` in `src/sdd_server/mcp/server.py` | developer | high |
| tb2f0042 | Add `sdd_decompose_specs` to MCP tool reference in README.md | tech-writer | medium |

<!-- Phase 5 — Tests -->

| ID | Title | Role | Priority |
|----|-------|------|----------|
| tb2f0050 | Write unit tests: `tests/unit/core/test_spec_decomposer.py` — detection, slugify, dry-run, idempotency | developer | high |
| tb2f0051 | Write unit tests: `tests/unit/mcp/tools/test_decompose.py` — tool parameter validation, error handling | developer | medium |
| tb2f0052 | Write integration test: decompose → spec-linter validates output (clean=true) | developer | high |
| tb2f0053 | Write integration test: decompose → architect on single feature → arch.md populated | developer | medium |
| tb2f0054 | Write integration test: decompose twice → idempotent, no duplicate files | developer | medium |
| tb2f0055 | Achieve 80%+ coverage on `spec_decomposer.py` and `mcp/tools/decompose.py` | developer | high |
