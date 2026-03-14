# AGENTS.md — SDD MCP Server

Guidance for AI coding agents working in this repository.

---

## Project Purpose

**sdd-server** is a Specs-Driven Development (SDD) MCP Server — an opinionated framework that enforces *specs before code*. It exposes 44+ MCP tools to AI agents (primarily Goose) so they can initialize projects, manage specs, run role-based reviews, check spec-code alignment, and enforce quality gates via pre-commit hooks.

**Core contract:** no code without a spec. The server guides a structured workflow through six roles (Architect → UI Designer → Interface Designer → Security Analyst → Edge Case Analyst → Senior Developer) before any implementation begins.

---

## Specs First

Before modifying any code, read the spec files:

```
specs/prd.md      # Product requirements and acceptance criteria
specs/arch.md     # Technical architecture and component design
specs/tasks.md    # Implementation task list with phase and status
```

All implementation decisions must align with these specs. If a task isn't in `specs/tasks.md`, add it there first (Pending section) before implementing.

---

## Development Setup

**Requires Python 3.14+** and [uv](https://docs.astral.sh/uv/).

```bash
# Install dependencies
uv sync --all-groups

# Install pre-commit hooks
uv run pre-commit install

# Run the MCP server
uv run sdd-server

# Run the CLI
uv run sdd --help
```

---

## Commands Reference

| Command | Purpose |
|---------|---------|
| `uv run pytest` | Run full test suite (must stay ≥ 80% coverage) |
| `uv run pytest tests/unit/` | Unit tests only |
| `uv run pytest -x` | Stop on first failure |
| `uv run pytest --no-cov` | Skip coverage (faster iteration) |
| `uv run ruff check src/ tests/` | Lint |
| `uv run ruff format src/ tests/` | Format |
| `uv run mypy src/` | Type check (strict mode) |
| `uv run pre-commit run --all-files` | Run all pre-commit hooks |

Tests run with `asyncio_mode = "auto"` — all async tests work without `@pytest.mark.asyncio`.

---

## Source Layout

```
src/sdd_server/
├── __main__.py              # MCP server entry point
├── cli/main.py              # Typer CLI (sdd init, preflight, status)
├── core/                    # Business logic (no I/O dependencies)
│   ├── role_engine.py       # Dependency-aware role orchestration
│   ├── spec_manager.py      # Spec file CRUD
│   ├── metadata.py          # Project state in .metadata.json
│   ├── initializer.py       # Project bootstrap
│   ├── recipe_manager.py    # Goose recipe CRUD
│   ├── recipe_generator.py  # Dynamic recipe generation
│   ├── ai_client.py         # AIClientBridge + GooseClientBridge
│   ├── alignment.py         # Spec-code alignment via LLM
│   ├── custom_plugin_manager.py
│   ├── task_manager.py
│   ├── code_generator.py
│   ├── spec_validator.py
│   └── startup.py
├── mcp/
│   ├── server.py            # FastMCP server + lifespan context
│   ├── tools/               # One file per tool group
│   │   ├── init.py          # sdd_init, sdd_preflight
│   │   ├── spec.py          # sdd_spec_read/write/list
│   │   ├── feature.py       # sdd_feature_create/list
│   │   ├── review.py        # sdd_review_*, sdd_recipes_*
│   │   ├── task.py          # Task management
│   │   ├── codegen.py       # Code scaffolding
│   │   ├── validation.py    # Spec validation
│   │   ├── align.py         # sdd_alignment_check
│   │   ├── status.py        # sdd_status
│   │   ├── custom_plugins.py
│   │   ├── health.py        # Health checks
│   │   └── _utils.py        # Rate limiting, error formatting
│   ├── resources/specs.py   # sdd://specs/* MCP resources
│   └── prompts/review.py    # sdd_role_* MCP prompts
├── plugins/
│   ├── base.py              # BasePlugin, RolePlugin, RoleResult, RoleStage
│   ├── loader.py            # Plugin discovery
│   ├── registry.py          # Plugin registry
│   └── roles/               # 6 built-in roles (one file each)
├── models/                  # Pydantic v2 data models
├── infrastructure/
│   ├── config.py            # Centralized config (pydantic-settings)
│   ├── filesystem.py        # FileSystemClient (path-traversal safe)
│   ├── git.py               # GitClient wrapper
│   ├── exceptions.py        # SDDError hierarchy
│   ├── retry.py
│   ├── observability/       # audit.py, health.py, metrics.py
│   └── security/            # input_validation.py, rate_limiter.py
├── utils/
│   ├── logging.py           # structlog setup
│   ├── fs.py                # atomic_write, ensure_directory
│   └── paths.py             # SpecsPaths
└── templates/               # Jinja2 templates for specs and recipes
```

---

## Architecture Patterns

### Stateless Design
All state lives in files (git-tracked) or `specs/.metadata.json`. The MCP server can be restarted with no data loss.

### Layering Rules
- `core/` must not import from `mcp/` — business logic has no MCP dependency
- `mcp/tools/` imports from `core/` via the lifespan context (see `mcp/server.py`)
- `infrastructure/` provides I/O primitives used by `core/`
- Never import from `tests/` in production code

### Lifespan Context
All MCP tools receive services via `mcp/server.py`'s `LifespanContext` TypedDict. Access services through `ctx.request_context.lifespan_context`:

```python
# In a tool function
lc = ctx.request_context.lifespan_context
spec_manager: SpecManager = lc["spec_manager"]
```

### Plugin System
New roles extend `RolePlugin` (from `plugins/base.py`):

```python
class MyRole(RolePlugin):
    @property
    def metadata(self) -> PluginMetadata: ...
    async def review(self, scope, target) -> RoleResult: ...
    def get_recipe_template(self) -> str: ...  # Jinja2 template
    def get_dependencies(self) -> list[str]: ...
    def get_stage(self) -> RoleStage: ...
```

Place the file in `plugins/roles/` — the loader discovers it automatically.

### File System Safety
Always use `FileSystemClient` (not raw `pathlib`) for any file operations that take user-supplied paths. It enforces path-traversal protection and atomic writes.

### Error Handling
Raise from the `SDDError` hierarchy (`infrastructure/exceptions.py`). MCP tools catch these and format them with `_utils.format_error_response()`. Never raise bare `Exception` in tool handlers.

---

## Role Workflow Stages

Roles execute in dependency order; independent roles run in parallel (max 3 concurrent, configurable via `SDD_MAX_PARALLEL_ROLES`):

```
ARCHITECTURE → UI_DESIGN → INTERFACE_DESIGN → SECURITY → EDGE_CASE_ANALYSIS → IMPLEMENTATION → REVIEW
```

| Role | Stage | Depends On |
|------|-------|-----------|
| Architect | ARCHITECTURE | — |
| UI Designer | UI_DESIGN | Architect |
| Interface Designer | INTERFACE_DESIGN | Architect |
| Security Analyst | SECURITY | Interface Designer |
| Edge Case Analyst | EDGE_CASE_ANALYSIS | Security Analyst |
| Senior Developer | IMPLEMENTATION | Edge Case Analyst |

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `SPECS_DIR` | `specs/` | Override specs directory |
| `RECIPES_DIR` | `specs/recipes/` | Override recipes directory |
| `SDD_LOG_LEVEL` | `INFO` | Logging level |
| `SDD_AI_CLIENT` | `goose` | AI backend (`goose` \| `claude-code` \| custom) |
| `SDD_SOURCE_DIRS` | `src,lib` | Dirs readable for alignment checks |
| `SDD_MAX_PARALLEL_ROLES` | `3` | Max concurrent role executions |

---

## Testing Conventions

- Test files mirror source layout: `tests/unit/core/test_role_engine.py` tests `src/sdd_server/core/role_engine.py`
- Use `pytest-mock`'s `mocker` fixture; do **not** use `unittest.mock` directly
- Async tests: just use `async def test_*()` — no decorator needed
- Use `tmp_path` (pytest built-in) for file system tests, never create real files in the repo
- Minimum coverage: **80%** — enforced by `--cov-fail-under=80` in `pytest.ini_options`
- Integration tests live in `tests/integration/`; they may be slow and are not required to run in isolation

---

## Code Style

- Line length: **100** (ruff enforces)
- Target: **Python 3.14** syntax
- Type hints: required on all public functions and methods (mypy strict)
- Imports: sorted by ruff (`I` rules); stdlib → third-party → local
- String quotes: double quotes (ruff enforces)
- No `print()` — use `get_logger(__name__)` from `utils/logging.py`

---

## Goose Recipe Files

Recipes live in `specs/recipes/*.yaml` (`.yaml` extension required — Goose CLI rejects `.yml`).

Each recipe must include: `version`, `title`, `description`, `instructions`, `prompt`, `extensions`, `response` (JSON schema), and `retry`. See `specs/tasks.md` for the canonical schema example.

Generate recipes via: `uv run sdd recipes generate` or the `sdd_recipes_generate` MCP tool.

---

## Implementation Status

| Phase | Scope | Status |
|-------|-------|--------|
| 1 — Foundation | Project structure, models, infrastructure, core managers, basic MCP tools | ✅ Complete (81% coverage) |
| 2 — Role System | Plugin base, 6 built-in roles, RoleEngine, recipe generation | ✅ Code exists; tests pending |
| 3 — AI Client Integration | AIClientBridge, GooseClientBridge, AlignmentChecker | ✅ Code exists; end-to-end not verified |
| 4 — Enforcement Engine | EnforcementEngine, `sdd bypass` with audit, CI/CD mode | ❌ Not implemented |
| 5 — Production Hardening | watchdog file monitor, Docker, e2e tests, full docs | ❌ Not implemented |

**Key pending tasks** (from `specs/tasks.md`):

- `t0000070–t0000074`: EnforcementEngine + pre-commit blocking + bypass audit trail
- `t0000080`: watchdog-based live spec reload
- `t0000082`: Docker packaging (use `cgr.dev/chainguard/python` base image)
- `t0000083`: End-to-end integration tests
- `t0000040–t0000045`: Supplementary models and git client extensions (medium priority)

---

## What Is NOT Ready for Production Use

1. **Enforcement is not wired up** — `sdd preflight` exists but the `EnforcementEngine` (Phase 4) that actually blocks commits is not implemented. Pre-commit hook installs but does not enforce spec completeness.
2. **AI round-trip is unverified** — `GooseClientBridge` is implemented but no end-to-end test confirms a real Goose subprocess call completes correctly.
3. **No CI/CD pipeline** — `.github/workflows/` is absent; there are no automated test runs on push.
4. **No Docker image** — the server cannot be distributed as a container yet.
5. **File watcher inactive** — `watchdog` is a declared dependency but the continuous monitoring loop (Phase 5) is not implemented.
