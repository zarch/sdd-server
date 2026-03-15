# Tasks: Spec Bootstrapper

**Feature:** spec-bootstrapper
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
| 1 | Feature specs + recipe written (this session) | ✅ Complete |
| 2 | Role reviews (all 11 roles) | ⬜ Pending |
| 3 | MCP tool implementation (`bootstrap.py`) | ✅ Complete |
| 4 | Server registration | ✅ Complete |
| 5 | Unit tests | 🔵 Partial (unit done; integration pending) |
| 6 | README update | ⬜ Pending |

---

## Completed

| ID | Title | Role | Completed |
|----|-------|------|-----------|
| tb3f0001 | Write feature specs: `specs/features/spec-bootstrapper/prd.md`, `arch.md`, `tasks.md` | developer | 2026-03-15 |
| tb3f0002 | Write Goose recipe: `specs/recipes/spec-bootstrapper.yaml` | developer | 2026-03-15 |
| tb3f0020 | Create `src/sdd_server/mcp/tools/bootstrap.py` — `sdd_bootstrap_specs` tool handler | developer | 2026-03-15 |
| tb3f0021 | Implement `update_existing` guard: check `specs/prd.md` existence, emit blocked envelope if needed | developer | 2026-03-15 |
| tb3f0022 | Implement `target_path` resolution and validation (path traversal safety) | developer | 2026-03-15 |
| tb3f0023 | Implement `max_features` parameter clamping (max 20) | developer | 2026-03-15 |
| tb3f0024 | Parse `RoleCompletionEnvelope` from recipe stdout and return as dict | developer | 2026-03-15 |
| tb3f0030 | Register `sdd_bootstrap_specs` in `src/sdd_server/mcp/server.py` | developer | 2026-03-15 |
| tb3f0040 | Write unit tests: `tests/unit/mcp/tools/test_bootstrap.py` — blocked guard, update mode, envelope parsing (17 tests) | developer | 2026-03-15 |

---

## In Progress

| ID | Title | Role | Started |
|----|-------|------|---------|

---

## Pending

<!-- Phase 2 — Role Reviews -->

| ID | Title | Role | Priority |
|----|-------|------|----------|
| tb3f0010 | Run all 11 role recipes against spec-bootstrapper feature specs | developer | high |

<!-- Phase 5 — Integration Tests -->

| ID | Title | Role | Priority |
|----|-------|------|----------|
| tb3f0041 | Write integration test: bootstrap on fixture with no specs → spec-linter returns `clean=true` | developer | high |
| tb3f0042 | Write integration test: bootstrap with `update_existing=false` when specs exist → blocked, no files changed | developer | high |
| tb3f0043 | Write integration test: bootstrap with `update_existing=true` → specs extended, original content intact | developer | high |
| tb3f0044 | Write integration test: bootstrap twice with `update_existing=true` → two `## Updated:` subsections, no duplication | developer | medium |
| tb3f0045 | Write integration test: fixture with >20 modules → exactly 20 feature dirs, rest in `omitted_features` | developer | medium |
| tb3f0046 | Achieve 80%+ coverage on `mcp/tools/bootstrap.py` | developer | high |

<!-- Phase 6 — README -->

| ID | Title | Role | Priority |
|----|-------|------|----------|
| tb3f0050 | Document `sdd_bootstrap_specs` MCP tool in README.md under "On-Demand Tools" | tech-writer | medium |
| tb3f0051 | Add "Onboarding an existing project" section to README.md with bootstrap → lint → pipeline workflow | tech-writer | medium |
