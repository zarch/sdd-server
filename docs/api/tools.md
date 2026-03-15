# MCP Tools Reference

Complete reference for all MCP tools provided by the SDD Server.

## Table of Contents

- [Project Initialization](#project-initialization)
- [Spec Management](#spec-management)
- [Feature Management](#feature-management)
- [On-Demand Spec Analysis](#on-demand-spec-analysis)
- [Task Management](#task-management)
- [Review Tools](#review-tools)
- [Lifecycle Management](#lifecycle-management)
- [Code Generation](#code-generation)
- [Validation](#validation)
- [Status](#status)

---

## Project Initialization

### sdd_init

Initialize a new SDD project with the standard directory structure.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project_name` | string | Yes | Name of the project |
| `description` | string | No | Short project description |
| `project_root` | string | No | Override project root path |

**Returns:**

```json
{
  "success": true,
  "project_root": "/path/to/project",
  "warnings": [],
  "message": "Project 'my-project' initialized"
}
```

### sdd_preflight

Run preflight checks to validate the spec structure.

**Parameters:** None

**Returns:**

```json
{
  "allowed": true,
  "issues": [],
  "checks_passed": 1
}
```

---

## Spec Management

### sdd_spec_read

Read the content of a spec file.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `spec_type` | string | Yes | One of: `prd`, `arch`, `tasks`, `context-hints` |
| `feature` | string | No | Feature name for feature-level specs |

**Returns:**

```json
{
  "content": "# PRD Content...",
  "spec_type": "prd",
  "feature": ""
}
```

### sdd_spec_write

Write content to a spec file.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `spec_type` | string | Yes | One of: `prd`, `arch`, `tasks`, `context-hints` |
| `content` | string | Yes | The content to write |
| `feature` | string | No | Feature name for feature-level specs |
| `mode` | string | No | `overwrite` (default), `append`, or `prepend` |

### sdd_spec_list

List all spec files in the project.

**Parameters:** None

**Returns:**

```json
{
  "root": {
    "prd": true,
    "arch": true,
    "tasks": true,
    "context_hints": true
  },
  "features": ["auth", "payments"],
  "issues": []
}
```

---

## Feature Management

### sdd_feature_create

Create a new feature subdirectory under `specs/features/<name>`.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | Yes | Feature name (lowercase, hyphens allowed) |
| `description` | string | No | Short feature description |

### sdd_feature_list

List all features in the project.

**Parameters:** None

**Returns:**

```json
{
  "features": ["auth", "payments"],
  "count": 2
}
```

---

## On-Demand Spec Analysis

These tools operate outside the review pipeline and can be called at any time.

### sdd_bootstrap_specs

Reverse-engineer an existing codebase into SDD-compliant specs. Invokes the `spec-bootstrapper` Goose recipe which surveys the source tree, reads package manifests, mines test names for acceptance criteria, and generates `specs/prd.md`, `specs/arch.md`, and feature stubs.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `update_existing` | boolean | No | `false` | Extend existing specs instead of blocking. Feature directories are always skipped if they exist. |
| `target_path` | string | No | `"."` | Path to the project to bootstrap (resolved relative to `SDD_PROJECT_ROOT`). |
| `max_features` | integer | No | `20` | Max feature stubs to generate. Clamped to 20. |

**Returns:**

```json
{
  "status": "completed",
  "summary": "Bootstrap complete — prd.md + arch.md generated, 4 features detected",
  "mode": "generate",
  "generated": ["specs/prd.md", "specs/arch.md", "specs/features/auth/prd.md"],
  "skipped": [],
  "omitted_features": [],
  "stats": {
    "source_files_scanned": 42,
    "tests_analyzed": 15,
    "acs_generated": 12,
    "features_detected": 4
  }
}
```

**`status` values:**

| Value | Meaning |
|-------|---------|
| `completed` | Specs generated or updated successfully |
| `blocked` | `specs/prd.md` already exists and `update_existing=false` — pass `update_existing=true` to update |
| `needs_retry` | Recipe lost context mid-session; call again |
| `error` | Goose invocation failed or path traversal detected |

**Direct recipe invocation:**

```bash
goose run --recipe specs/recipes/spec-bootstrapper.yaml
```

---

### sdd_decompose_specs

Split a monolithic `specs/prd.md` into per-feature subdirectories under `specs/features/`. Detects feature boundaries via H2/H3 headings and AC groupings, then writes `prd.md`, `arch.md`, and `tasks.md` stubs for each feature. Patches the root `prd.md` with a `## Feature Index` section.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `dry_run` | boolean | No | `false` | Return a result without writing any files |
| `force` | boolean | No | `false` | Overwrite existing feature directories |
| `target_feature` | string | No | `null` | Decompose only this feature (slug or heading text). Decomposes all if omitted. |

**Returns:**

```json
{
  "status": "ok",
  "features_created": 3,
  "features_skipped": 1,
  "files_created": [
    "specs/features/auth/prd.md",
    "specs/features/auth/arch.md",
    "specs/features/auth/tasks.md"
  ],
  "skipped": [{"slug": "payments", "reason": "already_exists"}],
  "unassigned_acs": ["AC-07"],
  "coverage_pct": 91.7,
  "dry_run": false
}
```

**Notes:**
- Feature directories that already exist are always skipped unless `force=true`
- Maximum 50 features per run
- `coverage_pct` shows what percentage of AC-XX identifiers in `prd.md` were assigned to a feature

---

## Task Management

### sdd_task_add

Add a new task.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `title` | string | Yes | Task title |
| `description` | string | No | Task description |
| `feature` | string | No | Feature to add task to |
| `priority` | string | No | `low`, `medium`, `high`, `critical` |
| `role` | string | No | Associated role |
| `dependencies` | string[] | No | Task IDs this depends on |
| `tags` | string[] | No | Tags for categorization |
| `ai_prompt` | string | No | AI prompt for execution |

### sdd_task_get

Get a task by ID.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `task_id` | string | Yes | Task ID |
| `feature` | string | No | Feature to search in |

### sdd_task_update

Update a task.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `task_id` | string | Yes | Task ID |
| `feature` | string | No | Feature the task belongs to |
| `title` | string | No | New title |
| `description` | string | No | New description |
| `priority` | string | No | New priority |
| `role` | string | No | New role |
| `dependencies` | string[] | No | New dependencies |
| `tags` | string[] | No | New tags |
| `ai_prompt` | string | No | New AI prompt |

### sdd_task_set_status

Set the status of a task.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `task_id` | string | Yes | Task ID |
| `status` | string | Yes | `pending`, `in_progress`, `complete`, `blocked`, `cancelled` |
| `feature` | string | No | Feature the task belongs to |
| `reason` | string | No | Reason for status change |

### sdd_task_remove

Remove a task.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `task_id` | string | Yes | Task ID |
| `feature` | string | No | Feature the task belongs to |

### sdd_task_list

List tasks with optional filters.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `feature` | string | No | Feature to list from |
| `status` | string | No | Filter by status |
| `priority` | string | No | Filter by priority |
| `tag` | string | No | Filter by tag |

### sdd_task_ready

Get tasks ready to start (pending with dependencies met).

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `feature` | string | No | Feature to check |

### sdd_task_dependencies

Get dependency information for a task.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `task_id` | string | Yes | Task ID |
| `feature` | string | No | Feature the task belongs to |

**Returns:**

```json
{
  "task_id": "t001",
  "dependencies": [...],
  "pending_ids": [],
  "can_start": true
}
```

### sdd_task_progress

Get progress statistics.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `feature` | string | No | Feature to get progress for |

### sdd_task_sync

Sync tasks from tasks.md spec file.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `feature` | string | No | Feature to sync |

### sdd_task_export

Export tasks to markdown format.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `feature` | string | No | Feature to export |

---

## Review Tools

### sdd_review_list

List all available review roles.

**Parameters:** None

**Returns:**

```json
{
  "roles": [
    {
      "name": "architect",
      "version": "1.0.0",
      "description": "Reviews system architecture",
      "stage": "planning",
      "dependencies": [],
      "priority": 10
    }
  ],
  "count": 6
}
```

### sdd_review_run

Run role-based code reviews.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `roles` | string[] | No | Role names to run (all if empty) |
| `scope` | string | No | `specs`, `code`, or `all` |
| `target` | string | No | Feature to focus on |
| `parallel` | boolean | No | Run in parallel (default: true) |

### sdd_review_status

Get current review engine status.

**Parameters:** None

### sdd_review_results

Get detailed results from role reviews.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `role` | string | No | Role to get results for |

### sdd_review_reset

Reset the review engine state.

**Parameters:** None

### sdd_recipes_generate

Generate Goose YAML recipes for all roles.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project_name` | string | Yes | Project name |
| `description` | string | No | Project description |
| `overwrite` | boolean | No | Overwrite existing |

### sdd_recipe_render

Render a single role recipe template.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `role` | string | Yes | Role name |
| `project_name` | string | Yes | Project name |
| `description` | string | No | Project description |

---

## Lifecycle Management

### sdd_lifecycle_create

Create a new feature lifecycle.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `feature_id` | string | Yes | Feature identifier |
| `initial_state` | string | No | Initial state (default: `planned`) |

**States:** `planned`, `in_progress`, `review`, `complete`, `archived`

### sdd_lifecycle_get

Get lifecycle state for a feature.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `feature_id` | string | Yes | Feature identifier |

### sdd_lifecycle_transition

Transition a feature to a new state.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `feature_id` | string | Yes | Feature identifier |
| `new_state` | string | Yes | Target state |
| `reason` | string | No | Reason for transition |
| `actor` | string | No | Who initiated |

### sdd_lifecycle_list

List all features with lifecycle states.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `state` | string | No | Filter by state |

### sdd_lifecycle_summary

Get summary of features in each state.

**Parameters:** None

### sdd_lifecycle_history

Get transition history for a feature.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `feature_id` | string | Yes | Feature identifier |

### sdd_lifecycle_metrics

Get metrics for a feature lifecycle.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `feature_id` | string | Yes | Feature identifier |

### sdd_lifecycle_archive

Archive a feature.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `feature_id` | string | Yes | Feature identifier |
| `reason` | string | No | Reason for archiving |

### sdd_lifecycle_can_transition

Check if a transition is valid.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `feature_id` | string | Yes | Feature identifier |
| `target_state` | string | Yes | Target state |

---

## Code Generation

### sdd_codegen_list_templates

List all available code templates.

**Parameters:** None

### sdd_codegen_generate

Generate a file from a template.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `template_name` | string | Yes | Template to use |
| `context` | object | No | Template variables |
| `output_path` | string | No | Output path |
| `overwrite` | boolean | No | Overwrite existing |
| `dry_run` | boolean | No | Preview only |

### sdd_codegen_preview

Preview generated code without writing.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `template_name` | string | Yes | Template to use |
| `context` | object | No | Template variables |

### sdd_codegen_scaffold

Scaffold a new feature with multiple files.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | Yes | Feature/module name |
| `description` | string | No | Description |
| `templates` | string[] | No | Template types |
| `output_dir` | string | No | Output directory |
| `package_name` | string | No | Package name |
| `author` | string | No | Author name |
| `overwrite` | boolean | No | Overwrite existing |
| `dry_run` | boolean | No | Preview only |

### sdd_codegen_generate_from_string

Generate from a custom template string.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `template_content` | string | Yes | Jinja2 template |
| `context` | object | No | Template variables |
| `output_path` | string | Yes | Output path |
| `overwrite` | boolean | No | Overwrite existing |
| `dry_run` | boolean | No | Preview only |

---

## Validation

### sdd_validate_spec

Validate a single spec file.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `spec_type` | string | Yes | Spec type |
| `feature` | string | No | Feature name |

### sdd_validate_feature

Validate all specs for a feature.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `feature` | string | Yes | Feature name |

### sdd_validate_project

Validate all specs in the project.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `include_features` | boolean | No | Include features |

### sdd_list_validation_rules

List all validation rules.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `spec_type` | string | No | Filter by spec type |

### sdd_add_validation_rule

Add a custom validation rule.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `rule_id` | string | Yes | Unique rule ID |
| `name` | string | Yes | Rule name |
| `description` | string | Yes | Description |
| `rule_type` | string | Yes | Rule type |
| `spec_types` | string | Yes | Comma-separated spec types |
| `severity` | string | No | Severity level |
| `section` | string | No | Section name |
| `pattern` | string | No | Regex pattern |

---

## Status

### sdd_status

Return current project status.

**Parameters:** None

**Returns:**

```json
{
  "workflow_state": "development",
  "features": ["auth", "payments"],
  "feature_count": 2,
  "bypass_count": 0,
  "spec_issues": [],
  "issues_count": 0
}
```
