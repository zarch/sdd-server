# Architecture: Spec Linter

**Version:** 1.0
**Date:** 2026-03-15
**Status:** ✅ Implemented
**Parent Architecture:** [specs/arch.md](../../arch.md) — Section 9.3 (Role Plugins)

---

## 1. Overview

The spec-linter is implemented as a `RolePlugin` with `priority=5` and `stage=SPEC_AUDIT`. It runs before all other roles and has no dependencies. The architect role now declares `dependencies=["spec-linter"]`, making it the mandatory entry point for every pipeline execution.

### Pipeline Position

```
spec-linter (5, SPEC_AUDIT)
    └── architect (10, ARCHITECTURE)
            ├── ui-designer (20)
            └── interface-designer (20)
                    └── security-analyst (30)
                            └── edge-case-analyst (40)
                                    └── senior-developer (50)
                                            ├── qa-engineer (60)
                                            ├── tech-writer (60)
                                            └── devops-engineer (60)
                                                    └── product-owner (80)
```

The spec-linter is also the recommended first command for onboarding an existing project:

```bash
goose run --recipe specs/recipes/spec-linter.yaml
```

---

## 2. Component Design

### 2.1 SpecLinterRole Plugin

**File:** `src/sdd_server/plugins/roles/spec_linter.py`

```python
class SpecLinterRole(RolePlugin):
    metadata = PluginMetadata(
        name="spec-linter",
        version="1.0.0",
        description="Pre-flight spec structure and consistency validator",
        author="SDD Team",
        priority=5,
        stage=RoleStage.SPEC_AUDIT,
        dependencies=[],  # First in chain
    )
```

The plugin delegates all validation logic to the Goose agent via `_run_with_ai_client()`. No Python-level file scanning is performed — the Goose agent does the analysis using the developer extension.

### 2.2 SPEC_AUDIT Stage

**File:** `src/sdd_server/plugins/base.py`

Added to `RoleStage(StrEnum)`:

```python
SPEC_AUDIT = "spec-audit"   # priority ~5 — before all other stages
ARCHITECTURE = "architecture"  # priority ~10
```

### 2.3 Architect Dependency Update

**File:** `src/sdd_server/plugins/roles/architect.py`

```python
metadata = PluginMetadata(
    name="architect",
    priority=10,
    stage=RoleStage.ARCHITECTURE,
    dependencies=["spec-linter"],  # was: []
)
```

### 2.4 Recipe

**File:** `specs/recipes/spec-linter.yaml`

9-step Goose agent workflow:
1. Check mandatory file (prd.md) → `blocked` if missing
2. Structure check (arch.md, tasks.md presence)
3. Required sections validation
4. AC ID cross-reference
5. Naming convention check
6. Broken relative link scan
7. Feature directory consistency
8. Write `## Spec Audit` to arch.md
9. Emit `RoleCompletionEnvelope`

Goose extensions used: `builtin:developer` (file read/write)
Timeout: 120 seconds
Max retries: 1

---

## 3. Integration Points

### 3.1 BUILTIN_ROLES Registration

**File:** `src/sdd_server/plugins/roles/__init__.py`

`SpecLinterRole` is the first entry in `BUILTIN_ROLES`:

```python
BUILTIN_ROLES = [
    SpecLinterRole,    # priority 5
    ArchitectRole,     # priority 10
    ...
]
```

Total built-in roles: **11** (was 10).

### 3.2 Plugin Registry

Because the registry enforces dependency ordering, `spec-linter` must be registered before `architect`. The `BUILTIN_ROLES` list ordering guarantees this when registered sequentially.

### 3.3 RoleEngine Execution

The `RoleEngine` reads the dependency graph and topologically sorts roles. With `architect` depending on `spec-linter`:

- `spec-linter` is always scheduled first
- A `blocked` or failed spec-linter result causes the engine to skip `architect` and all downstream roles

### 3.4 Recipe Generator

The `RecipeGenerator.generate_all_recipes()` now produces 11 recipes (was 10). Recipe ordering: spec-linter first, product-owner last.

---

## 4. Data Models

### 4.1 RoleCompletionEnvelope (spec-linter variant)

The spec-linter envelope adds a `clean` boolean field not present in other roles:

```json
{
  "sdd_role": "spec-linter",
  "status": "completed | blocked | needs_retry",
  "summary": "Spec audit complete — 3 findings (0 critical, 1 high, 2 medium, 0 low)",
  "clean": false,
  "findings": [
    {
      "file": "specs/prd.md",
      "issue": "No Acceptance Criteria section found",
      "severity": "high",
      "line": null,
      "recommendation": "Add '## Acceptance Criteria' section with AC-XX numbered entries"
    }
  ],
  "session_name": "sdd-spec-linter-default",
  "retry_hint": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `sdd_role` | string | Always `"spec-linter"` |
| `status` | enum | `completed`, `blocked`, `needs_retry` |
| `clean` | boolean | `true` only when `findings` is empty |
| `findings[].file` | string | Relative path from project root |
| `findings[].severity` | enum | `critical`, `high`, `medium`, `low` |
| `findings[].line` | int\|null | Line number if known |

### 4.2 Spec Audit Section (written to arch.md)

```markdown
## Spec Audit

### Audit Summary
Date: 2026-03-15
Status: ISSUES FOUND
Total findings: 3 (0 critical, 1 high, 2 medium, 0 low)

### Findings

| File | Issue | Severity | Recommendation |
|------|-------|----------|----------------|
| specs/prd.md | No Acceptance Criteria section | high | Add ## Acceptance Criteria |
| specs/tasks.md | AC-03 referenced but not defined in prd.md | medium | Add AC-03 to prd.md or remove reference |
| specs/features/auth/ | Missing arch.md | medium | Create arch.md stub |
```

---

## 5. Sequence Diagram

```
MCP Client          RoleEngine          SpecLinterRole      GooseSession
    │                   │                    │                   │
    │── sdd_review_run ─►│                   │                   │
    │                   │── execute(spec-linter) ──►│            │
    │                   │                    │── _run_with_ai_client()
    │                   │                    │── invoke_role() ──►│
    │                   │                    │                   │── goose session
    │                   │                    │                   │   --recipe spec-linter.yaml
    │                   │                    │                   │
    │                   │                    │                   │ [validates specs/]
    │                   │                    │                   │ [writes ## Spec Audit]
    │                   │                    │◄── SessionResult ─│
    │                   │◄── RoleResult ─────│                   │
    │                   │                    │                   │
    │                   │  [if blocked: skip architect + all downstream]
    │                   │  [if completed: schedule architect]
    │◄── review result ─│                   │                   │
```

---

## 6. Testing Approach

### Unit Tests

**File:** `tests/unit/plugins/test_plugins.py`

- `SpecLinterRole.metadata.priority == 5`
- `SpecLinterRole.metadata.stage == RoleStage.SPEC_AUDIT`
- `SpecLinterRole.get_dependencies() == []`
- `ArchitectRole.get_dependencies() == ["spec-linter"]`
- Registry ordering: spec-linter registered before architect
- `get_execution_order()` returns spec-linter at index 0

**File:** `tests/unit/core/test_recipe_generator.py`

- `len(paths) == 11`
- `paths[0].stem == "spec-linter"`
- `paths[1].stem == "architect"`

### Integration Tests

**File:** `tests/integration/test_goose_round_trip.py`

- Mocked subprocess: spec-linter `blocked` envelope halts architect scheduling
- Mocked subprocess: spec-linter `completed` envelope (clean=true) allows architect to proceed
- Mocked subprocess: spec-linter `completed` envelope (clean=false, findings present) still allows architect (non-blocking findings)
- Session name format: `sdd-spec-linter-<scope>`
