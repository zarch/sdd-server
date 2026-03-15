# SDD MCP Server

**Specs-Driven Development** — an MCP server that enforces writing specifications before implementation and orchestrates a pipeline of AI review agents (via [Goose](https://github.com/block/goose)) that progressively build and verify your project's architecture, security posture, documentation, and release readiness.

---

## Table of Contents

1. [What is SDD?](#what-is-sdd)
2. [How it works](#how-it-works)
3. [Prerequisites](#prerequisites)
4. [Installation](#installation)
5. [Connecting to an AI client](#connecting-to-an-ai-client)
6. [Starting the server](#starting-the-server)
7. [First project walkthrough](#first-project-walkthrough)
8. [Onboarding an existing project](#onboarding-an-existing-project)
9. [MCP tool reference](#mcp-tool-reference)
10. [The 11-role pipeline](#the-11-role-pipeline)
11. [Role completion envelopes](#role-completion-envelopes)
12. [Environment variables](#environment-variables)
13. [Custom plugins](#custom-plugins)
14. [Development](#development)

---

## What is SDD?

Specs-Driven Development is a workflow that enforces a simple rule: **specs come before code**.

Before any feature can be committed, the project must have:
- A Product Requirements Document (`specs/prd.md`)
- An Architecture document (`specs/arch.md`)
- A Task breakdown (`specs/tasks.md`)

A git pre-commit hook installed by `sdd_init` blocks commits that violate this rule. The MCP server provides tools for AI assistants (Claude, Goose, etc.) to read and write specs, run review agents, manage tasks, generate code scaffolding, and track project state — all through the Model Context Protocol.

---

## How it works

```
Developer writes PRD  ─── or ───  sdd_bootstrap_specs (existing codebase)
        │                                     │
        ▼                                     ▼
  sdd_init / sdd_spec_write        specs/prd.md + arch.md generated
        │                                     │
        └──────────────┬──────────────────────┘
                       │
                       ▼
           sdd_decompose_specs (optional)
           Splits monolithic PRD into specs/features/<slug>/
                       │
                       ▼
  sdd_review_run  ──────────────────────────────────────────────────────────┐
        │                                                                    │
        ▼                                                                    │
  Spec Linter (priority 5)                                                  │
  Validates prd.md / arch.md structure before pipeline starts              │
        │                                                                    │
        ▼                                                                    │
  Architect (priority 10)                                                   │
  Reads prd.md → writes arch.md component design                           │
        │                                                                    │
        ├──────────────────────┐                                            │
        ▼                      ▼                                            │
  Interface Designer (20)   UI/UX Designer (20)                            │
  API contracts, schemas    User flows, WCAG 2.1                           │
        │                                                                    │
        ▼                                                                    │
  Security Analyst (30)                                                     │
  OWASP Top 10, threat model, CVE scan                                     │
        │                                                                    │
        ▼                                                                    │
  Edge Case Analyst (40)                                                    │
  User/data/process/security edge cases + test scenarios                   │
        │                                                                    │
        ▼                                                                    │
  Senior Developer (50)                                                     │
  Code quality, security implementation, test coverage                     │
        │                                                                    │
        ├───────────────┬───────────────┐                                   │
        ▼               ▼               ▼                                   │
  QA Engineer (60)  Tech Writer (60)  DevOps Engineer (60)                 │
  Acceptance tests  API docs/README   CI/CD, Dockerfile                   │
        └───────────────┴───────────────┘                                   │
                        │                                                    │
                        ▼                                                    │
              Product Owner (80)                                             │
              SHIP / HOLD verdict ──────────────────────────────────────────┘

Each role emits a RoleCompletionEnvelope as its last output line.
The orchestrator verifies the envelope before marking the role complete.
```

Each role is a [Goose recipe](specs/recipes/) executed in a named, resumable session (`goose session --name sdd-{role}-{scope} --resume`). If a role loses context mid-session it emits `"status": "needs_retry"` and the orchestrator can fork a fresh session.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | 3.14 recommended |
| [uv](https://github.com/astral-sh/uv) | latest | Fast package manager |
| [Goose CLI](https://github.com/block/goose) | latest | Required for AI role reviews |
| Git | any | Pre-commit hook uses it |

Install Goose:
```bash
curl -fsSL https://github.com/block/goose/releases/latest/download/install.sh | bash
```

---

## Installation

```bash
# From source (recommended during development)
git clone https://github.com/block/sdd-server.git
cd sdd-server
uv sync

# Run the server directly
uv run sdd-server

# Or install into your environment
uv pip install -e .
sdd-server
```

---

## Connecting to an AI client

The SDD server is an MCP server. Connect it to any MCP-compatible AI client.

### Claude Desktop

Add to `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "sdd": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/sdd-server", "sdd-server"],
      "env": {
        "SDD_PROJECT_ROOT": "/path/to/your/project"
      }
    }
  }
}
```

### Goose

Add to `~/.config/goose/config.yaml`:

```yaml
extensions:
  sdd:
    type: stdio
    cmd: uv
    args:
      - run
      - --directory
      - /path/to/sdd-server
      - sdd-server
    env:
      SDD_PROJECT_ROOT: /path/to/your/project
    enabled: true
```

### Any MCP client (stdio)

```bash
SDD_PROJECT_ROOT=/path/to/your/project uv run sdd-server
```

The server speaks MCP over stdin/stdout.

---

## Starting the server

```bash
# Default — uses current directory as project root
sdd-server

# Explicit project root
SDD_PROJECT_ROOT=/path/to/project sdd-server

# With debug logging
SDD_LOG_LEVEL=DEBUG SDD_PROJECT_ROOT=/path/to/project sdd-server

# With a specific AI provider
SDD_AI_CLIENT=goose SDD_PROJECT_ROOT=/path/to/project sdd-server
```

On startup the server:
1. Validates that Goose is reachable (logs a warning if not — non-fatal)
2. Loads custom plugins from `specs/plugins/` (if any)
3. Registers a filesystem health check for `SDD_PROJECT_ROOT`
4. Yields the MCP context with all tools and resources available

---

## First project walkthrough

### 1. Initialize the project

Call `sdd_init` from your AI client:

```
sdd_init(project_name="my-app", description="E-commerce platform")
```

This creates:
```
my-project/
├── specs/
│   ├── prd.md              ← fill this in with your requirements
│   ├── arch.md             ← populated by the Architect role
│   ├── tasks.md            ← populated during planning
│   ├── context-hints.md    ← optional AI hints
│   ├── features/           ← per-feature subdirectories
│   └── recipes/            ← Goose YAML recipes (one per role)
└── .sdd/
    └── metadata.json       ← project state
```

And installs a pre-commit git hook that runs `sdd_preflight` before every commit.

### 2. Write your PRD

```
sdd_spec_write(
    spec_type="prd",
    content="# My App\n\n## Goals\n...\n\n## Acceptance Criteria\n..."
)
```

Or edit `specs/prd.md` directly.

### 3. Create a feature (optional)

For feature-scoped reviews:

```
sdd_feature_create(name="user-auth", description="JWT authentication")
```

This creates `specs/features/user-auth/` with its own `prd.md`, `arch.md`, and `tasks.md`.

### 4. Run the review pipeline

```
sdd_review_run(scope="all", parallel=True)
```

Or target a single feature:

```
sdd_review_run(scope="all", target="user-auth", parallel=True)
```

Or run specific roles only:

```
sdd_review_run(roles=["architect", "security-analyst"], scope="specs")
```

Roles run in dependency order. Independent roles (e.g. Interface Designer and UI Designer) run in parallel when `parallel=True`.

Each role:
- Launches `goose session --name sdd-{role}-{scope} --resume`
- Pipes its YAML recipe as stdin
- Reads and updates `specs/arch.md`
- Emits a `RoleCompletionEnvelope` JSON as its last output line
- The server verifies the envelope before marking the role complete

### 5. Check review status

```
sdd_review_status()
```

Returns which roles are running, completed, or failed, plus a dependency graph.

### 6. Get detailed results

```
sdd_review_results()              # all roles
sdd_review_results(role="architect")  # single role
```

### 7. Check preflight before committing

```
sdd_preflight()
```

Returns `allowed: true/false`. The git hook calls this automatically before each commit.

---

## Onboarding an existing project

If you already have a codebase but no specs, use `sdd_bootstrap_specs` to reverse-engineer them:

### 1. Generate specs from code

```
sdd_bootstrap_specs()
```

This invokes the `spec-bootstrapper` Goose recipe which:
- Scans your source tree (languages, frameworks, entry points)
- Reads package manifests (`pyproject.toml`, `package.json`, `go.mod`, …)
- Mines test names and docstrings for acceptance criteria
- Scans git history and README for feature intent
- Generates `specs/prd.md`, `specs/arch.md`, and up to 20 `specs/features/<slug>/` stubs

If specs already exist, the tool returns `status: "blocked"` to prevent accidental overwrite. Pass `update_existing=True` to extend them instead.

### 2. Decompose a monolithic PRD (optional)

If your `specs/prd.md` covers many features in a single document:

```
sdd_decompose_specs()
```

This splits the PRD into per-feature subdirectories under `specs/features/`, creating `prd.md`, `arch.md`, and `tasks.md` stubs for each detected feature. Feature directories that already exist are always skipped (idempotent). Use `dry_run=True` to preview without writing files.

### 3. Run the review pipeline

Once specs exist, continue with the standard pipeline:

```
sdd_review_run(scope="all", parallel=True)
```

The Spec Linter runs first (priority 5) and validates the generated specs before any other role begins.

---

## MCP tool reference

### Initialization

| Tool | Parameters | Description |
|---|---|---|
| `sdd_init` | `project_name`, `description`, `project_root?` | Create specs structure, install git hook |
| `sdd_preflight` | `action?` (default: `"commit"`) | Run enforcement checks; returns `allowed`, `violations`, `warnings` |

### Spec management

| Tool | Parameters | Description |
|---|---|---|
| `sdd_spec_read` | `spec_type`, `feature?` | Read `prd`, `arch`, `tasks`, or `context-hints` |
| `sdd_spec_write` | `spec_type`, `content`, `feature?` | Write a spec file |
| `sdd_spec_list` | — | List all spec files in the project |

`spec_type` values: `prd`, `arch`, `tasks`, `context-hints`

### Feature management

| Tool | Parameters | Description |
|---|---|---|
| `sdd_feature_create` | `name`, `description?` | Create `specs/features/{name}/` with stub specs |
| `sdd_feature_list` | — | List all features |

### Review pipeline

| Tool | Parameters | Description |
|---|---|---|
| `sdd_review_run` | `roles?`, `scope?`, `target?`, `parallel?` | Run role reviews via Goose |
| `sdd_review_status` | — | Running/completed/failed roles + success rate |
| `sdd_review_results` | `role?` | Detailed output, issues, suggestions per role |
| `sdd_review_list` | — | List all available roles with metadata |
| `sdd_review_reset` | — | Clear review engine state |
| `sdd_recipes_generate` | `project_name`, `description?`, `overwrite?` | Write Goose YAML recipes to `specs/recipes/` |
| `sdd_recipe_render` | `role`, `project_name`, `description?` | Preview a recipe without writing it |

`scope` values: `"specs"` (documents only), `"code"` (codebase only), `"all"` (both)

### Task management

| Tool | Parameters | Description |
|---|---|---|
| `sdd_task_add` | `title`, `feature?`, `priority?`, `depends_on?` | Add a task to `tasks.md` |
| `sdd_task_list` | `feature?`, `status?` | List tasks (optionally filtered) |
| `sdd_task_update` | `task_id`, `status`, `notes?` | Update task status |
| `sdd_task_get` | `task_id` | Get a single task |
| `sdd_task_breakdown` | `feature`, `prd_content` | AI-assisted task breakdown from PRD |

### Code generation

| Tool | Parameters | Description |
|---|---|---|
| `sdd_codegen_scaffold` | `name`, `templates`, `feature?` | Generate code from templates |
| `sdd_codegen_list_templates` | — | List available templates |
| `sdd_codegen_preview` | `name`, `template` | Preview generated output |

### Validation

| Tool | Parameters | Description |
|---|---|---|
| `sdd_validate` | `spec_type?`, `feature?` | Run validation rules on specs |
| `sdd_validate_rule_add` | `rule_type`, `config` | Add a custom validation rule |
| `sdd_validate_rule_list` | — | List active rules |

### On-demand spec tools

| Tool | Parameters | Description |
|---|---|---|
| `sdd_bootstrap_specs` | `update_existing?`, `target_path?`, `max_features?` | Reverse-engineer an existing codebase into SDD specs |
| `sdd_decompose_specs` | `dry_run?`, `force?`, `target_feature?` | Split a monolithic `specs/prd.md` into per-feature subdirectories |

`sdd_bootstrap_specs` parameters:
- `update_existing` (bool, default `false`) — extend existing specs; `false` returns `blocked` if `specs/prd.md` already exists
- `target_path` (str, default `"."`) — path to the project root to bootstrap
- `max_features` (int, default `20`, max `20`) — maximum feature stubs to generate

`sdd_decompose_specs` parameters:
- `dry_run` (bool, default `false`) — return a result without writing any files
- `force` (bool, default `false`) — overwrite existing feature directories
- `target_feature` (str, optional) — decompose only this feature (slug or heading)

### Spec alignment

| Tool | Parameters | Description |
|---|---|---|
| `sdd_align_check` | `diff?` | Check spec/code alignment (uses Goose LLM) |
| `sdd_align_status` | — | Get latest alignment report |

### Custom plugins

| Tool | Parameters | Description |
|---|---|---|
| `sdd_plugin_list` | — | List loaded custom role plugins |
| `sdd_plugin_reload` | — | Hot-reload plugins from `specs/plugins/` |

### Observability

| Tool | Parameters | Description |
|---|---|---|
| `sdd_health_check` | — | Health status of all registered subsystems |
| `sdd_status` | — | Project workflow state and metadata |

---

## The 11-role pipeline

Roles execute in priority order. Roles with the same priority can run in parallel. Each role reads from `specs/arch.md` and appends its findings section.

| Priority | Role | Stage | Depends on | Output |
|---|---|---|---|---|
| 5 | `spec-linter` | SPEC_AUDIT | — | Validates prd.md / arch.md structure; emits `clean: true/false` |
| 10 | `architect` | ARCHITECTURE | spec-linter | Component Design, Data Flow, Tech Choices, Risks |
| 20 | `interface-designer` | INTERFACE_DESIGN | architect | API Endpoints, Schemas, Error Catalogue |
| 20 | `ui-designer` | UI_DESIGN | architect | User Flows, WCAG, Component Inventory |
| 30 | `security-analyst` | SECURITY | interface-designer | Threat Model, OWASP Assessment, CVEs |
| 40 | `edge-case-analyst` | EDGE_CASE_ANALYSIS | security-analyst | Edge Case Catalogue, Test Scenarios |
| 50 | `senior-developer` | IMPLEMENTATION | edge-case-analyst | Code Quality, Coverage Gaps, Tech Debt |
| 60 | `qa-engineer` | QA | senior-developer | Acceptance Criteria Coverage, Defect List |
| 60 | `tech-writer` | DOCUMENTATION | senior-developer | Doc Inventory, Changelog Entry |
| 60 | `devops-engineer` | DEVOPS | senior-developer | CI/CD, Dockerfile, Secrets, Observability |
| 80 | `product-owner` | RELEASE | qa-engineer, tech-writer, devops-engineer | Release Decision: SHIP / HOLD |

### Prerequisite gates

Each role checks that its required sections exist before starting. If a prerequisite is missing, the role emits `"status": "blocked"` and the pipeline halts for that branch.

```
spec-linter      → blocked if specs/prd.md missing
                   emits clean=false (non-blocking warning) if structure issues found
architect        → blocked if spec-linter did not complete, or specs/prd.md missing
interface-designer → blocked if "Component Design" section missing from arch.md
security-analyst → blocked if "Interface Design" section missing
edge-case-analyst → blocked if "Interface Design" OR "Security Analysis" missing
senior-developer → blocked if any of: Component Design, Interface Design,
                   Security Analysis, Edge Case Analysis missing
qa-engineer, tech-writer, devops-engineer → blocked if "Implementation Review" missing
product-owner    → blocked if QA Report, Documentation, OR DevOps section missing
```

---

## Role completion envelopes

Every role recipe ends with a mandatory JSON envelope emitted as the **last line** of stdout:

```json
{
  "sdd_role": "architect",
  "status": "completed",
  "summary": "Architecture review complete — 5 components, 3 decisions, 2 risks",
  "findings": [
    {"area": "database", "decision": "PostgreSQL over SQLite", "risk": "low"}
  ],
  "session_name": "sdd-architect-all",
  "retry_hint": null
}
```

| `status` | Meaning | Action |
|---|---|---|
| `completed` | Role finished successfully | Mark complete, continue pipeline |
| `needs_retry` | Agent lost context mid-session | Fork a new session and retry |
| `blocked` | Prerequisite sections missing | Halt; run missing upstream roles first |

The server rejects exit code 0 without a valid envelope in session mode — this catches agents that silently exit without completing their work.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `SDD_PROJECT_ROOT` | `.` (cwd) | Absolute path to the project being reviewed |
| `SDD_LOG_LEVEL` | `INFO` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `SDD_AI_CLIENT` | `goose` | AI client type (currently only `goose` is supported) |
| `SDD_AI_TIMEOUT` | `300` | Goose subprocess timeout in seconds |
| `GOOSE_CONTEXT_STRATEGY` | `summarize` | Injected automatically — prevents context exhaustion |
| `GOOSE_AUTO_COMPACT_THRESHOLD` | `0.35` | Injected automatically — triggers summarisation early |

The last two are injected into every Goose subprocess by the server. You can override them:

```bash
GOOSE_CONTEXT_STRATEGY=truncate SDD_PROJECT_ROOT=/my/project sdd-server
```

---

## Custom plugins

Drop a Python file into `specs/plugins/` to add a custom review role:

```python
# specs/plugins/my_compliance_role.py
from sdd_server.plugins.base import PluginMetadata, RolePlugin, RoleResult, RoleStage
from datetime import datetime

class ComplianceRole(RolePlugin):
    metadata = PluginMetadata(
        name="compliance",
        version="1.0.0",
        description="GDPR and SOC2 compliance review",
        author="My Team",
        priority=35,                          # runs after security-analyst
        stage=RoleStage.SECURITY,
        dependencies=["security-analyst"],
    )

    async def review(self, scope="all", target=None) -> RoleResult:
        return await self._run_with_ai_client(scope, target, datetime.now())

    def get_recipe_template(self) -> str:
        return """version: "1.0.0"
title: "Compliance — {{ project_name }}"
instructions: |
  You are the Compliance Reviewer. Check GDPR and SOC2 requirements.
prompt: |
  Review {{ project_root }} for GDPR and SOC2 compliance gaps.
extensions:
  - type: builtin
    name: developer
"""
```

Reload without restarting:
```
sdd_plugin_reload()
```

---

## Development

```bash
# Install dependencies
uv sync

# Run tests (with coverage)
uv run pytest

# Run tests without coverage (faster)
uv run pytest --no-cov

# Type checking
uv run mypy src/

# Linting and formatting
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Run the server locally pointing at a test project
SDD_PROJECT_ROOT=/tmp/test-project SDD_LOG_LEVEL=DEBUG uv run sdd-server
```

### Test structure

```
tests/
├── unit/
│   ├── core/          # GooseSession, RoleEngine, RecipeGenerator, …
│   ├── mcp/           # MCP tool handlers
│   ├── plugins/       # Plugin registry and role plugins
│   └── infrastructure/ # GitClient, SpecManager, …
└── integration/
    ├── test_smoke.py          # init → read → status flow (no Goose needed)
    └── test_goose_round_trip.py  # full bridge chain (subprocess mocked)
```

### Adding a new built-in role

1. Create `src/sdd_server/plugins/roles/{role_name}.py` — extend `RolePlugin`
2. Create `specs/recipes/{role-name}.yaml` — follow the existing recipe format including the `RoleCompletionEnvelope` output contract
3. Add the role class to `BUILTIN_ROLES` in `src/sdd_server/plugins/roles/__init__.py`
4. Add any new `RoleStage` enum value to `src/sdd_server/plugins/base.py` if needed
5. Update count assertions in tests (`== 11` → `== 12`, etc.)
