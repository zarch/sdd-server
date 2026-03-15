# Architecture: Spec Decomposer

**Version:** 1.0
**Date:** 2026-03-15
**Status:** 🔵 Planned — Pending Implementation
**Parent Architecture:** [specs/arch.md](../../arch.md) — Section 3.1 (Specification Management)

---

## 1. Overview

The spec-decomposer is an **on-demand MCP tool**, not a `RolePlugin`. It does not participate in the standard pipeline cycle. Users invoke it explicitly via:

```
sdd_decompose_specs(dry_run=False, force=False, target_feature=None)
```

It reads `specs/prd.md`, detects feature boundaries, and creates the `specs/features/` subtree. The heavy lifting (parsing, feature extraction, file writing) is performed in Python — no Goose agent is involved, making it fast, deterministic, and testable without an AI client.

### Relationship to Other Components

```
sdd_decompose_specs (MCP tool)
    │
    ├── reads:   specs/prd.md (via SpecManager)
    ├── reads:   specs/arch.md (for back-reference metadata)
    ├── writes:  specs/features/<slug>/prd.md
    ├── writes:  specs/features/<slug>/arch.md  (stub)
    ├── writes:  specs/features/<slug>/tasks.md (stub)
    └── patches: specs/prd.md  (adds ## Feature Index)

    After decomposition, users typically run:
    └── spec-linter → validates the new feature directories
```

---

## 2. Component Design

### 2.1 MCP Tool

**File:** `src/sdd_server/mcp/tools/decompose.py`

```python
@mcp.tool()
async def sdd_decompose_specs(
    dry_run: bool = False,
    force: bool = False,
    target_feature: str | None = None,
) -> dict:
    """
    Decompose root specs/prd.md into feature-scoped specs/features/<slug>/ directories.

    Args:
        dry_run:        If True, return a preview without writing any files.
        force:          If True, overwrite existing feature directories.
        target_feature: If set, only decompose this feature (slug or heading text).

    Returns:
        {
          "status": "ok" | "dry_run" | "error",
          "features": [{"slug": ..., "title": ..., "acs": [...], "files_created": [...]}],
          "skipped": [{"slug": ..., "reason": "already_exists"}],
          "unassigned_acs": [...],
          "coverage_pct": 95.0,
        }
    """
```

**Registered in:** `src/sdd_server/mcp/server.py` alongside other MCP tools.

### 2.2 SpecDecomposer Engine

**File:** `src/sdd_server/core/spec_decomposer.py`

Encapsulates the decomposition algorithm. Keeps tool handler thin.

```python
class SpecDecomposer:
    def __init__(self, project_root: Path, spec_manager: SpecManager, fs: FileSystemClient):
        ...

    def detect_features(self, prd_content: str) -> list[FeatureBoundary]:
        """Parse prd.md and return feature boundaries with assigned AC IDs."""
        ...

    def decompose(
        self,
        dry_run: bool = False,
        force: bool = False,
        target: str | None = None,
    ) -> DecompositionResult:
        """Run full decomposition. Returns result without side effects if dry_run=True."""
        ...

    def _slugify(self, heading: str) -> str:
        """Convert heading text to kebab-case slug."""
        ...

    def _write_feature_prd(self, boundary: FeatureBoundary) -> Path:
        ...

    def _write_feature_arch_stub(self, boundary: FeatureBoundary) -> Path:
        ...

    def _write_feature_tasks_stub(self, boundary: FeatureBoundary) -> Path:
        ...

    def _patch_root_prd(self, features: list[FeatureBoundary]) -> None:
        """Add/update ## Feature Index section in root prd.md."""
        ...
```

### 2.3 Feature Boundary Detection Algorithm

The detector runs two passes over `prd.md`:

**Pass 1 — Heading-based detection:**
```
For each H2/H3 heading containing "Feature", "Section", or a numbered prefix (e.g. "3.1"):
    Collect all content (user stories, ACs) until the next same-level heading
    If content contains ≥ 1 AC-XX entry OR ≥ 1 "User Story:" block → candidate feature
```

**Pass 2 — AC grouping (fallback):**
```
If Pass 1 yields 0 or 1 features:
    Group consecutive AC-XX entries by their surrounding H3 heading
    Each group with ≥ 2 ACs becomes a feature boundary
```

**Slug generation:**
```python
def _slugify(heading: str) -> str:
    # Remove feature prefix: "Feature A: Auth" → "auth"
    # "3.1 Specification Management" → "specification-management"
    heading = re.sub(r'^(feature\s+\w+[:.]?\s*|[\d.]+\s*)', '', heading, flags=re.I)
    heading = heading.lower()
    heading = re.sub(r'[^a-z0-9]+', '-', heading)
    return heading.strip('-')
```

### 2.4 Data Models

```python
class FeatureBoundary(SDDBaseModel):
    slug: str               # kebab-case, e.g. "specification-management"
    title: str              # Original heading text
    acs: list[str]          # ["AC-01", "AC-02", ...]
    content_blocks: list[str]  # Raw markdown blocks (user stories, requirements)
    source_line_start: int
    source_line_end: int

class DecompositionResult(SDDBaseModel):
    features: list[FeatureBoundary]
    skipped: list[dict]         # [{"slug": ..., "reason": "already_exists"}]
    unassigned_acs: list[str]   # ACs found in prd.md but not assigned to any feature
    coverage_pct: float         # assigned_acs / total_acs * 100
    files_created: list[Path]   # Only populated when dry_run=False
    dry_run: bool
```

---

## 3. Integration Points

### 3.1 SpecManager

`SpecDecomposer` uses `SpecManager.read_spec()` and `SpecManager.write_spec()` for all file I/O. This ensures:
- Path traversal protection via `FileSystemClient`
- Atomic writes (no partial files on interruption)
- Consistent encoding handling

**Files:** `src/sdd_server/core/spec_manager.py`, `src/sdd_server/infrastructure/filesystem.py`

### 3.2 Spec Linter (post-decomposition)

After `sdd_decompose_specs` completes, the client should run the spec-linter to validate the new feature directories:

```python
# Recommended workflow in client code:
result = await sdd_decompose_specs()
if result["status"] == "ok":
    lint_result = await sdd_review_run(roles=["spec-linter"])
```

### 3.3 MCP Server Registration

**File:** `src/sdd_server/mcp/server.py`

`sdd_decompose_specs` is imported and registered alongside the other MCP tools in the server lifespan. It uses the same `AppContext` (`spec_manager`, `project_root`, `fs_client`).

### 3.4 Feature-Scoped Pipeline Runs

After decomposition, feature-scoped runs use `target` parameter:

```python
await sdd_review_run(roles=["architect"], target="specification-management")
# → reads specs/features/specification-management/prd.md as primary context
```

The `RoleEngine` passes `target` to each role's `review()` method, which includes it in the `invoke_context` dict sent to `ai_client.invoke_role()`.

---

## 4. Generated File Templates

### 4.1 Feature prd.md Template

```markdown
# Feature: {title}

**Version:** 1.0
**Date:** {date}
**Status:** 🔵 Decomposed from root PRD
**Parent PRD:** [specs/prd.md](../../prd.md)

> Decomposed by `sdd_decompose_specs` on {date}.
> Original section: "{heading}" (lines {start}–{end})

---

{content_blocks}
```

### 4.2 Feature arch.md Stub Template

```markdown
# Architecture: {title}

**Version:** 1.0
**Date:** {date}
**Status:** 🔵 Stub — Pending Architect Review
**Parent Architecture:** [specs/arch.md](../../arch.md)

> This stub was generated by `sdd_decompose_specs`.
> The Architect role will populate this file during the review cycle.

---

## Architecture

<!-- To be populated by the Architect role -->
<!-- Run: goose run --recipe specs/recipes/architect.yaml -->
```

### 4.3 Feature tasks.md Stub Template

```markdown
# Tasks: {title}

**Feature:** {slug}
**Date:** {date}
**Based on:** [prd.md](./prd.md) v1.0
**Parent Tasks:** [specs/tasks.md](../../tasks.md)

> This stub was generated by `sdd_decompose_specs`.

---

## Role Review Checklist

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

## Completed

| ID | Title | Role | Completed |
|----|-------|------|-----------|

---

## In Progress

| ID | Title | Role | Started |
|----|-------|------|---------|

---

## Pending

| ID | Title | Role | Priority |
|----|-------|------|----------|
```

---

## 5. Sequence Diagram

```
MCP Client              sdd_decompose_specs     SpecDecomposer      SpecManager / FS
    │                           │                    │                    │
    │── sdd_decompose_specs() ──►│                   │                    │
    │   dry_run=False            │── detect_features()──►│               │
    │                           │                    │── read prd.md ────►│
    │                           │                    │◄── content ────────│
    │                           │                    │ [parse headings]   │
    │                           │                    │ [assign ACs]       │
    │                           │◄── [FeatureBoundary list] ─────────────│
    │                           │                    │                    │
    │                           │── for each feature:│                    │
    │                           │   write_feature_prd()──►│              │
    │                           │                    │── write prd.md ───►│
    │                           │   write_arch_stub()──►│                │
    │                           │                    │── write arch.md ──►│
    │                           │   write_tasks_stub()──►│               │
    │                           │                    │── write tasks.md ─►│
    │                           │                    │                    │
    │                           │── patch_root_prd()──►│                 │
    │                           │                    │── patch prd.md ───►│
    │                           │                    │                    │
    │◄── DecompositionResult ───│                   │                    │
```

---

## 6. Testing Approach

### Unit Tests

**File:** `tests/unit/core/test_spec_decomposer.py` (to be created)

```python
class TestFeatureDetection:
    def test_detects_features_by_heading()
    def test_detects_features_by_ac_grouping_fallback()
    def test_slugify_removes_feature_prefix()
    def test_slugify_handles_special_chars()
    def test_minimum_ac_threshold_enforced()
    def test_maximum_features_capped_at_50()

class TestDecomposition:
    def test_dry_run_creates_no_files()
    def test_creates_feature_directories()
    def test_idempotent_skips_existing_dirs()
    def test_force_flag_overwrites()
    def test_patches_root_prd_with_feature_index()
    def test_unassigned_acs_reported()
    def test_coverage_pct_calculated()

class TestGeneratedFiles:
    def test_feature_prd_contains_back_reference()
    def test_feature_prd_preserves_ac_numbering()
    def test_arch_stub_has_placeholder_section()
    def test_tasks_stub_has_full_role_checklist()
```

### Integration Tests

**File:** `tests/integration/test_spec_decomposer.py` (to be created)

- Full round-trip: decompose root prd.md → spec-linter validates output (clean=true)
- Decompose → run architect on single feature → arch.md populated
- Idempotency: decompose twice → same result, no duplicate files
