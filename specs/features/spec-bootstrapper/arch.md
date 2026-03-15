# Architecture: Spec Bootstrapper

**Version:** 1.0
**Date:** 2026-03-15
**Status:** 🔵 Planned — Pending Implementation
**Parent Architecture:** [specs/arch.md](../../arch.md) — Section 3.1 (Specification Management)

---

## 1. Overview

The spec-bootstrapper is an **on-demand Goose recipe**, not a `RolePlugin`. It does not participate
in the standard pipeline cycle. Users invoke it explicitly:

```
# Direct invocation
goose run --recipe specs/recipes/spec-bootstrapper.yaml

# Future: via MCP tool
sdd_bootstrap_specs(update_existing=False, target_path=".", max_features=20)
```

Unlike the spec-decomposer (which splits an existing PRD), the spec-bootstrapper **generates specs
from source code** when none exist. The heavy lifting is performed by the Goose agent reading the
filesystem — there is no Python parsing engine. This makes it slower than the decomposer but
capable of operating on any language or framework without language-specific parsers.

### Relationship to Other Components

```
spec-bootstrapper (Goose recipe)
    │
    ├── reads:   src/ (source tree walk)
    ├── reads:   tests/ (test name extraction)
    ├── reads:   pyproject.toml / package.json / go.mod / Cargo.toml (dependency analysis)
    ├── reads:   README.md + existing docs (written requirements)
    ├── reads:   git log --oneline (feature timeline)
    ├── writes:  specs/prd.md                       (generate or update)
    ├── writes:  specs/arch.md                      (generate or update)
    └── writes:  specs/features/<slug>/prd.md       (generate only, skip if exists)
                 specs/features/<slug>/arch.md      (generate only, skip if exists)

    After bootstrap, recommended workflow:
    └── spec-linter → validates generated specs
    └── architect   → enriches specs/arch.md
    └── full pipeline
```

---

## 2. Recipe Design

### 2.1 MCP Tool (Future)

**File:** `src/sdd_server/mcp/tools/bootstrap.py` — **pending implementation**

```python
@mcp.tool()
async def sdd_bootstrap_specs(
    update_existing: bool = False,
    target_path: str = ".",
    max_features: int = 20,
) -> dict:
    """
    Reverse-engineer an existing codebase into SDD-compliant specs.

    Args:
        update_existing: If True, extend existing specs instead of blocking.
        target_path:     Project root to analyze (default: current directory).
        max_features:    Maximum number of feature directories to generate (max 20).

    Returns:
        RoleCompletionEnvelope dict from the recipe execution.
    """
```

**Registered in:** `src/sdd_server/mcp/server.py` (pending).

**Invocation chain:**
```
MCP client
    │── sdd_bootstrap_specs(update_existing, target_path, max_features)
    │       └── ai_client.invoke_role("spec-bootstrapper", context)
    │               └── GooseClientBridge.run_recipe(
    │                       recipe="specs/recipes/spec-bootstrapper.yaml",
    │                       params={
    │                           "update_existing": update_existing,
    │                           "project_root": target_path,
    │                           "max_features": max_features,
    │                       }
    │                   )
    └── returns RoleCompletionEnvelope
```

### 2.2 Recipe Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `update_existing` | bool | `false` | Extend existing specs instead of blocking |
| `project_root` | string | `.` | Absolute path to project root |
| `max_features` | int | `20` | Cap on generated feature directories |
| `session_name` | string | `sdd-spec-bootstrapper-default` | Goose session name (injected by orchestrator) |

### 2.3 10-Step Agent Workflow

The recipe instructs the Goose agent to execute these steps in order:

| Step | Name | Description |
|------|------|-------------|
| 1 | Mode detection | Check if `specs/prd.md` exists → `"generate"` or `"update"` mode |
| 2 | Codebase survey | Walk source tree: languages, frameworks, entry points, module boundaries |
| 3 | Dependency analysis | Read package manifests (`pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`) |
| 4 | Test mining | Extract test function names → infer AC-XX acceptance criteria |
| 5 | Git history scan | `git log --oneline` → infer delivered features from commit messages |
| 6 | README scan | Extract written requirements and descriptions |
| 7 | Feature boundary detection | Identify top-level module/package groupings → candidate features (max 20) |
| 8 | Generate/update `specs/prd.md` | Write user stories + AC-XX; preserve content in update mode |
| 9 | Generate/update `specs/arch.md` | Write component inventory + tech stack; preserve content in update mode |
| 10 | Generate `specs/features/<slug>/` | Per-feature prd.md + arch.md stubs; skip existing dirs |
| 11 | Emit envelope | Mandatory final JSON line (`RoleCompletionEnvelope`) |

---

## 3. Completion Envelope Schema

The recipe emits a `RoleCompletionEnvelope` as its mandatory last line. The spec-bootstrapper
extends the base envelope with `mode`, `generated`, `skipped`, and `stats` fields:

```json
{
  "sdd_role": "spec-bootstrapper",
  "status": "completed | blocked | needs_retry",
  "summary": "Bootstrap complete — prd.md + arch.md generated, 4 features detected",
  "mode": "generate | update",
  "generated": [
    "specs/prd.md",
    "specs/arch.md",
    "specs/features/auth/prd.md",
    "specs/features/auth/arch.md"
  ],
  "skipped": [
    {"path": "specs/features/api/prd.md", "reason": "feature_dir_exists"}
  ],
  "omitted_features": ["very-large-module", "another-module"],
  "stats": {
    "source_files_scanned": 42,
    "tests_analyzed": 15,
    "acs_generated": 12,
    "features_detected": 4
  },
  "session_name": "sdd-spec-bootstrapper-default",
  "retry_hint": null
}
```

**Status rules:**

| Condition | Status |
|-----------|--------|
| `specs/prd.md` does not exist | `"completed"` (generate mode) |
| `specs/prd.md` exists + `update_existing=false` | `"blocked"` |
| `specs/prd.md` exists + `update_existing=true` | `"completed"` (update mode) |
| Agent loses context mid-session | `"needs_retry"` with `retry_hint` |

---

## 4. Generated File Templates

### 4.1 Generated `specs/prd.md`

```markdown
# Product Requirements: <Project Name>

**Version:** 1.0
**Date:** <date>
**Status:** 🔵 Bootstrapped — Pending Human Review
**Generated by:** `spec-bootstrapper` on <date>

> This file was generated by the SDD spec-bootstrapper by analyzing the project codebase.
> Review and refine before running the full pipeline.

---

## 1. Overview

<summary derived from README.md or inferred from source tree>

---

## 2. User Stories

<user stories inferred from test names and git history>

---

## 3. Acceptance Criteria

<AC-XX entries mined from test function names>
```

### 4.2 Generated `specs/arch.md`

```markdown
# Architecture: <Project Name>

**Version:** 1.0
**Date:** <date>
**Status:** 🔵 Bootstrapped — Pending Architect Review
**Generated by:** `spec-bootstrapper` on <date>

> This file was generated by the SDD spec-bootstrapper.
> The Architect role will enrich this file during the review cycle.

---

## Architecture

### Tech Stack

<detected languages, frameworks, and runtimes from package manifests>

### Component Inventory

<top-level modules/packages with one-line descriptions>

### Data Flow

<!-- To be populated by the Architect role -->
```

### 4.3 Feature prd.md Stub

```markdown
# Feature: <Module Name>

**Version:** 1.0
**Date:** <date>
**Status:** 🔵 Bootstrapped — Pending Human Review
**Parent PRD:** [specs/prd.md](../../prd.md)

> Bootstrapped from module `<path>` by `spec-bootstrapper` on <date>.
> Review and complete this stub before running the architect role.

---

## Acceptance Criteria

<!-- To be populated: add AC-XX entries for this feature -->
```

### 4.4 Feature arch.md Stub

```markdown
# Architecture: <Module Name>

**Version:** 1.0
**Date:** <date>
**Status:** 🔵 Stub — Pending Architect Review
**Parent Architecture:** [specs/arch.md](../../arch.md)

> This stub was generated by `spec-bootstrapper`.
> The Architect role will populate this file during the review cycle.

---

## Architecture

<!-- To be populated by the Architect role -->
<!-- Run: goose run --recipe specs/recipes/architect.yaml -->
```

---

## 5. Sequence Diagram

```
MCP Client            sdd_bootstrap_specs     GooseClientBridge     Goose Agent (recipe)
    │                         │                      │                      │
    │── sdd_bootstrap_specs() ►│                     │                      │
    │   update_existing=False  │── invoke_role() ────►│                     │
    │                         │                      │── run_recipe() ─────►│
    │                         │                      │   (10-step workflow) │
    │                         │                      │                      │── read src/
    │                         │                      │                      │── read tests/
    │                         │                      │                      │── read manifests
    │                         │                      │                      │── git log
    │                         │                      │                      │── write specs/
    │                         │                      │◄── envelope (JSON) ──│
    │◄── RoleCompletionEnvelope│                     │                      │
```

---

## 6. Integration Points

### 6.1 Spec Linter (post-bootstrap)

The spec-linter must pass after bootstrap before any pipeline roles run:

```python
result = await sdd_bootstrap_specs()
if result["status"] == "completed":
    lint_result = await sdd_review_run(roles=["spec-linter"])
    # lint_result["clean"] should be True before proceeding
```

### 6.2 GooseClientBridge

**File:** `src/sdd_server/infrastructure/goose_client.py`

The MCP tool invokes the recipe via `GooseClientBridge.run_recipe()`, which handles session naming,
parameter injection, and envelope extraction from stdout.

### 6.3 Post-Bootstrap Workflow

Recommended sequence after a successful bootstrap:

```
spec-bootstrapper → spec-linter → architect → full 11-role pipeline
```

The architect role will populate the `## Data Flow` section and enrich feature `arch.md` stubs.

---

## 7. Testing Approach

### Unit Tests

**File:** `tests/unit/mcp/tools/test_bootstrap.py` (pending)

```python
class TestBootstrapTool:
    def test_blocked_when_prd_exists_and_update_false()
    def test_update_mode_invoked_when_update_existing_true()
    def test_max_features_param_passed_to_recipe()
    def test_envelope_parsed_from_recipe_output()

class TestEnvelopeParsing:
    def test_generated_list_extracted()
    def test_skipped_list_extracted()
    def test_stats_dict_extracted()
    def test_needs_retry_propagated()
```

### Integration Tests

**File:** `tests/integration/test_spec_bootstrapper.py` (pending)

- Full round-trip on a fixture project with no specs → spec-linter returns `clean=true`
- Run with `update_existing=false` when specs exist → `blocked`, no files changed
- Run with `update_existing=true` → specs extended, original content intact
- Run twice with `update_existing=true` → two `## Updated:` subsections, no content lost
- Fixture project with >20 modules → exactly 20 feature dirs created, rest in `omitted_features`
