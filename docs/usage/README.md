# SDD Server Usage Guide

This guide covers how to use the SDD MCP Server in your development workflow.

## Table of Contents

- [Installation](#installation)
- [Starting the Server](#starting-the-server)
- [Project Initialization](#project-initialization)
- [Configuration](#configuration)
- [CLI Commands](#cli-commands)
- [MCP Integration](#mcp-integration)
- [Workflow Examples](#workflow-examples)

---

## Installation

### From Source

```bash
git clone https://github.com/block/sdd-server.git
cd sdd-server
uv sync
```

### With pip

```bash
pip install sdd-server
```

---

## Starting the Server

### Command Line

```bash
# Start with default settings
sdd-server

# Start with custom project root
SDD_PROJECT_ROOT=/path/to/project sdd-server

# Start with debug logging
SDD_LOG_LEVEL=DEBUG sdd-server
```

### As a Service

```bash
# Using systemd (Linux)
sudo systemctl enable sdd-server
sudo systemctl start sdd-server

# Using Docker
docker run -v /path/to/project:/project -e SDD_PROJECT_ROOT=/project sdd-server
```

---

## Project Initialization

### Using CLI

```bash
# Initialize a new project
sdd init my-project --description "My awesome project"

# Run preflight checks
sdd preflight

# Check project status
sdd status
```

### Using MCP Tools

```python
# Initialize via MCP
result = await sdd_init(
    project_name="my-project",
    description="My awesome project"
)
```

### Project Structure

After initialization, your project will have:

```
my-project/
├── specs/
│   ├── prd.md           # Product Requirements
│   ├── arch.md          # Architecture Design
│   ├── tasks.md         # Task Breakdown
│   ├── context-hints.md # AI Context
│   ├── features/        # Feature-specific specs
│   └── recipes/         # Generated Goose recipes
├── .sdd/
│   └── metadata.json    # Project state
└── .git/
    └── hooks/
        └── pre-commit   # Spec enforcement hook
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SDD_PROJECT_ROOT` | Project root directory | Current directory |
| `SDD_LOG_LEVEL` | Logging level | `INFO` |
| `SDD_LOG_FORMAT` | Log format | `json` or `text` |
| `SDD_CONFIG_FILE` | Config file path | `specs/config.yaml` |

### Configuration File

Create `specs/config.yaml`:

```yaml
server:
  host: "0.0.0.0"
  port: 8080
  debug: false

execution:
  max_parallel_roles: 4
  timeout_seconds: 300
  retry:
    max_attempts: 3
    backoff_factor: 2.0

logging:
  level: "INFO"
  format: "json"
  output: "stdout"

security:
  rate_limit:
    requests_per_second: 10
    burst_size: 20

observability:
  metrics:
    enabled: true
    port: 9090
  health_check:
    enabled: true
    path: "/health"
```

### Configuration Priority

1. **Environment variables** (highest priority)
2. **Configuration file** (YAML/JSON)
3. **Default values** (lowest priority)

---

## CLI Commands

### sdd init

Initialize a new SDD project.

```bash
sdd init <project_name> [options]

Options:
  --description, -d    Project description
  --root, -r          Project root directory
```

### sdd preflight

Run preflight validation checks.

```bash
sdd preflight
```

### sdd status

Show project status.

```bash
sdd status
```

---

## MCP Integration

### With Goose

Add to your Goose configuration:

```yaml
# ~/.config/goose/config.yaml
extensions:
  sdd:
    command: sdd-server
    env:
      SDD_PROJECT_ROOT: /path/to/project
```

### With Claude Desktop

Add to Claude Desktop config:

```json
{
  "mcpServers": {
    "sdd": {
      "command": "sdd-server",
      "env": {
        "SDD_PROJECT_ROOT": "/path/to/project"
      }
    }
  }
}
```

### With Other MCP Clients

The SDD Server implements the standard MCP protocol. Connect via:

- stdio transport (default)
- HTTP/SSE transport (with `--http` flag)

---

## Workflow Examples

### Starting a New Feature

```python
# 1. Create the feature
await sdd_feature_create(
    name="user-auth",
    description="User authentication system"
)

# 2. Write the PRD
await sdd_spec_write(
    spec_type="prd",
    feature="user-auth",
    content="# User Authentication PRD\n\n..."
)

# 3. Create the lifecycle
await sdd_lifecycle_create(
    feature_id="user-auth",
    initial_state="planned"
)

# 4. Add tasks
await sdd_task_add(
    title="Implement login",
    feature="user-auth",
    priority="high",
    role="developer"
)
```

### Running Reviews

```python
# List available roles
roles = await sdd_review_list()

# Run specific roles
result = await sdd_review_run(
    roles=["architect", "developer"],
    scope="all",
    parallel=True
)

# Check results
status = await sdd_review_status()
results = await sdd_review_results(role="architect")
```

### Tracking Progress

```python
# Get ready tasks
ready = await sdd_task_ready(feature="user-auth")

# Update task status
await sdd_task_set_status(
    task_id="t001",
    status="in_progress",
    feature="user-auth"
)

# Check progress
progress = await sdd_task_progress(feature="user-auth")
```

### Generating Code

```python
# List templates
templates = await sdd_codegen_list_templates()

# Scaffold a module
result = await sdd_codegen_scaffold(
    name="auth_service",
    description="Authentication service module",
    templates=["module", "test"],
    package_name="myapp"
)
```

### Validating Specs

```python
# Validate a single spec
result = await sdd_validate_spec(
    spec_type="prd",
    feature="user-auth"
)

# Validate entire project
report = await sdd_validate_project(include_features=True)
```

### Onboarding an Existing Project

Use this workflow when you have a codebase but no specs yet.

```python
# 1. Generate specs from existing code
result = await sdd_bootstrap_specs()
# result["status"] == "completed"
# result["generated"] == ["specs/prd.md", "specs/arch.md", ...]
# result["stats"]["features_detected"] == 4

# 2. If specs already exist, update them instead
result = await sdd_bootstrap_specs(update_existing=True)

# 3. Optionally limit feature stubs (max 20)
result = await sdd_bootstrap_specs(max_features=5)

# 4. Run the review pipeline — spec-linter validates first
review = await sdd_review_run(scope="all", parallel=True)
```

You can also invoke the bootstrapper directly without the MCP server:

```bash
goose run --recipe specs/recipes/spec-bootstrapper.yaml
```

### Decomposing a Monolithic PRD

Use this when `specs/prd.md` covers many features and you want per-feature subdirectories.

```python
# Preview what would be created (no files written)
result = await sdd_decompose_specs(dry_run=True)
# result["features_created"] == 5  (would create)
# result["coverage_pct"] == 87.5   (% of AC-XX assigned)

# Run the decomposition
result = await sdd_decompose_specs()
# Creates: specs/features/<slug>/prd.md + arch.md + tasks.md
# Patches: specs/prd.md with ## Feature Index section

# Decompose only one feature
result = await sdd_decompose_specs(target_feature="user-auth")

# Force overwrite of an existing feature directory
result = await sdd_decompose_specs(target_feature="payments", force=True)
```

---

## Best Practices

### Spec Organization

1. Keep root specs high-level
2. Use feature specs for detailed requirements
3. Update specs before implementation
4. Run validation regularly

### Task Management

1. Break large tasks into smaller ones
2. Use dependencies to order work
3. Update task status as you progress
4. Export tasks for tracking

### Review Workflow

1. Run reviews after spec changes
2. Address issues before implementation
3. Use parallel execution for speed
4. Reset between review sessions

### Configuration

1. Use environment variables for secrets
2. Version control config files
3. Use different configs per environment
4. Monitor with observability features
