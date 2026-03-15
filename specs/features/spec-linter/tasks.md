# Tasks: Spec Linter

**Feature:** spec-linter
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
| 1 | Plugin and stage definition | ✅ Complete |
| 2 | Recipe authoring | ✅ Complete |
| 3 | Pipeline wiring (architect dependency, BUILTIN_ROLES) | ✅ Complete |
| 4 | Unit and integration test coverage | ✅ Complete |
| 5 | Feature specs written (this file) | ✅ Complete |

---

## Completed

| ID | Title | Role | Completed |
|----|-------|------|-----------|
| ta1f0001 | Add `RoleStage.SPEC_AUDIT = "spec-audit"` to `plugins/base.py` | developer | 2026-03-15 |
| ta1f0002 | Create `SpecLinterRole` plugin at `src/sdd_server/plugins/roles/spec_linter.py` | developer | 2026-03-15 |
| ta1f0003 | Add `SpecLinterRole` to `BUILTIN_ROLES` in `plugins/roles/__init__.py` (count: 10 → 11) | developer | 2026-03-15 |
| ta1f0004 | Update `ArchitectRole.dependencies` from `[]` to `["spec-linter"]` | developer | 2026-03-15 |
| ta1f0005 | Author `specs/recipes/spec-linter.yaml` (9-step workflow, output contract, 120s timeout) | developer | 2026-03-15 |
| ta1f0006 | Update unit tests: role count assertions 10 → 11, dependency chain, execution order | developer | 2026-03-15 |
| ta1f0007 | Update `test_plugins.py`: register spec-linter before architect in all test fixtures | developer | 2026-03-15 |
| ta1f0008 | Update `test_recipe_generator.py`: `names[0]=="spec-linter"`, `names[1]=="architect"` | developer | 2026-03-15 |
| ta1f0009 | Update `test_review.py`: dependency assertions, count 10 → 11 | developer | 2026-03-15 |
| ta1f0010 | Update `RolePlugin` docstring in `plugins/base.py` to list all 11 built-in roles | developer | 2026-03-15 |
| ta1f0011 | Write feature specs: `specs/features/spec-linter/prd.md`, `arch.md`, `tasks.md` | developer | 2026-03-15 |

---

## In Progress

| ID | Title | Role | Started |
|----|-------|------|---------|

---

## Pending

| ID | Title | Role | Priority |
|----|-------|------|----------|
| ta1f0020 | Add `test_spec_linter_role_metadata` unit test verifying priority=5, stage=SPEC_AUDIT, deps=[] | developer | medium |
| ta1f0021 | Add integration test: spec-linter `blocked` envelope halts entire pipeline | developer | medium |
| ta1f0022 | Add integration test: spec-linter `completed` (clean=false) still allows architect to run | developer | medium |
| ta1f0023 | Validate recipe against a real project with intentionally broken specs | qa-engineer | high |
| ta1f0024 | Run role review checklist (all 11 roles) against this feature's specs | developer | low |
