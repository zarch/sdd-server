# Tasks: SDD MCP Server

**Project:** sdd-server
**Date:** 2026-03-02

<!-- Task ID format: t<7hexchars> (e.g., ta3f2b1c) -->
<!-- Role recipes: run `goose run --recipe recipes/<role>.yaml` before implementation -->

---

## Project Overview

Specs-Driven Development (SDD) MCP Server - An MCP server that implements the SDD workflow with role-based spec reviews executed via Goose recipes.

---

## Phase 1: Foundation (COMPLETE)

**Status:** ✅ Complete (81% coverage, 95 tests)

| ID | Title | Status |
|----|-------|--------|
| t0000001 | Project scaffold (pyproject.toml, pre-commit, mypy) | ✅ |
| t0000002 | Core models (WorkflowState, FeatureState, ProjectState) | ✅ |
| t0000003 | Infrastructure (FileSystemClient, GitClient) | ✅ |
| t0000004 | Core services (SpecManager, MetadataManager, StartupValidator) | ✅ |
| t0000005 | Templates (prd.md, arch.md, tasks.md, context-hints) | ✅ |
| t0000006 | MCP server with FastMCP lifespan | ✅ |
| t0000007 | MCP tools (init, spec, feature, status) | ✅ |
| t0000008 | MCP resources (specs/*) | ✅ |
| t0000009 | CLI commands (sdd init, sdd preflight, sdd status) | ✅ |
| t0000010 | Recipe templates for 6 roles | ✅ |

---

## Phase 2: Plugin System & Role Engine (COMPLETE)

**Status:** ✅ Complete (83% coverage, 191 tests)

| ID | Title | Status |
|----|-------|--------|
| t0000050 | Plugin base classes (BasePlugin, RolePlugin) | ✅ |
| t0000051 | Plugin loader (discovery, entry points) | ✅ |
| t0000052 | Plugin registry (registration, dependencies) | ✅ |
| t0000053 | Built-in role plugins (6 roles) | ✅ |
| t0000054 | RoleEngine (dependency graph, execution order) | ✅ |
| t0000055 | RecipeGenerator (dynamic recipe generation) | ✅ |
| t0000056 | MCP review tools (sdd_review_*) | ✅ |
| t0000057 | MCP prompts (role-specific prompts) | ✅ |
| t0000058 | Server integration (register tools/prompts) | ✅ |

---

## Phase 3: Role Execution & AI Integration (COMPLETE)

**Status:** ✅ Complete (295+ tests)

| ID | Title | Priority | Status |
|----|-------|----------|--------|
| t0000100 | RoleExecutionPipeline (parallel execution) | high | ✅ |
| t0000101 | Goose session integration | high | ✅ |
| t0000102 | Result aggregation and reporting | medium | ✅ |
| t0000103 | Streaming progress updates | medium | ✅ |

---

## Phase 4: Enhanced Workflow

**Status:** ✅ Complete (5/5)

| ID | Title | Priority | Status |
|----|-------|----------|--------|
| t0000200 | Feature lifecycle management | high | ✅ |
| t0000201 | Task breakdown from specs | high | ✅ |
| t0000202 | Code generation from templates | medium | ✅ |
| t0000203 | Spec validation rules | medium | ✅ |
| t0000204 | Custom plugin support | low | ✅ |

---

## Phase 5: Production Readiness

**Status:** 🔲 Pending

| ID | Title | Priority | Status |
|----|-------|----------|--------|
| t0000300 | Error handling improvements | high | 🔲 |
| t0000301 | Logging and observability | high | 🔲 |
| t0000302 | Configuration management | medium | 🔲 |
| t0000303 | Documentation (API, usage) | medium | 🔲 |
| t0000304 | Performance optimization | low | 🔲 |
| t0000305 | Security hardening | high | 🔲 |

---

## Current Sprint

**Goal:** Phase 4 Complete - Ready for Phase 5: Production Readiness

### Completed in Phase 4

1. **t0000200: Feature Lifecycle Management** - Full lifecycle tracking with states and transitions
2. **t0000201: Task Breakdown from Specs** - Parse tasks from markdown and sync with specs
3. **t0000202: Code Generation from Templates** - Jinja2 templates for scaffolding code
4. **t0000203: Spec Validation Rules** - Configurable validation for PRD/ARCH/TASKS specs
5. **t0000204: Custom Plugin Support** - YAML/JSON-defined custom role plugins

---

## Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Test Coverage | 83% | 85% |
| Tests Passing | 191 | - |
| Source Files | 49 | - |
| Test Files | 30 | - |

---

## Notes

- Phase 2 added plugin architecture with 6 built-in roles
- Each role has a recipe template for Goose execution
- RoleEngine handles dependency-aware execution order
- RecipeGenerator creates dynamic recipes with context injection
