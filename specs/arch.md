# Technical Architecture Document: Specs-Driven Development MCP Server

**Version:** 1.0  
**Date:** 2026-03-02  
**Status:** ✅ Complete - Ready for Implementation

---

## 1. Executive Summary

### 1.1 Architecture Goals

This document defines the technical architecture for the Specs-Driven Development (SDD) MCP Server, an opinionated framework that enforces spec-first development tightly integrated with Goose.

**Primary Goals:**
1. **Low Barrier to Entry:** Smooth onboarding, intuitive workflows
2. **Strict Enforcement:** Block actions without specs (no bypass)
3. **Seamless Goose Integration:** Native handoff for implementation
4. **Extensibility:** Plugin architecture for roles, analyzers, linters
5. **Reliability:** Stateless design, git-based recovery

### 1.2 Technology Stack Summary

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Language** | Python 3.14+ | MCP SDK maturity, fast development, `tomllib` stdlib, `asyncio.TaskGroup` |
| **MCP Framework** | `mcp` (official SDK) | Native MCP support, async-friendly |
| **Validation** | Pydantic v2 | Type safety, validation, serialization |
| **CLI** | Rich + Typer | Beautiful output, easy command building |
| **Async** | asyncio + anyio | Parallel role execution, non-blocking I/O |
| **Testing** | pytest + pytest-asyncio | Industry standard, async support |
| **Linting** | ruff | Fast, comprehensive, replaces flake8/black |
| **Type Checking** | mypy | Static type verification |
| **Package Manager** | uv | Blazing fast, replaces pip/pip-tools/venv |

---

## 2. System Architecture Overview

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER / GOOSE CLI                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SDD MCP SERVER                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        MCP Tool Layer                                │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │    │
│  │  │  sdd_    │ │  sdd_    │ │  sdd_    │ │  sdd_    │ │  sdd_    │  │    │
│  │  │  init    │ │  spec    │ │  feature │ │  task    │ │  status  │  │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐               │    │
│  │  │  sdd_    │ │  sdd_    │ │  sdd_    │ │  sdd_    │               │    │
│  │  │  review  │ │  commit  │ │  align   │ │  config  │               │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                      │                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        Core Services Layer                           │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │    │
│  │  │ SpecManager  │  │ RoleEngine   │  │AIClientBridge│              │    │
│  │  │              │  │              │  │              │              │    │
│  │  │ - CRUD ops   │  │ - Role seq   │  │ - CLI wrap   │              │    │
│  │  │ - Templates  │  │ - Parallel   │  │ - Task exec  │              │    │
│  │  │ - Validation │  │ - Aggregation│  │ - Progress   │              │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │    │
│  │  │ Alignment    │  │ Enforcement  │  │ RecipeGen    │              │    │
│  │  │ Checker      │  │ Middleware   │  │              │              │    │
│  │  │              │  │              │  │              │              │    │
│  │  │ - AST parse  │  │ - Pre-commit │  │ - Context    │              │    │
│  │  │ - Diff gen   │  │ - Blockades  │  │ - Templates  │              │    │
│  │  │ - Verify     │  │ - Guidance   │  │ - Validation │              │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                      │                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        Infrastructure Layer                          │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │    │
│  │  │ FileSystem   │  │ GitClient    │  │ PluginLoader │              │    │
│  │  │              │  │              │  │              │              │    │
│  │  │ - Atomic ops │  │ - Status     │  │ - Discovery  │              │    │
│  │  │ - Paths      │  │ - Commit     │  │ - Loading    │              │    │
│  │  │ - Watch      │  │ - Hooks      │  │ - Registry   │              │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FILE SYSTEM & GIT                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │ specs/     │  │ recipes/   │  │ .git/      │  │ src/       │           │
│  │            │  │            │  │            │  │            │           │
│  │ - prd.md   │  │ - *.yml    │  │ - history  │  │ - code     │           │
│  │ - arch.md  │  │            │  │ - hooks    │  │            │           │
│  │ - tasks.md │  │            │  │            │  │            │           │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Responsibilities

| Component | Responsibility | Key Dependencies |
|-----------|---------------|------------------|
| **MCP Tool Layer** | Expose tools to AI clients/user | All core services |
| **MCP Resource Layer** | Expose spec files as MCP resources | SpecManager, FileSystem |
| **MCP Prompt Layer** | Expose role prompts as MCP prompts | RoleEngine, SpecManager |
| **SpecManager** | CRUD operations on spec files | FileSystem, Templates |
| **RoleEngine** | Orchestrate role execution | RecipeGen, AIClientBridge |
| **AIClientBridge** | Abstract AI client interface (Goose impl by default) | subprocess, GitClient |
| **AlignmentChecker** | LLM-based semantic spec-code alignment | AIClientBridge, SpecManager |
| **EnforcementMiddleware** | Block actions with grace mode + audit log | All services |
| **WorkflowOrchestrator** | Manage execution loop, coordinate monitoring | StateManager, FileWatcher, EventBus |
| **StateManager** | Persist per-feature workflow state with history | FileSystem |
| **FileWatcher** | Monitor file changes, emit events | watchdog, EventBus |
| **EventBus** | Central event dispatching | - |
| **RecipeGen** | Generate AI client recipes/prompts | Templates, Context |
| **FileSystem** | Atomic file operations | pathlib, tempfile |
| **GitClient** | Git operations | subprocess |
| **PluginLoader** | Load role/analyzer plugins | importlib |

---
## 3. Python Tech Stack Proposal

### 3.1 Core Dependencies

```toml
# pyproject.toml
[project]
name = "sdd-server"
version = "0.1.0"
description = "Specs-Driven Development MCP Server"
requires-python = ">=3.14"
readme = "README.md"
license = { text = "MIT" }
authors = [
    { name = "SDD Team" }
]

dependencies = [
    # MCP Framework
    "mcp>=1.0.0",
    
    # Data Validation & Settings
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    
    # YAML Processing
    "pyyaml>=6.0",
    
    # CLI & Output
    "rich>=13.0.0",
    "typer>=0.9.0",

    # Async Support
    "anyio>=4.0.0",

    # Template Engine
    "jinja2>=3.1.0",

    # Markdown Processing
    "markdown-it-py>=3.0.0",

    # File Monitoring
    "watchdog>=4.0.0",         # File system event monitoring

    # Logging
    "structlog>=24.0.0",
    # NOTE: tomllib is stdlib in Python 3.11+; no external dep needed at 3.14+
    # NOTE: libcst removed — alignment uses LLM semantic analysis, not AST parsing
]

[project.optional-dependencies]
dev = [
    # Testing
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    
    # Type Checking
    "mypy>=1.8.0",
    
    # Linting & Formatting
    "ruff>=0.2.0",
    
    # Pre-commit
    "pre-commit>=3.6.0",
]

# Additional language support
rust = [
    "toml>=0.10.0",            # Rust Cargo.toml parsing
]

[project.scripts]
sdd-server = "sdd_server.cli:main"
sdd = "sdd_server.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### 3.2 Dependency Rationale

| Package | Purpose | Why This Choice |
|---------|---------|-----------------|
| **mcp** | MCP server framework | Official SDK, async-native |
| **pydantic** | Data validation | Type safety, JSON schema generation |
| **rich** | Terminal output | Beautiful tables, progress bars, syntax highlighting |
| **typer** | CLI framework | Type-hint driven, integrates with Rich |
| **jinja2** | Templating | Mature, powerful for spec templates |
| **structlog** | Structured logging | JSON logs for debugging, human-readable for CLI |
| **anyio** | Async abstraction | Works with asyncio and trio |
| **watchdog** | File monitoring | Efficient cross-platform file system events |
| **tomllib** | TOML parsing | Python 3.11+ stdlib — no external dep |

### 3.3 Package Management with uv

This project uses **uv** for all Python package and project management. uv is a blazing-fast Python package installer and resolver written in Rust, replacing pip, pip-tools, pipx, poetry, pyenv, and virtualenv.

#### Why uv?

| Feature | Benefit |
|---------|---------|
| **Speed** | 10-100x faster than pip for dependency resolution |
| **Unified Tool** | Replaces pip, pip-tools, pipx, poetry, venv |
| **Lock File** | Automatic `uv.lock` for reproducible builds |
| **Python Management** | Install and manage Python versions |
| **Project Management** | Native `pyproject.toml` support |
| **Virtual Environments** | Automatic venv creation and management |

#### Development Workflow with uv

```bash
# Install uv (one-time setup)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create project and set up development environment
uv init sdd-server
cd sdd-server

# Add dependencies (tomllib is stdlib at 3.14+; libcst not needed)
uv add mcp pydantic pydantic-settings pyyaml rich typer
uv add anyio jinja2 markdown-it-py structlog

# Add dev dependencies
uv add --dev pytest pytest-asyncio pytest-cov pytest-mock
uv add --dev mypy ruff pre-commit

# Run commands in the virtual environment
uv run python -m sdd_server
uv run pytest
uv run ruff check src/
uv run mypy src/

# Build distribution
uv build

# Run the MCP server
uv run sdd-server
```

#### uv Configuration

```toml
# pyproject.toml additions for uv
[tool.uv]
dev-dependencies = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    "mypy>=1.8.0",
    "ruff>=0.2.0",
    "pre-commit>=3.6.0",
]

[tool.uv.python]
version = "3.14"
```

#### Common uv Commands

| Command | Purpose |
|---------|---------|
| `uv init` | Initialize a new project |
| `uv add <package>` | Add a dependency |
| `uv add --dev <package>` | Add a dev dependency |
| `uv remove <package>` | Remove a dependency |
| `uv sync` | Sync dependencies from lock file |
| `uv lock` | Update lock file |
| `uv run <command>` | Run command in venv |
| `uv build` | Build distribution |
| `uv publish` | Publish to PyPI |
| `uv python install 3.12` | Install Python version |

### 3.4 Development Tooling

```toml
# ruff.toml
[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "ARG",    # flake8-unused-arguments
    "SIM",    # flake8-simplify
]
ignore = [
    "E501",   # line too long (handled by formatter)
]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.mypy]
python_version = "3.14"
strict = true
warn_return_any = true
warn_unused_ignores = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### 3.5 CI/CD Configuration with uv

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.14"]

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python ${{ matrix.python-version }}
        run: uv python install ${{ matrix.python-version }}

      - name: Install dependencies
        run: uv sync --dev

      - name: Run ruff
        run: uv run ruff check src/ tests/

      - name: Run ruff format check
        run: uv run ruff format --check src/ tests/

      - name: Run mypy
        run: uv run mypy src/

      - name: Run tests
        run: uv run pytest --cov=src/sdd_server --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml

  build:
    runs-on: ubuntu-latest
    needs: lint-and-test

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Build package
        run: uv build

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/
```

---

## 4. Project Structure

### 4.1 Directory Layout

```
sdd-server/
├── pyproject.toml              # Project configuration
├── ruff.toml                   # Linting configuration
├── README.md                   # Project documentation
├── LICENSE
│
├── src/
│   └── sdd_server/
│       ├── __init__.py         # Package init, version
│       ├── __main__.py         # Entry point for python -m
│       │
│       ├── cli/                # CLI Interface
│       │   ├── __init__.py
│       │   ├── main.py         # Typer app definition
│       │   ├── commands/       # CLI commands
│       │   │   ├── __init__.py
│       │   │   ├── init.py     # sdd init
│       │   │   ├── spec.py     # sdd spec
│       │   │   ├── feature.py  # sdd feature
│       │   │   ├── task.py     # sdd task
│       │   │   ├── review.py   # sdd review
│       │   │   ├── commit.py   # sdd commit
│       │   │   └── status.py   # sdd status
│       │   └── utils.py        # CLI utilities
│       │
│       ├── mcp/                # MCP Server
│       │   ├── __init__.py
│       │   ├── server.py       # MCP server setup
│       │   ├── tools/          # MCP tools
│       │   │   ├── __init__.py
│       │   │   ├── init.py     # sdd_init, sdd_preflight tools
│       │   │   ├── spec.py     # sdd_spec_* tools
│       │   │   ├── feature.py  # sdd_feature_* tools
│       │   │   ├── task.py     # sdd_task_* tools
│       │   │   ├── review.py   # sdd_review tool
│       │   │   ├── commit.py   # sdd_commit tool
│       │   │   ├── align.py    # sdd_align tool
│       │   │   └── status.py   # sdd_status tool
│       │   ├── resources/      # MCP resources (spec files as readable resources)
│       │   │   ├── __init__.py
│       │   │   └── specs.py    # sdd://specs/* resource handlers
│       │   └── prompts/        # MCP prompts (role definitions)
│       │       ├── __init__.py
│       │       └── roles.py    # sdd_role_* prompt handlers
│       │
│       ├── core/               # Core Services
│       │   ├── __init__.py
│       │   ├── spec_manager.py # Spec file management
│       │   ├── role_engine.py  # Role orchestration
│       │   ├── ai_client.py    # AIClientBridge abstract interface
│       │   ├── alignment.py    # LLM-based spec-code alignment
│       │   ├── enforcement.py  # Enforcement middleware
│       │   ├── recipe_gen.py   # Recipe generation
│       │   ├── orchestrator.py # Workflow orchestrator
│       │   ├── state_manager.py# State persistence
│       │   ├── file_watcher.py # File monitoring
│       │   └── event_bus.py    # Event dispatching
│       │
│       ├── plugins/            # Plugin System
│       │   ├── __init__.py
│       │   ├── base.py         # Plugin base classes
│       │   ├── loader.py       # Plugin discovery/loading
│       │   ├── roles/          # Built-in role plugins
│       │   │   ├── __init__.py
│       │   │   ├── architect.py
│       │   │   ├── ui_designer.py
│       │   │   ├── interface_designer.py
│       │   │   ├── security_analyst.py
│       │   │   ├── edge_case_analyst.py
│       │   │   └── senior_developer.py
│       │   ├── analyzers/      # Built-in code analyzers
│       │   │   ├── __init__.py
│       │   │   ├── python.py
│       │   │   ├── rust.py
│       │   │   └── typescript.py
│       │   └── linters/        # Built-in lint integrations
│       │       ├── __init__.py
│       │       ├── ruff.py
│       │       ├── eslint.py
│       │       └── clippy.py
│       │
│       ├── infrastructure/     # Infrastructure
│       │   ├── __init__.py
│       │   ├── filesystem.py   # File operations
│       │   ├── git.py          # Git operations
│       │   ├── templates.py    # Template management
│       │   └── config.py       # Configuration
│       │
│       ├── models/             # Data Models
│       │   ├── __init__.py
│       │   ├── spec.py         # Spec models
│       │   ├── task.py         # Task models
│       │   ├── feature.py      # Feature models
│       │   ├── role.py         # Role models
│       │   ├── recipe.py       # Recipe models
│       │   └── project.py      # Project context
│       │
│       └── utils/              # Utilities
│           ├── __init__.py
│           ├── logging.py      # Logging setup
│           ├── paths.py        # Path utilities
│           ├── text.py         # Text processing
│           └── validation.py   # Input validation
│
├── tests/                      # Test Suite
│   ├── conftest.py             # Pytest fixtures
│   ├── unit/
│   │   ├── test_spec_manager.py
│   │   ├── test_role_engine.py
│   │   ├── test_alignment.py
│   │   └── ...
│   ├── integration/
│   │   ├── test_mcp_tools.py
│   │   ├── test_ai_client.py
│   │   └── ...
│   └── e2e/
│       ├── test_new_project.py
│       ├── test_existing_project.py
│       └── ...
│
└── docs/                       # Documentation
    # NOTE: Templates are packaged inside src/sdd_server/templates/ (not a top-level dir).
    # This avoids duplication and ensures templates ship with the package.
    ├── index.md
    ├── getting-started.md
    ├── mcp-tools.md
    ├── roles.md
    ├── plugins.md
    └── configuration.md
```

---
## 5. Core Component Design

### 5.1 SpecManager

**Purpose:** Manage spec file operations (CRUD, validation, templates)

```python
# src/sdd_server/core/spec_manager.py

from pathlib import Path
from typing import Optional
from pydantic import BaseModel

class SpecManager:
    """
    Manages spec file operations with atomic writes and validation.
    """
    
    def __init__(self, specs_dir: Path, templates_dir: Path):
        self.specs_dir = specs_dir
        self.templates_dir = templates_dir
    
    # === Read Operations ===
    
    async def read_prd(self, feature: Optional[str] = None) -> str:
        """Read PRD content (main or feature-specific)."""
        ...
    
    async def read_arch(self, feature: Optional[str] = None) -> str:
        """Read architecture content."""
        ...
    
    async def read_tasks(self, feature: Optional[str] = None) -> str:
        """Read tasks content."""
        ...
    
    # === Write Operations ===
    
    async def write_prd(
        self, 
        content: str, 
        feature: Optional[str] = None,
        mode: str = "overwrite"  # "overwrite" | "append" | "prepend"
    ) -> None:
        """Write PRD with atomic operation."""
        ...
    
    async def write_arch(
        self, 
        content: str, 
        feature: Optional[str] = None,
        mode: str = "overwrite"
    ) -> None:
        """Write architecture with atomic operation."""
        ...
    
    async def write_tasks(
        self, 
        content: str, 
        feature: Optional[str] = None,
        mode: str = "overwrite"
    ) -> None:
        """Write tasks with atomic operation."""
        ...
    
    # === Feature Management ===
    
    async def create_feature(
        self, 
        name: str, 
        description: str,
        inherit_from_main: bool = True
    ) -> Path:
        """Create a new feature directory with templates."""
        ...
    
    async def list_features(self) -> list[str]:
        """List all feature directories."""
        ...
    
    async def delete_feature(self, name: str) -> None:
        """Delete a feature directory (with confirmation)."""
        ...
    
    # === Validation ===
    
    async def validate_spec_structure(self) -> list[str]:
        """Validate spec directory structure, return list of issues."""
        ...
    
    async def ensure_specs_exist(self) -> None:
        """Create specs directory if it doesn't exist."""
        ...
```

### 5.1b StartupValidator

**Purpose:** Validate server configuration on startup and surface clear errors before any tool is invoked.

```python
# src/sdd_server/core/startup.py

from dataclasses import dataclass
from pathlib import Path

@dataclass
class StartupCheck:
    name: str
    passed: bool
    message: str
    fatal: bool = True  # Fatal checks abort startup; non-fatal are warnings

class StartupValidator:
    """
    Runs configuration and environment checks at MCP server startup.
    Prevents cryptic runtime failures by surfacing issues early.

    Checks performed:
    - specs_dir exists and is writable
    - recipes_dir exists and is writable
    - Project is inside a git repository
    - Configured AI client is reachable and version-compatible
    - Pre-commit hook is installed (non-fatal warning if missing)
    - source_dirs are readable (for alignment checks)
    - Python version >= 3.14 (sanity check)
    """

    def __init__(
        self,
        project_root: Path,
        specs_dir: Path,
        recipes_dir: Path,
        ai_client: "AIClientBridge",
        source_dirs: list[str],
    ):
        ...

    async def run_all(self) -> list[StartupCheck]:
        """Run all startup checks and return results."""
        ...

    async def assert_ready(self) -> None:
        """Run checks and raise StartupError if any fatal check fails."""
        ...
```

### 5.2 RoleEngine

**Purpose:** Orchestrate role execution with parallel/sequential coordination

```python
# src/sdd_server/core/role_engine.py

from enum import Enum
from pydantic import BaseModel
from typing import Callable, Awaitable

class RoleStage(Enum):
    ARCHITECTURE = "architecture"
    UI_DESIGN = "ui_design"
    INTERFACE_DESIGN = "interface_design"
    SECURITY = "security"
    EDGE_CASE_ANALYSIS = "edge_case_analysis"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"

class RoleResult(BaseModel):
    role: str
    stage: RoleStage
    success: bool
    output: str
    issues: list[str] = []
    suggestions: list[str] = []

class RoleEngine:
    """
    Orchestrates role execution based on workflow stage.
    Supports parallel execution for independent roles.
    """
    
    def __init__(self, ai_client: "AIClientBridge", recipe_gen: "RecipeGen"):
        self.ai_client = ai_client
        self.recipe_gen = recipe_gen
        self.role_graph = self._build_dependency_graph()
    
    def _build_dependency_graph(self) -> dict[RoleStage, list[RoleStage]]:
        """
        Build role dependency graph.
        
        Dependencies:
        - UI_DESIGN depends on ARCHITECTURE
        - INTERFACE_DESIGN depends on ARCHITECTURE
        - SECURITY depends on ARCHITECTURE, INTERFACE_DESIGN
        - EDGE_CASE_ANALYSIS depends on ARCHITECTURE, INTERFACE_DESIGN, SECURITY
        - IMPLEMENTATION depends on all above
        - REVIEW depends on IMPLEMENTATION
        """
        return {
            RoleStage.ARCHITECTURE: [],
            RoleStage.UI_DESIGN: [RoleStage.ARCHITECTURE],
            RoleStage.INTERFACE_DESIGN: [RoleStage.ARCHITECTURE],
            RoleStage.SECURITY: [RoleStage.ARCHITECTURE, RoleStage.INTERFACE_DESIGN],
            RoleStage.EDGE_CASE_ANALYSIS: [
                RoleStage.ARCHITECTURE,
                RoleStage.INTERFACE_DESIGN,
                RoleStage.SECURITY
            ],
            RoleStage.IMPLEMENTATION: [
                RoleStage.ARCHITECTURE, 
                RoleStage.UI_DESIGN, 
                RoleStage.INTERFACE_DESIGN,
                RoleStage.SECURITY,
                RoleStage.EDGE_CASE_ANALYSIS
            ],
            RoleStage.REVIEW: [RoleStage.IMPLEMENTATION],
        }
    
    async def execute_stage(
        self, 
        stage: RoleStage,
        context: dict,
        parallel: bool = True
    ) -> list[RoleResult]:
        """
        Execute all roles for a given stage.
        
        If parallel=True and roles are independent, run concurrently.
        """
        ...
    
    async def execute_role(
        self,
        role_name: str,
        stage: RoleStage,
        context: dict
    ) -> RoleResult:
        """Execute a single role via Goose bridge."""
        ...
    
    async def get_next_stage(self, current: Optional[RoleStage] = None) -> RoleStage:
        """Determine next stage based on completion status."""
        ...
    
    async def get_parallel_roles(self, stage: RoleStage) -> list[str]:
        """Get roles that can run in parallel for a stage."""
        ...
```

### 5.3 AIClientBridge

**Purpose:** Abstract interface for AI client execution. Default implementation: Goose CLI.

```python
# src/sdd_server/core/ai_client.py

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from pydantic import BaseModel

class ClientResult(BaseModel):
    success: bool
    output: str
    error: str | None = None
    exit_code: int
    tokens_used: int | None = None  # For cost tracking

class AIClientBridge(ABC):
    """
    Abstract interface for AI client execution.
    All role invocations, task executions, and alignment checks
    go through this interface so the underlying client is swappable.
    """

    @abstractmethod
    async def execute_task(
        self,
        task_id: str,
        prompt: str,
        recipe: str | None = None
    ) -> ClientResult:
        """Execute a task prompt via the AI client."""
        ...

    @abstractmethod
    async def invoke_role(
        self,
        role_name: str,
        context: dict,
        recipe_path: Path | None = None
    ) -> ClientResult:
        """Invoke a role via the AI client."""
        ...

    @abstractmethod
    async def run_alignment_check(
        self,
        spec_context: str,
        code_diff: str
    ) -> ClientResult:
        """Run LLM-based semantic alignment check."""
        ...

    @abstractmethod
    async def get_version(self) -> str:
        """Return client version string."""
        ...

    @abstractmethod
    async def check_compatibility(self) -> tuple[bool, str]:
        """Check if the client version is compatible with this server."""
        ...


class GooseClientBridge(AIClientBridge):
    """
    Goose CLI implementation of AIClientBridge.
    Invokes Goose via subprocess.
    """

    def __init__(self, project_root: Path, timeout: int = 300):
        self.project_root = project_root
        self.timeout = timeout
        self._goose_path = self._find_goose()

    def _find_goose(self) -> str:
        """Find goose binary in PATH."""
        ...

    async def execute_task(self, task_id: str, prompt: str, recipe: str | None = None) -> ClientResult:
        """goose run --recipe {recipe} --prompt "{prompt}" """
        ...

    async def invoke_role(self, role_name: str, context: dict, recipe_path: Path | None = None) -> ClientResult:
        """goose run --recipe recipes/{role_name}.yml"""
        ...

    async def run_alignment_check(self, spec_context: str, code_diff: str) -> ClientResult:
        """Passes spec + diff to Goose for semantic alignment assessment."""
        ...

    async def get_version(self) -> str:
        ...

    async def check_compatibility(self) -> tuple[bool, str]:
        ...


def create_ai_client(client_type: str, project_root: Path) -> AIClientBridge:
    """Factory: instantiate the correct bridge from SDD_AI_CLIENT env var."""
    match client_type:
        case "goose":
            return GooseClientBridge(project_root)
        case _:
            raise ValueError(f"Unknown AI client: {client_type!r}")
```

### 5.4 AlignmentChecker

**Purpose:** Verify spec-code alignment using LLM semantic analysis (not AST parsing).

```python
# src/sdd_server/core/alignment.py

from pathlib import Path
from pydantic import BaseModel
from enum import Enum

class AlignmentStatus(Enum):
    ALIGNED = "aligned"
    DIVERGED = "diverged"
    MISSING_SPEC = "missing_spec"
    MISSING_CODE = "missing_code"

class AlignmentIssue(BaseModel):
    file: Path | None
    spec_ref: str
    status: AlignmentStatus
    description: str
    suggested_action: str  # "update_spec" | "update_code" | "create_spec"
    severity: str          # "critical" | "warning" | "info"

class AlignmentReport(BaseModel):
    overall_status: AlignmentStatus
    issues: list[AlignmentIssue]
    summary: dict[str, int]
    tokens_used: int | None = None

class AlignmentChecker:
    """
    Verifies alignment between specs and code via LLM semantic analysis.

    Approach:
    1. Extract relevant spec section(s) from arch.md / prd.md
    2. Collect code diff (git diff HEAD or specific files)
    3. Send {spec_context + code_diff} to AIClientBridge.run_alignment_check()
    4. Parse structured response into AlignmentReport

    This is language-agnostic and detects semantic misalignment
    (wrong behaviour, missing requirement coverage) that AST cannot.
    Token usage is bounded by max_tokens_per_check configuration.
    """

    def __init__(
        self,
        spec_manager: "SpecManager",
        ai_client: "AIClientBridge",
        project_root: Path,
        source_dirs: list[str] | None = None,
        max_tokens_per_check: int = 8000,
    ):
        self.spec_manager = spec_manager
        self.ai_client = ai_client
        self.project_root = project_root
        self.source_dirs = source_dirs or ["src", "lib"]
        self.max_tokens_per_check = max_tokens_per_check

    async def check_alignment(
        self,
        scope: str = "all"  # "all" | "feature:<name>" | "file:<path>"
    ) -> AlignmentReport:
        """
        Check alignment between specs and code.

        Steps:
        1. Extract relevant spec sections
        2. Collect focused code diff (bounded by max_tokens_per_check)
        3. Invoke LLM alignment check via AIClientBridge
        4. Parse and return structured AlignmentReport
        """
        ...

    async def check_task_completion(
        self,
        task_id: str
    ) -> tuple[bool, list[str]]:
        """Check if a task has been completed by asking the LLM to evaluate."""
        ...

    async def summarize_codebase_structure(self) -> str:
        """
        Produce a concise text summary of the codebase structure.
        Used for existing project initialization (not AST, just file tree + key files).
        """
        ...
    
    async def suggest_spec_updates(
        self,
        code_changes: list[Path]
    ) -> list[str]:
        """Suggest spec updates based on code changes."""
        ...
```

### 5.5 EnforcementMiddleware

**Purpose:** Block actions when specs are missing, guide user to compliance

```python
# src/sdd_server/core/enforcement.py

from enum import Enum
from pydantic import BaseModel

class BlockedAction(Enum):
    IMPLEMENT_WITHOUT_SPEC = "implement_without_spec"
    COMMIT_WITHOUT_REVIEW = "commit_without_review"
    SKIP_QUALITY_GATE = "skip_quality_gate"
    MISSING_PRD = "missing_prd"
    MISSING_ARCH = "missing_arch"

class EnforcementResult(BaseModel):
    allowed: bool
    blocked_reason: BlockedAction | None = None
    required_actions: list[str]
    guidance: str

class BypassRecord(BaseModel):
    """Audit record for an enforcement bypass."""
    action: BlockedAction
    reason: str
    timestamp: float
    actor: str  # git user.name or "unknown"

class EnforcementMiddleware:
    """
    Enforces spec-driven development by blocking non-compliant actions.

    Grace mode: any block can be bypassed with an explicit reason.
    Bypasses are always logged to .metadata.json (append-only audit trail)
    and surfaced prominently in `sdd status`.
    """

    def __init__(
        self,
        spec_manager: "SpecManager",
        role_engine: "RoleEngine",
        alignment_checker: "AlignmentChecker",
        state_manager: "StateManager",
    ):
        self.spec_manager = spec_manager
        self.role_engine = role_engine
        self.alignment_checker = alignment_checker
        self.state_manager = state_manager
    
    async def check_can_implement(
        self,
        feature: str | None,
        component: str
    ) -> EnforcementResult:
        """
        Check if implementation is allowed.
        
        Requirements:
        - PRD must exist
        - Arch must define the component
        - Task must be defined
        """
        ...
    
    async def check_can_commit(
        self,
        files: list[str]
    ) -> EnforcementResult:
        """
        Check if commit is allowed.
        
        Requirements:
        - All quality gates passed
        - All required roles reviewed
        - Alignment check passed
        """
        ...
    
    async def get_required_actions(
        self,
        blocked_reason: BlockedAction
    ) -> list[str]:
        """Get list of actions required to unblock."""
        ...

    async def generate_guidance(
        self,
        blocked_reason: BlockedAction,
        context: dict
    ) -> str:
        """Generate step-by-step guidance for user."""
        ...

    async def bypass(
        self,
        blocked_reason: BlockedAction,
        reason: str,
        actor: str,
    ) -> None:
        """
        Record a grace-mode bypass in the audit log.
        This does NOT skip enforcement logic — callers must check EnforcementResult.allowed
        and explicitly call bypass() when the user provides --reason.
        """
        record = BypassRecord(
            action=blocked_reason,
            reason=reason,
            timestamp=datetime.now().timestamp(),
            actor=actor,
        )
        await self.state_manager.append_bypass(record)
```

### 5.6 WorkflowOrchestrator

**Purpose:** Manage the execution loop, coordinate monitoring, validation, and action triggering

```python
# src/sdd_server/core/orchestrator.py

from enum import Enum
from pydantic import BaseModel
from typing import Callable, Awaitable
import asyncio

class WorkflowState(Enum):
    """
    Per-feature workflow states.
    Each feature has its own independent state machine.
    Project-level state is a rollup computed from feature states.
    """
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    SPEC_REVIEW = "spec_review"
    READY = "ready"
    IMPLEMENTING = "implementing"
    REVIEWING = "reviewing"
    BLOCKED = "blocked"
    COMPLETED = "completed"

class StateTransition(BaseModel):
    """Represents a valid state transition."""
    from_state: WorkflowState
    to_state: WorkflowState
    trigger: str
    required_conditions: list[str] = []
    automatic: bool = False

class WorkflowEvent(BaseModel):
    """Event that may trigger state changes or actions."""
    event_type: str  # "file_change", "user_action", "timer", "external"
    source: str
    data: dict
    timestamp: float


class WorkflowOrchestrator:
    """
    Central orchestrator managing the execution loop.
    
    Execution Loop:
    1. DETECT → Monitor state and changes
    2. VALIDATE → Check alignment and compliance
    3. TRIGGER → Invoke appropriate roles/actions
    4. GUIDE → Provide next-step suggestions
    5. UPDATE → Refresh state and status
    """
    
    # Valid state transitions
    TRANSITIONS: list[StateTransition] = [
        StateTransition(
            from_state=WorkflowState.UNINITIALIZED,
            to_state=WorkflowState.INITIALIZING,
            trigger="sdd_init",
            automatic=False
        ),
        StateTransition(
            from_state=WorkflowState.INITIALIZING,
            to_state=WorkflowState.SPEC_REVIEW,
            trigger="prd_generated",
            automatic=True
        ),
        StateTransition(
            from_state=WorkflowState.SPEC_REVIEW,
            to_state=WorkflowState.READY,
            trigger="all_roles_complete",
            required_conditions=["architect_approved", "security_approved"],
            automatic=True
        ),
        StateTransition(
            from_state=WorkflowState.READY,
            to_state=WorkflowState.IMPLEMENTING,
            trigger="task_started",
            automatic=False
        ),
        StateTransition(
            from_state=WorkflowState.IMPLEMENTING,
            to_state=WorkflowState.REVIEWING,
            trigger="commit_requested",
            automatic=False
        ),
        StateTransition(
            from_state=WorkflowState.REVIEWING,
            to_state=WorkflowState.BLOCKED,
            trigger="review_failed",
            automatic=True
        ),
        StateTransition(
            from_state=WorkflowState.REVIEWING,
            to_state=WorkflowState.IMPLEMENTING,
            trigger="review_passed",
            automatic=True
        ),
        StateTransition(
            from_state=WorkflowState.BLOCKED,
            to_state=WorkflowState.IMPLEMENTING,
            trigger="issues_resolved",
            automatic=True
        ),
        StateTransition(
            from_state=WorkflowState.IMPLEMENTING,
            to_state=WorkflowState.COMPLETED,
            trigger="all_tasks_complete",
            automatic=True
        ),
    ]
    
    def __init__(
        self,
        state_manager: "StateManager",
        file_watcher: "FileWatcher",
        role_engine: "RoleEngine",
        enforcement: "EnforcementMiddleware",
        event_bus: "EventBus"
    ):
        self.state_manager = state_manager
        self.file_watcher = file_watcher
        self.role_engine = role_engine
        self.enforcement = enforcement
        self.event_bus = event_bus
        self._running = False
        self._event_queue: asyncio.Queue[WorkflowEvent] = asyncio.Queue()
    
    async def start(self) -> None:
        """Start the execution loop."""
        self._running = True
        await self.file_watcher.start()
        
        # Main execution loop
        while self._running:
            await self._execution_cycle()
            await asyncio.sleep(1)  # Prevent tight loop
    
    async def stop(self) -> None:
        """Stop the execution loop."""
        self._running = False
        await self.file_watcher.stop()
    
    async def _execution_cycle(self) -> None:
        """
        Single iteration of the execution loop.
        
        1. DETECT → Check for events
        2. VALIDATE → Verify compliance
        3. TRIGGER → Execute actions
        4. GUIDE → Update suggestions
        5. UPDATE → Persist state
        """
        # 1. DETECT - Process pending events
        event = await self._get_pending_event()
        if event:
            await self._process_event(event)
        
        # 2. VALIDATE - Check current state validity
        validation_result = await self._validate_current_state()
        
        # 3. TRIGGER - Execute any pending automatic actions
        if validation_result.auto_actions:
            for action in validation_result.auto_actions:
                await self._execute_action(action)
        
        # 4. GUIDE - Update next-step suggestions
        await self._update_guidance()
        
        # 5. UPDATE - Persist state changes
        await self._persist_state()
    
    async def transition_to(self, new_state: WorkflowState) -> bool:
        """
        Attempt to transition to a new state.
        Returns True if transition was valid and completed.
        """
        current = await self.state_manager.get_current_state()
        
        # Find valid transition
        transition = self._find_transition(current, new_state)
        if not transition:
            return False
        
        # Check required conditions
        for condition in transition.required_conditions:
            if not await self._check_condition(condition):
                return False
        
        # Execute transition
        await self.state_manager.set_state(new_state)
        await self.event_bus.emit(WorkflowEvent(
            event_type="state_transition",
            source="orchestrator",
            data={"from": current.value, "to": new_state.value}
        ))
        
        return True
    
    async def get_next_actions(self) -> list[dict]:
        """Get suggested next actions for the user."""
        current_state = await self.state_manager.get_current_state()
        
        actions = {
            WorkflowState.UNINITIALIZED: [
                {"action": "sdd_init", "description": "Initialize the project"}
            ],
            WorkflowState.SPEC_REVIEW: [
                {"action": "sdd_review_run", "description": "Run pending role reviews"}
            ],
            WorkflowState.READY: [
                {"action": "sdd_task_create", "description": "Create implementation tasks"},
                {"action": "goose run", "description": "Start implementing a task"}
            ],
            WorkflowState.BLOCKED: [
                {"action": "resolve_issues", "description": "Fix blocked issues"}
            ],
        }
        
        return actions.get(current_state, [])
```

### 5.7 StateManager

**Purpose:** Persist and manage workflow state with history tracking

```python
# src/sdd_server/core/state_manager.py

from pydantic import BaseModel
from pathlib import Path
import json
from datetime import datetime
from typing import Optional

class StateHistory(BaseModel):
    """Record of a state transition."""
    from_state: str
    to_state: str
    timestamp: float
    trigger: str
    automatic: bool

class FeatureState(BaseModel):
    """State for a single feature."""
    workflow_state: str
    last_updated: float
    role_reviews: dict[str, str]        # role_name -> status
    pending_actions: list[str]
    blocked_reasons: list[str]
    state_history: list[StateHistory] = []

class ProjectState(BaseModel):
    """
    Complete project state snapshot.
    features maps feature_id -> FeatureState.
    Includes a synthetic "__root__" feature for the project-level state.
    Project-level workflow_state is computed as a rollup from feature states.
    """
    features: dict[str, FeatureState]   # feature_id -> FeatureState
    bypasses: list["BypassRecord"] = [] # grace-mode audit log
    last_updated: float

    @property
    def workflow_state(self) -> str:
        """Rollup: blocked > implementing > spec_review > ready > completed > uninitialized."""
        states = [f.workflow_state for f in self.features.values()]
        for priority in ("blocked", "reviewing", "implementing", "spec_review", "initializing", "ready", "completed", "uninitialized"):
            if priority in states:
                return priority
        return "uninitialized"

class StateManager:
    """
    Manages project state persistence.
    State is stored in specs/.metadata.json for durability.
    """
    
    def __init__(self, specs_dir: Path):
        self.specs_dir = specs_dir
        self.metadata_path = specs_dir / ".metadata.json"
        self._state_cache: Optional[ProjectState] = None
    
    async def get_current_state(self) -> "WorkflowState":
        """Get current workflow state."""
        state = await self._load_state()
        from .orchestrator import WorkflowState
        return WorkflowState(state.workflow_state)
    
    async def set_state(self, new_state: "WorkflowState") -> None:
        """Set new workflow state with history tracking."""
        state = await self._load_state()
        old_state = state.workflow_state
        
        # Record transition
        state.state_history.append(StateHistory(
            from_state=old_state,
            to_state=new_state.value,
            timestamp=datetime.now().timestamp(),
            trigger="manual",
            automatic=False
        ))
        
        # Update state
        state.workflow_state = new_state.value
        state.last_updated = datetime.now().timestamp()
        
        await self._save_state(state)
    
    async def get_role_review_status(self, role_name: str) -> Optional[str]:
        """Get review status for a role."""
        state = await self._load_state()
        return state.role_reviews.get(role_name)
    
    async def set_role_review_status(self, role_name: str, status: str) -> None:
        """Update review status for a role."""
        state = await self._load_state()
        state.role_reviews[role_name] = status
        await self._save_state(state)
    
    async def _load_state(self) -> ProjectState:
        """Load state from disk or create default."""
        if self._state_cache:
            return self._state_cache
        
        from .orchestrator import WorkflowState
        
        if self.metadata_path.exists():
            data = json.loads(self.metadata_path.read_text())
            self._state_cache = ProjectState(**data)
        else:
            self._state_cache = ProjectState(
                workflow_state=WorkflowState.UNINITIALIZED.value,
                last_updated=datetime.now().timestamp(),
                features={},
                role_reviews={},
                pending_actions=[],
                blocked_reasons=[]
            )
        
        return self._state_cache
    
    async def _save_state(self, state: ProjectState) -> None:
        """Save state to disk atomically."""
        temp_path = self.metadata_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(state.model_dump(), indent=2))
        temp_path.replace(self.metadata_path)
        self._state_cache = state
```

### 5.8 FileWatcher

**Purpose:** Monitor file system for changes and emit events

```python
# src/sdd_server/core/file_watcher.py

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from pydantic import BaseModel
from pathlib import Path
import asyncio
import fnmatch

class WatchConfig(BaseModel):
    """Configuration for file watching."""
    watch_paths: list[str] = ["specs/", "src/"]
    ignore_patterns: list[str] = [
        "*.pyc", "__pycache__/", ".git/", "*.tmp", "*.swp"
    ]
    debounce_seconds: float = 0.5

class FileChange(BaseModel):
    """Represents a detected file change."""
    path: str
    change_type: str  # "created", "modified", "deleted"
    is_directory: bool

class FileWatcher(FileSystemEventHandler):
    """
    Watches for file system changes and emits events.
    Uses watchdog library for efficient file monitoring.
    """
    
    def __init__(self, event_bus: "EventBus", config: WatchConfig | None = None):
        self.event_bus = event_bus
        self.config = config or WatchConfig()
        self._observer: Observer | None = None
        self._debounce_tasks: dict[str, asyncio.Task] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
    
    async def start(self) -> None:
        """Start watching for file changes."""
        self._loop = asyncio.get_event_loop()
        self._observer = Observer()
        
        for path in self.config.watch_paths:
            if Path(path).exists():
                self._observer.schedule(self, path, recursive=True)
        
        self._observer.start()
    
    async def stop(self) -> None:
        """Stop watching for file changes."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
    
    def on_modified(self, event: FileSystemEvent) -> None:
        if self._should_ignore(event.src_path):
            return
        self._debounce_emit("modified", event.src_path, event.is_directory)
    
    def on_created(self, event: FileSystemEvent) -> None:
        if self._should_ignore(event.src_path):
            return
        self._debounce_emit("created", event.src_path, event.is_directory)
    
    def _should_ignore(self, path: str) -> bool:
        for pattern in self.config.ignore_patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
        return False
    
    def _debounce_emit(self, change_type: str, path: str, is_directory: bool) -> None:
        """Debounce rapid file changes before emitting event."""
        if path in self._debounce_tasks:
            self._debounce_tasks[path].cancel()
        
        async def emit_after_delay():
            await asyncio.sleep(self.config.debounce_seconds)
            from .orchestrator import WorkflowEvent
            await self.event_bus.emit(WorkflowEvent(
                event_type="file_change",
                source="file_watcher",
                data={"path": path, "change_type": change_type}
            ))
        
        if self._loop:
            self._debounce_tasks[path] = asyncio.run_coroutine_threadsafe(
                emit_after_delay(), self._loop
            )
```

### 5.9 EventBus

**Purpose:** Central event dispatching for loose coupling between components

```python
# src/sdd_server/core/event_bus.py

from pydantic import BaseModel
from typing import Callable, Awaitable
from collections import defaultdict

EventHandler = Callable[[BaseModel], Awaitable[None]]

class EventBus:
    """
    Simple event bus for component communication.
    Supports pub/sub pattern with async handlers.
    """
    
    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._event_log: list[BaseModel] = []
        self._max_log_size = 1000
    
    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe to events of a specific type."""
        self._handlers[event_type].append(handler)
    
    async def emit(self, event: BaseModel) -> None:
        """Emit an event to all subscribers."""
        event_type = event.__class__.__name__
        
        # Log event
        self._event_log.append(event)
        if len(self._event_log) > self._max_log_size:
            self._event_log = self._event_log[-self._max_log_size:]
        
        # Notify subscribers
        for handler in self._handlers.get(event_type, []):
            try:
                await handler(event)
            except Exception as e:
                print(f"Event handler error: {e}")
    
    def get_recent_events(self, count: int = 50) -> list[BaseModel]:
        """Get recent events for debugging/display."""
        return self._event_log[-count:]
```

### 5.10 MCP Resources

**Purpose:** Expose spec files as native MCP resources so any MCP client can read them directly, without a tool call.

```python
# src/sdd_server/mcp/resources/specs.py

# Resources are registered with the MCP server using the @server.resource decorator.
# URI scheme: sdd://specs/{path}

# Examples:
#   sdd://specs/prd          -> specs/prd.md
#   sdd://specs/arch         -> specs/arch.md
#   sdd://specs/tasks        -> specs/tasks.md
#   sdd://specs/features/auth/prd  -> specs/auth/prd.md

async def handle_spec_resource(uri: str) -> str:
    """
    Map a sdd://specs/* URI to a spec file and return its content.
    Resources are read-only. Writes must use sdd_spec_write tool.
    Content is cached and invalidated when the underlying file changes.
    """
    ...
```

### 5.11 MCP Prompts

**Purpose:** Expose role definitions as native MCP prompts so any MCP client can invoke a role without going through the full recipe/task execution pipeline.

```python
# src/sdd_server/mcp/prompts/roles.py

# Prompts are registered with the MCP server using the @server.prompt decorator.
# Prompt names: sdd_role_{role_name}
# Each prompt embeds the current spec context automatically.

# Registered prompts:
#   sdd_role_architect        -> Architect system prompt + current specs/arch.md
#   sdd_role_ui_designer      -> UI Designer system prompt + current specs/prd.md
#   sdd_role_interface_designer
#   sdd_role_security_analyst
#   sdd_role_edge_case_analyst
#   sdd_role_senior_developer

async def build_role_prompt(role_name: str, feature: str | None = None) -> list[dict]:
    """
    Build an MCP prompt message list for a given role.
    Injects current spec content as context.
    Returns messages in MCP prompt format (system + optional user message).
    """
    ...
```

---
## 6. MCP Tool Definitions

### 6.1 Tool Overview

The SDD MCP server exposes the following tools for Goose and users:

| Tool | Description | Phase |
|------|-------------|-------|
| `sdd_init` | Initialize project (new or existing) | Foundation |
| `sdd_spec_read` | Read spec file content | Foundation |
| `sdd_spec_write` | Write/update spec file | Foundation |
| `sdd_feature_create` | Create new feature specs | Foundation |
| `sdd_feature_list` | List all features | Foundation |
| `sdd_task_create` | Create new task | Foundation |
| `sdd_task_update` | Update task status | Foundation |
| `sdd_task_list` | List tasks with filters | Foundation |
| `sdd_review_run` | Run role review | Role System |
| `sdd_review_status` | Check review completion | Role System |
| `sdd_commit_check` | Pre-commit validation | Enforcement |
| `sdd_align_check` | Check spec-code alignment | Enforcement |
| `sdd_status` | Get project status | Monitoring |

### 6.2 Tool Specifications

#### `sdd_init`

```python
# MCP Tool Definition

name: "sdd_init"
description: """
Initialize a specs-driven development project.
- For new projects: Accept natural language description, generate structured PRD
- For existing projects: Analyze codebase, extract current architecture
"""

inputSchema:
  type: "object"
  properties:
    project_type:
      type: "string"
      enum: ["new", "existing"]
      description: "Type of project initialization"
    description:
      type: "string"
      description: "Natural language project description (for new projects)"
    tech_stack:
      type: "array"
      items:
        type: "string"
      description: "List of technologies (e.g., ['python', 'fastapi', 'postgresql'])"
    analyze_codebase:
      type: "boolean"
      default: true
      description: "Whether to analyze existing code (for existing projects)"

# Example invocation
{
  "project_type": "new",
  "description": "A REST API for managing user authentication with JWT tokens",
  "tech_stack": ["python", "fastapi", "postgresql"]
}

# Response
{
  "success": true,
  "specs_created": ["specs/prd.md", "specs/arch.md", "specs/tasks.md"],
  "next_steps": [
    "Review generated PRD in specs/prd.md",
    "Run 'sdd_review_run' to get role-based feedback",
    "Start implementing tasks with Goose"
  ]
}
```

#### `sdd_spec_read`

```python
name: "sdd_spec_read"
description: "Read a spec file (prd.md, arch.md, or tasks.md)"

inputSchema:
  type: "object"
  properties:
    spec_type:
      type: "string"
      enum: ["prd", "arch", "tasks"]
      description: "Type of spec to read"
    feature:
      type: "string"
      description: "Feature name (optional, for feature-specific specs)"
    section:
      type: "string"
      description: "Specific section to read (optional)"

# Example
{
  "spec_type": "arch",
  "feature": "authentication"
}
```

#### `sdd_spec_write`

```python
name: "sdd_spec_write"
description: "Write or update a spec file"

inputSchema:
  type: "object"
  required: ["spec_type", "content"]
  properties:
    spec_type:
      type: "string"
      enum: ["prd", "arch", "tasks"]
    feature:
      type: "string"
      description: "Feature name (optional)"
    content:
      type: "string"
      description: "Content to write"
    mode:
      type: "string"
      enum: ["overwrite", "append", "prepend"]
      default: "overwrite"
    validate:
      type: "boolean"
      default: true
      description: "Validate content before writing"

# Example
{
  "spec_type": "tasks",
  "content": "### ta3f2b1c: Implement login endpoint\n\n**Status**: pending\n**Prompt**: Create POST /login endpoint...",
  "mode": "append"
}
```

#### `sdd_feature_create`

```python
name: "sdd_feature_create"
description: "Create a new feature with its spec structure"

inputSchema:
  type: "object"
  required: ["name", "description"]
  properties:
    name:
      type: "string"
      pattern: "^[a-z0-9-]+$"
      description: "Feature name (kebab-case)"
    description:
      type: "string"
      description: "Feature description"
    inherit_context:
      type: "boolean"
      default: true
      description: "Inherit context from parent specs"

# Example
{
  "name": "user-authentication",
  "description": "JWT-based user authentication system",
  "inherit_context": true
}
```

#### `sdd_task_create`

```python
name: "sdd_task_create"
description: "Create a new task in tasks.md"

inputSchema:
  type: "object"
  required: ["title", "prompt"]
  properties:
    title:
      type: "string"
      description: "Task title"
    description:
      type: "string"
      description: "Detailed task description"
    prompt:
      type: "string"
      description: "Executable prompt for Goose"
    feature:
      type: "string"
      description: "Feature to associate with (optional)"
    role:
      type: "string"
      enum: ["architect", "ui-designer", "interface-designer", "security-analyst", "edge-case-analyst", "senior-developer"]
      description: "Assigned role (optional)"
    depends_on:
      type: "array"
      items:
        type: "string"
      description: "Task IDs this depends on (optional)"

# Example
{
  "title": "Implement JWT token generation",
  "description": "Create JWT token generation and validation",
  "prompt": "Implement JWT token generation in auth/utils.py:\n- Use python-jose for JWT\n- Include user_id and expiration\n- Add validation function",
  "feature": "user-authentication",
  "role": "senior-developer"
}

# Response includes generated task_id
{
  "task_id": "tb7e9d2a",
  "status": "pending",
  "message": "Task created in specs/feature-user-authentication/tasks.md"
}
```

#### `sdd_review_run`

```python
name: "sdd_review_run"
description: "Run role-based review on specs or code"

inputSchema:
  type: "object"
  properties:
    scope:
      type: "string"
      enum: ["specs", "code", "all"]
      default: "specs"
    roles:
      type: "array"
      items:
        type: "string"
      description: "Specific roles to run (optional, defaults to all pending)"
    feature:
      type: "string"
      description: "Feature to review (optional)"
    parallel:
      type: "boolean"
      default: true
      description: "Run independent roles in parallel"

# Example
{
  "scope": "specs",
  "roles": ["architect", "security-analyst"],
  "feature": "user-authentication"
}

# Response
{
  "reviews": [
    {
      "role": "architect",
      "status": "complete",
      "feedback": "Architecture is well-structured. Consider adding rate limiting.",
      "suggestions": ["Add rate limiting layer", "Consider token refresh strategy"]
    },
    {
      "role": "security-analyst",
      "status": "complete",
      "feedback": "Security considerations look good. Add token revocation.",
      "suggestions": ["Implement token blacklist", "Add refresh token rotation"]
    }
  ],
  "all_reviews_complete": false,
  "pending_reviews": ["ui-designer", "interface-designer"]
}
```

#### `sdd_commit_check`

```python
name: "sdd_commit_check"
description: "Pre-commit validation (enforced, no bypass)"

inputSchema:
  type: "object"
  properties:
    files:
      type: "array"
      items:
        type: "string"
      description: "Files to check (optional, defaults to staged)"
    checks:
      type: "array"
      items:
        type: "string"
        enum: ["lint", "security", "alignment", "documentation", "all"]
      default: ["all"]

# Example
{
  "checks": ["all"]
}

# Success Response
{
  "allowed": true,
  "checks_passed": ["lint", "security", "alignment", "documentation"],
  "message": "Commit allowed. All quality gates passed."
}

# Failure Response
{
  "allowed": false,
  "checks_failed": ["alignment"],
  "issues": [
    {
      "check": "alignment",
      "issue": "Code implements /logout endpoint not defined in specs",
      "required_action": "Add logout endpoint to specs/feature-user-authentication/prd.md OR remove the endpoint"
    }
  ],
  "guidance": "You must either:\n1. Update specs to include the logout endpoint\n2. Remove the logout endpoint from code\n\nRun 'sdd_spec_write' to update specs."
}
```

#### `sdd_align_check`

```python
name: "sdd_align_check"
description: "Check spec-code alignment"

inputSchema:
  type: "object"
  properties:
    scope:
      type: "string"
      enum: ["all", "feature", "file"]
    target:
      type: "string"
      description: "Feature name or file path (based on scope)"
    auto_suggest:
      type: "boolean"
      default: true
      description: "Generate suggestions for fixing misalignments"

# Example
{
  "scope": "feature",
  "target": "user-authentication"
}

# Response
{
  "status": "diverged",
  "alignment_score": 85,
  "issues": [
    {
      "file": "src/auth/routes.py",
      "spec_ref": "specs/feature-user-authentication/prd.md#logout",
      "status": "missing_spec",
      "description": "/logout endpoint implemented but not in specs",
      "suggested_action": "update_spec"
    }
  ],
  "suggestions": [
    "Add to specs/feature-user-authentication/prd.md:\n\n### Logout Endpoint\n\nPOST /logout - Invalidate user session"
  ]
}
```

#### `sdd_status`

```python
name: "sdd_status"
description: "Get project status and progress"

inputSchema:
  type: "object"
  properties:
    detailed:
      type: "boolean"
      default: false
      description: "Include detailed breakdown"
    feature:
      type: "string"
      description: "Get status for specific feature (optional)"

# Example
{
  "detailed": true
}

# Response
{
  "project": "user-auth-api",
  "overall_completion": 45,
  "features": [
    {
      "name": "authentication",
      "completion": 60,
      "tasks": {
        "total": 10,
        "pending": 4,
        "in_progress": 2,
        "complete": 4
      },
      "reviews": {
        "architect": "complete",
        "ui-designer": "complete",
        "interface-designer": "pending",
        "security-analyst": "complete",
        "edge-case-analyst": "pending",
        "senior-developer": "pending"
      }
    }
  ],
  "blocked_items": [],
  "next_actions": [
    "Run interface-designer review",
    "Complete ta3f2b1c: Implement login endpoint"
  ]
}
```

---
## 7. User Interaction Flow

### 7.1 Design Philosophy

**Goal:** Lower the barrier to entry while maintaining strict enforcement

**Principles:**
1. **Progressive Disclosure:** Start simple, reveal complexity as needed
2. **Guided Workflows:** Clear next steps at every point
3. **Actionable Feedback:** Not just "what's wrong" but "how to fix it"
4. **Visual Clarity:** Rich terminal output with colors, icons, progress bars
5. **Graceful Degradation:** Works even when some features aren't available

### 7.2 New Project Onboarding Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         NEW PROJECT ONBOARDING                               │
└─────────────────────────────────────────────────────────────────────────────┘

Step 1: Initial Invocation
┌─────────────────────────────────────────────────────────────────────────────┐
│ > sdd init                                                                  │
│                                                                             │
│ 🪿 Welcome to Specs-Driven Development!                                     │
│                                                                             │
│ Let's set up your project. I'll guide you through the process.             │
│                                                                             │
│ ? What would you like to do?                                                │
│   ❯ Create a new project                                                    │
│     Add specs to an existing project                                        │
└─────────────────────────────────────────────────────────────────────────────┘

Step 2: Project Description
┌─────────────────────────────────────────────────────────────────────────────┐
│ ? Describe your project in a few sentences:                                 │
│                                                                             │
│ A REST API for user authentication with JWT tokens. It should support      │
│ registration, login, logout, and token refresh. Built with FastAPI.        │
│                                                                             │
│ ─────────────────────────────────────────────────────────────────────────── │
│ 💡 Tip: Include what you're building, key features, and tech stack         │
└─────────────────────────────────────────────────────────────────────────────┘

Step 3: Tech Stack Confirmation
┌─────────────────────────────────────────────────────────────────────────────┐
│ I detected this tech stack. Is this correct?                               │
│                                                                             │
│   ✓ Python                                                                  │
│   ✓ FastAPI                                                                 │
│   ✓ JWT (authentication)                                                    │
│   ? Database (I need more info)                                            │
│                                                                             │
│ ? Which database?                                                           │
│   ❯ PostgreSQL                                                              │
│     SQLite                                                                  │
│     MongoDB                                                                 │
│     Custom (I'll specify)                                                   │
└─────────────────────────────────────────────────────────────────────────────┘

Step 4: PRD Generation
┌─────────────────────────────────────────────────────────────────────────────┐
│ ✨ Generating your Product Requirements Document...                         │
│                                                                             │
│ ████████████████████████████████████████████████████████ 100%              │
│                                                                             │
│ ✓ Created specs/prd.md                                                      │
│ ✓ Created specs/arch.md (initial structure)                                │
│ ✓ Created specs/tasks.md (empty, ready for tasks)                          │
│ ✓ Created specs/.goosehints (Goose context)                                │
│ ✓ Created recipes/ (default role recipes)                                  │
│                                                                             │
│ ─────────────────────────────────────────────────────────────────────────── │
│ 📄 Here's a preview of your PRD:                                           │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ # Product Requirements: User Authentication API                          │ │
│ │                                                                          │ │
│ │ ## Overview                                                              │ │
│ │ A REST API for user authentication with JWT tokens...                   │ │
│ │                                                                          │ │
│ │ ## Features                                                              │ │
│ │ 1. User Registration                                                     │ │
│ │ 2. Login with JWT tokens                                                │ │
│ │ 3. Logout and token invalidation                                        │ │
│ │ 4. Token refresh mechanism                                              │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘

Step 5: Role Review Suggestion
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🎭 Next: Role-Based Review                                                  │
│                                                                             │
│ Your PRD is ready! Before implementing, I recommend getting feedback       │
│ from our specialized roles:                                                 │
│                                                                             │
│   1. Architect     - Define system architecture                            │
│   2. UI Designer   - Plan API interface (endpoints, request/response)     │
│   3. Security      - Analyze security considerations                       │
│   4. Senior Dev    - Ensure KISS principles                                │
│                                                                             │
│ ? Would you like to run the role review now?                               │
│   ❯ Yes, run all roles in sequence                                         │
│     Yes, but let me choose which roles                                     │
│     Skip for now (I'll do it later)                                        │
└─────────────────────────────────────────────────────────────────────────────┘

Step 6: Role Review Execution
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🎭 Running Role Reviews...                                                  │
│                                                                             │
│ Architect     ████████████████████████████████████████ ✓ Complete          │
│ UI Designer   ████████████████████████████████████████ ✓ Complete          │
│ Security      ████████████████████████████████████████ ✓ Complete          │
│ Senior Dev    ████████████████████████████████░░░░░░░░ ⏳ In Progress      │
│                                                                             │
│ ─────────────────────────────────────────────────────────────────────────── │
│ 📋 Feedback Summary:                                                        │
│                                                                             │
│ Architect:                                                                  │
│   ✓ Good separation of concerns                                            │
│   💡 Consider adding rate limiting layer                                   │
│                                                                             │
│ UI Designer:                                                                │
│   ✓ RESTful endpoint design is solid                                       │
│   ⚠️  Missing error response specifications                                │
│                                                                             │
│ Security:                                                                   │
│   ✓ JWT implementation approach is sound                                   │
│   ⚠️  Add token revocation strategy                                        │
│   💡 Consider refresh token rotation                                       │
└─────────────────────────────────────────────────────────────────────────────┘

Step 7: Ready to Implement
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🚀 You're ready to implement!                                               │
│                                                                             │
│ Your specs are complete and reviewed. Here's your next steps:              │
│                                                                             │
│   1. Review and apply role suggestions:                                    │
│      > sdd spec read --type prd                                             │
│                                                                             │
│   2. Create your first task:                                               │
│      > sdd task create "Implement user registration"                        │
│                                                                             │
│   3. Run the task with Goose:                                              │
│      > goose run --recipe developer --prompt "Implement task_001"          │
│                                                                             │
│   4. Check your progress anytime:                                          │
│      > sdd status                                                           │
│                                                                             │
│ 💡 Remember: All code changes require spec alignment. I'll guide you!      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.3 Existing Project Onboarding Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      EXISTING PROJECT ONBOARDING                             │
└─────────────────────────────────────────────────────────────────────────────┘

Step 1: Detection
┌─────────────────────────────────────────────────────────────────────────────┐
│ > sdd init                                                                  │
│                                                                             │
│ 🪿 Welcome to Specs-Driven Development!                                     │
│                                                                             │
│ 🔍 I detected an existing project in this directory.                       │
│                                                                             │
│ Project structure found:                                                    │
│   src/           (Python package)                                          │
│   tests/         (Test suite)                                               │
│   pyproject.toml (Project config)                                          │
│                                                                             │
│ ? I can analyze your codebase and generate specs from it. Continue?        │
│   ❯ Yes, analyze and generate specs                                        │
│     No, I'll provide a description manually                                │
└─────────────────────────────────────────────────────────────────────────────┘

Step 2: Analysis
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🔍 Analyzing your codebase...                                               │
│                                                                             │
│ Scanning Python files...        ████████████████████████ 100%              │
│ Parsing AST...                  ████████████████████████ 100%              │
│ Extracting structure...         ████████████████████████ 100%              │
│ Identifying patterns...         ████████████████████░░░░ 80%               │
│                                                                             │
│ ─────────────────────────────────────────────────────────────────────────── │
│ 📊 Analysis Results:                                                        │
│                                                                             │
│ Detected Components:                                                        │
│   • FastAPI application (main.py)                                          │
│   • User model (models/user.py)                                            │
│   • Authentication routes (routes/auth.py)                                 │
│   • JWT utilities (utils/jwt.py)                                           │
│   • Database layer (database.py)                                           │
│                                                                             │
│ Detected Patterns:                                                          │
│   • Repository pattern (implied)                                           │
│   • Dependency injection (FastAPI style)                                   │
│   • Middleware for authentication                                          │
│                                                                             │
│ ⚠️  Potential Issues:                                                       │
│   • No rate limiting detected                                              │
│   • Missing input validation in 2 endpoints                                │
└─────────────────────────────────────────────────────────────────────────────┘

Step 3: Spec Generation
┌─────────────────────────────────────────────────────────────────────────────┐
│ ✨ Generating specs from codebase analysis...                               │
│                                                                             │
│ ✓ Created specs/prd.md (extracted from code)                               │
│ ✓ Created specs/arch.md (from detected structure)                          │
│ ✓ Created specs/tasks.md (improvement suggestions)                         │
│ ✓ Created specs/.goosehints                                                │
│                                                                             │
│ ⚠️  Note: These specs are generated from existing code.                    │
│    Please review and refine them to match your intent.                     │
│                                                                             │
│ ? Would you like to review the generated PRD now?                          │
│   ❯ Yes, open in editor                                                    │
│     Yes, show in terminal                                                   │
│     Skip for now                                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.4 Commit Enforcement Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COMMIT ENFORCEMENT                                   │
└─────────────────────────────────────────────────────────────────────────────┘

Scenario: User tries to commit without specs

┌─────────────────────────────────────────────────────────────────────────────┐
│ > git commit -m "Add logout endpoint"                                       │
│                                                                             │
│ ❌ COMMIT BLOCKED by SDD Enforcement                                        │
│                                                                             │
│ ─────────────────────────────────────────────────────────────────────────── │
│ 🚫 Issue: Code without corresponding specification                         │
│                                                                             │
│ File: src/routes/auth.py                                                    │
│ Change: Added POST /logout endpoint                                         │
│                                                                             │
│ This endpoint is not defined in your specs.                                │
│                                                                             │
│ ─────────────────────────────────────────────────────────────────────────── │
│ 🛠️  Required Actions (choose one):                                         │
│                                                                             │
│ Option A: Add to specs (Recommended)                                        │
│   > sdd spec write --type prd --append                                      │
│                                                                             │
│   Add this content:                                                         │
│   ---                                                                       │
│   ### Logout Endpoint                                                       │
│                                                                             │
│   **POST /logout**                                                          │
│   - Invalidates the current user's JWT token                               │
│   - Adds token to blacklist                                                │
│   - Returns 204 No Content on success                                      │
│   ---                                                                       │
│                                                                             │
│ Option B: Remove the code                                                   │
│   > git checkout src/routes/auth.py                                        │
│                                                                             │
│ ─────────────────────────────────────────────────────────────────────────── │
│ 💡 Why? Spec-driven development ensures your code is always documented      │
│    and aligned with project requirements.                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.5 Status Dashboard

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ > sdd status                                                                │
│                                                                             │
│ ╭─────────────────────────────────────────────────────────────────────────╮ │
│ │  🪿 Specs-Driven Development Status                                      │ │
│ │                                                                          │ │
│ │  Project: user-auth-api                                                 │ │
│ │  Status: 🟡 In Progress                                                  │ │
│ ╰─────────────────────────────────────────────────────────────────────────╯ │
│                                                                             │
│ 📊 Overall Progress                                                         │
│                                                                             │
│ █████████████████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░ 65%     │
│                                                                             │
│ ─────────────────────────────────────────────────────────────────────────── │
│ 📁 Features                                                                 │
│                                                                             │
│ authentication        ████████████████████████████░░░░░░░░ 75%    4 tasks  │
│ ├── ✅ User registration                                                    │
│ ├── ✅ Login endpoint                                                       │
│ ├── ⏳ Logout endpoint (in progress)                                        │
│ └── ⬚ Token refresh                                                         │
│                                                                             │
│ rate-limiting         ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 25%    1 task   │
│ ├── ✅ Rate limiter middleware                                             │
│ ├── ⬚ Configurable limits                                                  │
│ └── ⬚ Redis backend                                                        │
│                                                                             │
│ ─────────────────────────────────────────────────────────────────────────── │
│ 🎭 Role Reviews                                                             │
│                                                                             │
│ Main Project:                                                               │
│   ✓ architect          (complete)                                          │
│   ✓ ui-designer        (complete)                                          │
│   ✓ interface-designer (complete)                                          │
│   ✓ security-analyst   (complete)                                          │
│   ✓ edge-case-analyst  (complete)                                          │
│   ⏳ senior-developer   (pending)                                           │
│                                                                             │
│ ─────────────────────────────────────────────────────────────────────────── │
│ ⚠️  Blocked Items                                                           │
│                                                                             │
│ None! You're good to go.                                                   │
│                                                                             │
│ ─────────────────────────────────────────────────────────────────────────── │
│ 🎯 Suggested Next Actions                                                   │
│                                                                             │
│   1. Complete senior-developer review                                      │
│      > sdd review run --role senior-developer                              │
│                                                                             │
│   2. Continue implementing logout endpoint                                 │
│      > goose run --task ta3f2b1c                               │
│                                                                             │
│   3. Create token refresh task                                             │
│      > sdd task create "Implement token refresh"                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---
## 8. Goose Integration Patterns

### 8.1 Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         GOOSE INTEGRATION LAYER                              │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────────────────┐
                    │         SDD MCP Server           │
                    │                                  │
                    │  ┌────────────────────────────┐  │
                    │  │    AIClientBridge          │  │
                    │  │                            │  │
                    │  │  - execute_task()          │  │
                    │  │  - invoke_role()           │  │
                    │  │  - run_quality_check()     │  │
                    │  └────────────────────────────┘  │
                    └──────────────────────────────────┘
                                    │
                                    │ subprocess / CLI
                                    ▼
                    ┌──────────────────────────────────┐
                    │         Goose CLI                │
                    │                                  │
                    │  goose run [options]             │
                    │  --recipe <path>                 │
                    │  --prompt <text>                 │
                    │  --config <path>                 │
                    └──────────────────────────────────┘
                                    │
                                    │ reads
                                    ▼
                    ┌──────────────────────────────────┐
                    │         recipes/*.yml            │
                    │                                  │
                    │  - architect.yml                 │
                    │  - ui-designer.yml               │
                    │  - security-analyst.yml          │
                    │  - senior-developer.yml          │
                    │  - code-reviewer.yml             │
                    └──────────────────────────────────┘
                                    │
                                    │ reads context
                                    ▼
                    ┌──────────────────────────────────┐
                    │       specs/.goosehints          │
                    │                                  │
                    │  - Project context               │
                    │  - Architecture decisions        │
                    │  - Constraints                   │
                    └──────────────────────────────────┘
```

### 8.2 Recipe Generation

SDD dynamically generates Goose recipes based on project context:

```yaml
# recipes/architect.yml (Generated)

name: architect
description: Define and review system architecture
version: "1.0"

# Triggered by SDD after PRD creation
triggers:
  - after_prd_creation
  - on_architecture_change

# Context loaded from specs
context:
  - specs/prd.md
  - specs/.goosehints

# Instructions for the role
instructions: |
  You are the System Architect for this project.
  
  Your responsibilities:
  1. Review the PRD and define the system architecture
  2. Identify major components and their relationships
  3. Document technical decisions and their rationale
  4. Define data flow and communication patterns
  5. Consider scalability, maintainability, and security
  
  Output your findings to specs/arch.md using the sdd_spec_write tool.
  
  Focus on:
  - Component diagram
  - Technology choices
  - Data models
  - API contracts
  - Infrastructure requirements

# Expected outputs
outputs:
  - specs/arch.md

# Quality gates
validation:
  required_sections:
    - "Component Overview"
    - "Technology Stack"
    - "Data Models"
    - "API Design"
  
# Interaction settings
interaction:
  ask_clarification: true
  max_turns: 10
```

### 8.3 Task-to-Goose Bridge

Tasks in `tasks.md` are formatted for direct Goose execution:

```markdown
# specs/tasks.md

### tb7e9d2a: Implement user registration

**Description**: Create user registration endpoint with validation

**Status**: pending

**Priority**: high

**Assigned Role**: senior-developer

**Dependencies**: None

**Prompt for Goose**:
```
Implement the user registration endpoint in src/routes/auth.py:

Requirements:
- POST /register endpoint
- Accept email, password, name in request body
- Validate email format and password strength
- Hash password with bcrypt
- Store user in PostgreSQL database
- Return 201 with user ID on success
- Return 400 with validation errors

Files to create/modify:
- src/routes/auth.py (add endpoint)
- src/schemas/user.py (add request/response schemas)
- tests/test_auth.py (add tests)

Reference:
- specs/prd.md#user-registration
- specs/arch.md#api-layer
```

---

### tc1f4e8b: Add rate limiting

**Description**: Implement rate limiting middleware

**Status**: pending

**Priority**: medium

**Assigned Role**: senior-developer

**Dependencies**: tb7e9d2a

**Prompt for Goose**:
```
Implement rate limiting in src/middleware/rate_limit.py:

Requirements:
- Limit requests per IP address
- Default: 100 requests per minute
- Return 429 Too Many Requests when exceeded
- Add X-RateLimit headers

Files to create/modify:
- src/middleware/rate_limit.py
- src/main.py (add middleware)

Reference:
- specs/arch.md#rate-limiting
```
```

### 8.4 `.goosehints` Management

SDD automatically generates and maintains `.goosehints` files:

```markdown
# specs/.goosehints (Generated by SDD)

## Project Context

This is a Specs-Driven Development project. All code changes must align with
specifications in this directory.

## Project Overview

- **Name**: User Authentication API
- **Type**: REST API
- **Tech Stack**: Python, FastAPI, PostgreSQL, JWT

## Key Architecture Decisions

1. **Authentication**: JWT tokens with 1-hour expiration
2. **Database**: PostgreSQL with SQLAlchemy ORM
3. **API Style**: RESTful with OpenAPI documentation
4. **Validation**: Pydantic models for request/response

## Constraints

- All endpoints must have corresponding specs in prd.md
- Security reviews required for authentication changes
- Follow the architecture defined in arch.md

## Current Features

- `authentication` - User auth with JWT (75% complete)
- `rate-limiting` - Request rate limiting (25% complete)

## Spec Files

- `prd.md` - Product requirements
- `arch.md` - Technical architecture
- `tasks.md` - Implementation tasks

## Commands

- Check status: `sdd status`
- Run review: `sdd review run`
- Check alignment: `sdd align check`
```

### 8.5 Execution Flow

```
User Action: sdd task run tb7e9d2a
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ SDD Server                                                                   │
│                                                                              │
│ 1. Validate task exists and is pending                                      │
│ 2. Check dependencies are complete                                          │
│ 3. Check enforcement rules (specs exist)                                    │
│ 4. Read task prompt from tasks.md                                           │
│ 5. Build Goose command                                                      │
│    goose run --recipe senior-developer --prompt "..."                       │
│ 6. Execute Goose (stream output)                                            │
│ 7. Monitor completion                                                       │
│ 8. Update task status to "in_progress" → "complete"                         │
│ 9. Run alignment check                                                      │
│ 10. Prompt user for commit if aligned                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
            Task Complete or Blocked
```

### 8.6 Parallel Role Execution

For independent roles, SDD runs them concurrently:

```python
# Pseudo-code for parallel execution

async def run_parallel_reviews(self, roles: list[str]) -> list[RoleResult]:
    """
    Run multiple roles in parallel using asyncio.
    """
    tasks = [
        self.goose_bridge.invoke_role(role, context)
        for role in roles
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Aggregate and present results
    return self._aggregate_results(results)
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Parallel Review Execution                                                   │
│                                                                              │
│ Time ──►                                                                    │
│                                                                              │
│ architect     ████████████████████████████ ✓                               │
│ ui-designer   ████████████████████████████ ✓                               │
│ security      ████████████████████████████ ✓                               │
│                      │                                                       │
│                      ▼                                                       │
│              All complete → Aggregate results                               │
│                                                                              │
│ Total time: ~30s (instead of ~90s sequential)                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.7 Goose Recipe Schema

All SDD role recipes follow the standard Goose recipe format with the following enhancements:

#### Core Recipe Structure

```yaml
version: "1.0.0"
title: "Role Name — Project Name"
description: "Description of what the role does"

instructions: |
  Detailed instructions for the role...
  (Multi-line YAML block)

prompt: |
  Short prompt for headless execution.
  References spec files and output tool.

activities:
  - "Activity 1 description"
  - "Activity 2 description"

extensions:
  - type: builtin
    name: developer

parameters:
  - key: feature
    input_type: string
    requirement: optional
    default: ""
    description: Feature subdirectory to focus on

response:
  json_schema:
    type: object
    properties:
      spec_updated:
        type: boolean
      findings_count:
        type: integer
      # ... additional structured output fields
    required:
      - spec_updated

retry:
  max_retries: 2
  timeout_seconds: 300
  checks:
    - type: shell
      command: "test -f specs/arch.md"
  on_failure: "echo 'Role failed. Ensure spec files exist.'"
```

#### Recipe Fields Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | String | - | Recipe format version (default: "1.0.0") |
| `title` | String | ✅ | Short title describing the recipe |
| `description` | String | ✅ | Detailed description of what the recipe does |
| `instructions` | String | ✅* | Template instructions (can include parameter substitutions) |
| `prompt` | String | ✅* | Short prompt for headless mode execution |
| `activities` | Array | - | List of clickable activity bubbles (Desktop only) |
| `extensions` | Array | - | Extension configurations (typically `type: builtin, name: developer`) |
| `parameters` | Array | - | Parameter definitions for dynamic recipes |
| `response` | Object | - | Structured output schema for automation workflows |
| `retry` | Object | - | Automated retry logic with success validation |

*At least one of `instructions` or `prompt` must be provided.

#### Response Schema

The `response` field defines structured output for automation workflows:
- Enables validation of role execution results
- Provides consistent interface for CI/CD integration
- Supports JSON Schema for type safety

Example:
```yaml
response:
  json_schema:
    type: object
    properties:
      spec_updated:
        type: boolean
        description: Whether the spec file was updated
      findings_count:
        type: integer
        description: Number of findings identified
      critical_issues:
        type: array
        items:
          type: string
        description: List of critical issues found
    required:
      - spec_updated
```

#### Retry Configuration

The `retry` field enables automated retry with success validation:
- `max_retries`: Number of retry attempts (recommended: 2)
- `timeout_seconds`: Maximum execution time (default: 300)
- `checks`: Array of shell commands to validate success
- `on_failure`: Shell command to run on failure

Example:
```yaml
retry:
  max_retries: 2
  timeout_seconds: 300
  checks:
    - type: shell
      command: "test -f specs/arch.md"
    - type: shell
      command: "grep -q '## Component' specs/arch.md"
  on_failure: "echo 'Role failed. Ensure spec files exist.'"
```

#### File Extension

**Important**: Recipe files must use `.yaml` extension (not `.yml`) for goose CLI compatibility.

#### Role Recipes

| Role | Recipe File | Purpose |
|------|-------------|---------|
| Architect | `recipes/architect.yaml` | System structure, tech stack, data flow |
| UI/UX Designer | `recipes/ui-designer.yaml` | CLI, config, env vars, error messages |
| Interface Designer | `recipes/interface-designer.yaml` | APIs, file formats, integration contracts |
| Security Analyst | `recipes/security-analyst.yaml` | Threat model, input validation, auth |
| Edge Case Analyst | `recipes/edge-case-analyst.yaml` | Boundary conditions, failure modes |
| Senior Developer | `recipes/senior-developer.yaml` | KISS review, task breakdown, test strategy |

#### Running Recipes

```bash
# Run a single role
goose run --recipe specs/recipes/architect.yaml

# Run with feature parameter
goose run --recipe specs/recipes/security-analyst.yaml --param feature=auth

# Run all roles in sequence
for recipe in specs/recipes/*.yaml; do
  goose run --recipe "$recipe"
done
```

---
## 9. Plugin Architecture

### 9.1 Plugin System Overview

SDD uses a plugin architecture for extensibility:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PLUGIN ARCHITECTURE                                  │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────────────────┐
                    │        PluginLoader              │
                    │                                  │
                    │  - discover_plugins()            │
                    │  - load_plugin()                 │
                    │  - validate_plugin()             │
                    │  - register_plugin()             │
                    └──────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
            ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
            │ Role Plugins │ │ Analyzer     │ │ Linter       │
            │              │ │ Plugins     │ │ Plugins     │
            │ - architect  │ │ - python    │ │ - ruff      │
            │ - ui-design  │ │ - rust      │ │ - eslint    │
            │ - security   │ │ - typescript│ │ - clippy    │
            │ - senior-dev │ │ - go        │ │ - prettier  │
            └──────────────┘ └──────────────┘ └──────────────┘
```

### 9.2 Plugin Base Classes

```python
# src/sdd_server/plugins/base.py

from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any

class PluginMetadata(BaseModel):
    name: str
    version: str
    description: str
    author: str
    priority: int = 100  # Lower = higher priority

class BasePlugin(ABC):
    """Base class for all SDD plugins."""
    
    metadata: PluginMetadata
    
    @abstractmethod
    async def initialize(self, context: dict) -> None:
        """Initialize plugin with context."""
        ...
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Cleanup plugin resources."""
        ...

# === Role Plugin ===

class RolePlugin(BasePlugin):
    """Base class for role plugins."""
    
    @abstractmethod
    async def review(
        self, 
        scope: str,  # "specs" | "code" | "all"
        target: str | None = None
    ) -> RoleResult:
        """
        Perform role-specific review.
        
        Returns:
            RoleResult with feedback, suggestions, and issues
        """
        ...
    
    @abstractmethod
    def get_recipe_template(self) -> str:
        """Return Jinja2 template for Goose recipe."""
        ...
    
    @abstractmethod
    def get_dependencies(self) -> list[str]:
        """Return list of role names this role depends on."""
        ...

# === Code Analyzer Plugin ===

class CodeAnalyzerPlugin(BasePlugin):
    """Base class for code analyzer plugins."""
    
    @abstractmethod
    def get_supported_extensions(self) -> list[str]:
        """Return list of supported file extensions."""
        ...
    
    @abstractmethod
    async def analyze_file(self, file_path: Path) -> dict:
        """
        Analyze a single file.
        
        Returns:
            {
                "classes": [...],
                "functions": [...],
                "imports": [...],
                "exports": [...],
                "patterns": [...]
            }
        """
        ...
    
    @abstractmethod
    async def analyze_project(self, root: Path) -> dict:
        """
        Analyze entire project.
        
        Returns:
            {
                "structure": {...},
                "components": [...],
                "dependencies": [...]
            }
        """
        ...

# === Linter Plugin ===

class LinterPlugin(BasePlugin):
    """Base class for linter integration plugins."""
    
    @abstractmethod
    def get_command(self, files: list[Path]) -> list[str]:
        """Return command to run linter."""
        ...
    
    @abstractmethod
    def parse_output(self, output: str) -> list[LintIssue]:
        """Parse linter output into structured format."""
        ...
    
    @abstractmethod
    def get_fix_command(self, files: list[Path]) -> list[str] | None:
        """Return command to auto-fix issues (if supported)."""
        ...
```

### 9.3 Built-in Role Plugins

```python
# src/sdd_server/plugins/roles/architect.py

from sdd_server.plugins.base import RolePlugin, RoleResult

class ArchitectRole(RolePlugin):
    """
    Architect role plugin.
    
    Responsibilities:
    - Define system components
    - Document technical decisions
    - Design data flow
    - Identify dependencies
    """
    
    metadata = PluginMetadata(
        name="architect",
        version="1.0.0",
        description="System architecture design and review",
        author="SDD Team",
        priority=10  # High priority - runs first
    )
    
    async def review(self, scope: str, target: str | None = None) -> RoleResult:
        # Implementation uses Goose to perform review
        ...
    
    def get_recipe_template(self) -> str:
        return """
name: architect
description: {{ description }}
instructions: |
  You are the System Architect.
  
  Review the project and provide:
  1. Component diagram
  2. Technology recommendations
  3. Data flow analysis
  4. Security considerations
  5. Scalability assessment
  
  Write your findings to specs/arch.md.
"""
    
    def get_dependencies(self) -> list[str]:
        return []  # No dependencies - runs first
```

```python
# src/sdd_server/plugins/roles/security_analyst.py

class SecurityAnalystRole(RolePlugin):
    """
    Security analyst role plugin.
    
    Responsibilities:
    - Identify security vulnerabilities
    - Review authentication/authorization
    - Check for common attack vectors
    - Validate security configurations
    """
    
    metadata = PluginMetadata(
        name="security-analyst",
        version="1.0.0",
        description="Security analysis and review",
        author="SDD Team",
        priority=30
    )
    
    async def review(self, scope: str, target: str | None = None) -> RoleResult:
        ...
    
    def get_dependencies(self) -> list[str]:
        return ["architect", "interface-designer"]
```

```python
# src/sdd_server/plugins/roles/edge_case_analyst.py

from sdd_server.plugins.base import RolePlugin, PluginMetadata, RoleResult

class EdgeCaseAnalystRole(RolePlugin):
    """
    Edge case analyst role plugin.
    
    Responsibilities:
    - Identify edge cases in user interactions
    - Analyze data flow edge cases
    - Review process flow edge cases
    - Generate test scenarios for edge cases
    """
    
    metadata = PluginMetadata(
        name="edge-case-analyst",
        version="1.0.0",
        description="Edge case analysis for user, data, and process flows",
        author="SDD Team",
        priority=40
    )
    
    async def review(self, scope: str, target: str | None = None) -> RoleResult:
        """
        Analyze specs for potential edge cases.
        
        Domains analyzed:
        1. User Interaction Edge Cases
           - Invalid inputs (empty, null, malformed, oversized)
           - Unexpected sequences (skip steps, go back, repeat)
           - Boundary conditions (min/max values, edge formats)
           - Concurrent actions (race conditions)
        
        2. Data Flow Edge Cases
           - Empty/null/missing data scenarios
           - Data transformation failures
           - Invalid data states (corrupted, partial, stale)
           - Circular references
           - Size limits (overflow, truncation)
        
        3. Process Flow Edge Cases
           - Interrupted workflows (crash, timeout, cancellation)
           - Out-of-order operations
           - Retry scenarios and idempotency
           - Rollback requirements
           - External dependency failures
        """
        ...
    
    def get_dependencies(self) -> list[str]:
        return ["architect", "interface-designer", "security-analyst"]
    
    def get_edge_case_template(self) -> str:
        """Template for documenting edge cases."""
        return """
## Edge Case: {title}

**Domain:** {domain}  # user_interaction | data_flow | process_flow
**Trigger:** {trigger_description}
**Expected Behavior:** {expected_behavior}
**Test Scenario:** {test_scenario}
**Priority:** {priority}  # high | medium | low
**Related Spec:** {spec_reference}
"""
```

### 9.4 Codebase Summarizer (replaces AST Analyzers)

> **Note:** Language-specific AST analyzers (`libcst`, `tree-sitter`) are **not** used in the MVP.
> The `CodebaseSummarizer` provides a lightweight, language-agnostic file tree and diff summary
> that is passed to the LLM for semantic alignment analysis.

```python
# src/sdd_server/core/codebase_summary.py

import ast  # stdlib — used only for Python file validation, not deep analysis
from pathlib import Path

class CodebaseSummarizer:
    """
    Produces focused codebase summaries for LLM-based alignment checks.
    Language-agnostic: works for Python, Rust, TypeScript, Go, etc.
    """

    def __init__(self, project_root: Path, source_dirs: list[str], max_tokens: int = 8000):
        self.project_root = project_root
        self.source_dirs = source_dirs
        self.max_tokens = max_tokens

    def file_tree(self) -> str:
        """Return a filtered file listing of source directories."""
        ...

    def focused_diff(self, base: str = "HEAD") -> str:
        """Return git diff bounded by token budget."""
        ...

    def read_key_files(self, file_paths: list[Path]) -> str:
        """Read specific files mentioned in spec sections, bounded by token budget."""
        ...
```

### 9.5 Plugin Discovery

```python
# src/sdd_server/plugins/loader.py

import importlib
from pathlib import Path

class PluginLoader:
    """
    Discovers and loads plugins from:
    1. Built-in plugins (src/sdd_server/plugins/roles/, analyzers/, linters/)
    2. User plugins (SDD_PLUGINS_PATH environment variable)
    3. Installed packages (entry points)
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.registry: dict[str, BasePlugin] = {}
    
    async def discover_plugins(self) -> list[type[BasePlugin]]:
        """Discover all available plugins."""
        plugins = []
        
        # 1. Built-in plugins
        plugins.extend(self._discover_builtins())
        
        # 2. User plugins from path
        if self.config.plugins_path:
            plugins.extend(self._discover_from_path(self.config.plugins_path))
        
        # 3. Entry point plugins
        plugins.extend(self._discover_from_entry_points())
        
        return plugins
    
    async def load_plugin(self, plugin_class: type[BasePlugin]) -> BasePlugin:
        """Instantiate and initialize a plugin."""
        plugin = plugin_class()
        await plugin.initialize(self._get_context())
        return plugin
    
    def register_plugin(self, plugin: BasePlugin) -> None:
        """Register plugin in the registry."""
        self.registry[plugin.metadata.name] = plugin
    
    def get_plugin(self, name: str) -> BasePlugin | None:
        """Get plugin by name."""
        return self.registry.get(name)
```

---
## 10. Data Models

### 10.1 Core Models

```python
# src/sdd_server/models/project.py

from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class ProjectType(str, Enum):
    NEW = "new"
    EXISTING = "existing"

class ProjectMetadata(BaseModel):
    """Project metadata stored in specs/.metadata.json"""
    
    name: str
    description: str
    project_type: ProjectType
    tech_stack: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    
    # Feature tracking
    features: list[str] = Field(default_factory=list)
    
    # Role completion tracking
    role_reviews: dict[str, str] = Field(default_factory=dict)  # role -> status
    
    # Configuration
    config: dict = Field(default_factory=dict)
```

```python
# src/sdd_server/models/spec.py

from pydantic import BaseModel, Field
from enum import Enum

class SpecType(str, Enum):
    PRD = "prd"
    ARCH = "arch"
    TASKS = "tasks"

class SpecSection(BaseModel):
    """Represents a section within a spec file."""
    
    title: str
    level: int  # Markdown heading level
    content: str
    line_start: int
    line_end: int

class SpecFile(BaseModel):
    """Represents a parsed spec file."""
    
    spec_type: SpecType
    feature: str | None = None
    path: str
    
    # Parsed content
    raw_content: str
    sections: list[SpecSection] = Field(default_factory=list)
    
    # Metadata
    last_modified: datetime
    word_count: int
    is_valid: bool = True
    validation_errors: list[str] = Field(default_factory=list)
```

```python
# src/sdd_server/models/task.py

from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    BLOCKED = "blocked"

class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Task(BaseModel):
    """Represents a task in tasks.md."""
    
    id: str  # e.g., "tb7e9d2a"
    title: str
    description: str
    prompt: str  # Executable prompt for Goose
    
    # Status tracking
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    
    # Associations
    feature: str | None = None
    role: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    # Execution info
    goose_session_id: str | None = None
    execution_log: str | None = None

class TaskList(BaseModel):
    """Represents the entire tasks.md file."""
    
    feature: str | None = None
    tasks: list[Task] = Field(default_factory=list)
    
    def get_by_id(self, task_id: str) -> Task | None:
        return next((t for t in self.tasks if t.id == task_id), None)
    
    def get_pending(self) -> list[Task]:
        return [t for t in self.tasks if t.status == TaskStatus.PENDING]
    
    def get_by_status(self, status: TaskStatus) -> list[Task]:
        return [t for t in self.tasks if t.status == status]
```

```python
# src/sdd_server/models/role.py

from pydantic import BaseModel, Field
from enum import Enum

class RoleStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"

class RoleResult(BaseModel):
    """Result from a role execution."""
    
    role: str
    status: RoleStatus
    success: bool
    
    # Feedback
    output: str
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    
    # Metadata
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    
    # Goose integration
    goose_session_id: str | None = None

class RoleDefinition(BaseModel):
    """Definition of a role (loaded from recipe)."""
    
    name: str
    description: str
    version: str = "1.0"
    
    # Triggers
    triggers: list[str] = Field(default_factory=list)
    
    # Dependencies
    dependencies: list[str] = Field(default_factory=list)
    
    # Context
    context_files: list[str] = Field(default_factory=list)
    
    # Output
    outputs: list[str] = Field(default_factory=list)
    
    # Validation
    required_sections: list[str] = Field(default_factory=list)
```

```python
# src/sdd_server/models/recipe.py

from pydantic import BaseModel, Field
from pathlib import Path

class GooseRecipe(BaseModel):
    """Goose recipe structure."""
    
    name: str
    description: str
    version: str = "1.0"
    
    # Instructions
    instructions: str
    context: list[str] = Field(default_factory=list)
    
    # Outputs
    outputs: list[str] = Field(default_factory=list)
    
    # Settings
    interaction: dict = Field(default_factory=dict)
    validation: dict = Field(default_factory=dict)
    
    def to_yaml(self) -> str:
        """Serialize to YAML format for Goose."""
        ...
    
    @classmethod
    def from_yaml(cls, yaml_content: str) -> "GooseRecipe":
        """Parse from YAML."""
        ...
```

```python
# src/sdd_server/models/alignment.py

from pydantic import BaseModel, Field
from pathlib import Path
from enum import Enum

class AlignmentStatus(str, Enum):
    ALIGNED = "aligned"
    DIVERGED = "diverged"
    MISSING_SPEC = "missing_spec"
    MISSING_CODE = "missing_code"

class AlignmentIssue(BaseModel):
    """Single alignment issue."""
    
    file: Path
    spec_ref: str  # Reference to spec section
    status: AlignmentStatus
    description: str
    suggested_action: str  # "update_spec" | "update_code" | "create_spec"
    
    # Details
    code_snippet: str | None = None
    spec_snippet: str | None = None

class AlignmentReport(BaseModel):
    """Full alignment report."""
    
    overall_status: AlignmentStatus
    alignment_score: int  # 0-100
    
    issues: list[AlignmentIssue] = Field(default_factory=list)
    
    # Summary
    summary: dict[str, int] = Field(default_factory=dict)
    # e.g., {"aligned": 10, "diverged": 2, "missing_spec": 1}
    
    # Timestamps
    checked_at: datetime
    
    # Scope
    scope: str  # "all" | "feature:name" | "file:path"
```

---
## 11. Error Handling & Recovery

### 11.1 Error Categories

```python
# src/sdd_server/utils/errors.py

from enum import Enum

class ErrorCategory(str, Enum):
    # File system errors
    FILE_NOT_FOUND = "file_not_found"
    FILE_PERMISSION = "file_permission"
    FILE_CORRUPTED = "file_corrupted"
    
    # Validation errors
    INVALID_SPEC = "invalid_spec"
    INVALID_INPUT = "invalid_input"
    VALIDATION_FAILED = "validation_failed"
    
    # Enforcement errors
    ACTION_BLOCKED = "action_blocked"
    MISSING_SPEC = "missing_spec"
    REVIEW_REQUIRED = "review_required"
    
    # Integration errors
    GOOSE_NOT_FOUND = "goose_not_found"
    GOOSE_EXECUTION_FAILED = "goose_execution_failed"
    RECIPE_INVALID = "recipe_invalid"
    
    # Plugin errors
    PLUGIN_NOT_FOUND = "plugin_not_found"
    PLUGIN_LOAD_FAILED = "plugin_load_failed"
    
    # Git errors
    NOT_A_GIT_REPO = "not_a_git_repo"
    GIT_OPERATION_FAILED = "git_operation_failed"

class SDDError(Exception):
    """Base SDD error with actionable guidance."""
    
    def __init__(
        self, 
        message: str, 
        category: ErrorCategory,
        guidance: str | None = None,
        required_actions: list[str] | None = None
    ):
        super().__init__(message)
        self.category = category
        self.guidance = guidance or self._default_guidance()
        self.required_actions = required_actions or []
    
    def _default_guidance(self) -> str:
        """Default guidance based on category."""
        guidance_map = {
            ErrorCategory.FILE_NOT_FOUND: "Create the missing file or check the path.",
            ErrorCategory.ACTION_BLOCKED: "Complete the required actions before proceeding.",
            ErrorCategory.GOOSE_NOT_FOUND: "Install Goose CLI: https://github.com/block/goose",
        }
        return guidance_map.get(self.category, "Check the error and try again.")
    
    def to_user_message(self) -> str:
        """Format error for user display."""
        lines = [
            f"❌ Error: {super().__str__()}",
            "",
            f"📋 Category: {self.category.value}",
        ]
        
        if self.guidance:
            lines.extend(["", f"💡 Guidance:", self.guidance])
        
        if self.required_actions:
            lines.extend(["", "🔧 Required Actions:"])
            for i, action in enumerate(self.required_actions, 1):
                lines.append(f"  {i}. {action}")
        
        return "\n".join(lines)
```

### 11.2 Recovery Strategies

```python
# src/sdd_server/utils/recovery.py

from pathlib import Path

class RecoveryManager:
    """
    Handles recovery from common error states.
    Uses git as the source of truth for recovery.
    """
    
    async def recover_spec_file(self, spec_path: Path) -> bool:
        """
        Recover a corrupted spec file from git.
        
        1. Check if file exists in git history
        2. Restore last known good version
        3. Notify user of recovery
        """
        ...
    
    async def recover_metadata(self) -> bool:
        """
        Rebuild metadata from spec files.
        
        Used when metadata.json is corrupted or missing.
        """
        ...
    
    async def create_backup(self, path: Path) -> Path:
        """Create a backup before risky operation."""
        ...
    
    async def rollback(self, backup_path: Path) -> None:
        """Rollback to a previous state."""
        ...
```

### 11.3 Graceful Degradation

```python
# Graceful degradation patterns

class SDDServer:
    """
    Server design allows graceful degradation.
    """
    
    async def run_review(self, roles: list[str]) -> ReviewResult:
        """
        If Goose is unavailable, fall back to basic checks.
        """
        if not await self.goose_bridge.is_available():
            # Graceful degradation: run basic checks without Goose
            return await self._run_basic_review(roles)
        
        return await self._run_goose_review(roles)
    
    async def check_alignment(self) -> AlignmentReport:
        """
        If AST analyzer fails, use text-based comparison.
        """
        try:
            return await self._ast_alignment_check()
        except AnalyzerError:
            # Graceful degradation: text-based check
            return await self._text_alignment_check()
```

---

## 12. Testing Strategy

### 12.1 Test Pyramid

```
                    ┌───────────┐
                   │    E2E    │  (10%)
                  │  Tests    │  - Full workflow tests
                 └───────────┘  - Slow, comprehensive
                ┌─────────────────┐
               │  Integration    │  (30%)
              │     Tests       │  - MCP tool tests
             └─────────────────┘  - Goose bridge tests
            ┌───────────────────────┐
           │      Unit Tests       │  (60%)
          │                       │  - Component tests
         └───────────────────────┘  - Fast, isolated
```

### 12.2 Test Categories

```python
# tests/conftest.py

import pytest
from pathlib import Path
from sdd_server.core import SpecManager, RoleEngine

@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory with specs."""
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    
    # Create basic spec files
    (specs_dir / "prd.md").write_text("# Test Project\n\nTest PRD content")
    (specs_dir / "arch.md").write_text("# Architecture\n\nTest arch")
    (specs_dir / "tasks.md").write_text("# Tasks\n\nNo tasks yet")
    
    return tmp_path

@pytest.fixture
def spec_manager(temp_project: Path) -> SpecManager:
    """Create a SpecManager instance for testing."""
    return SpecManager(
        specs_dir=temp_project / "specs",
        templates_dir=Path("templates")
    )

@pytest.fixture
def mock_goose():
    """Mock Goose CLI for testing."""
    class MockGoose:
        async def execute_task(self, *args, **kwargs):
            return GooseResult(success=True, output="Mock output")
        
        async def invoke_role(self, *args, **kwargs):
            return GooseResult(success=True, output="Mock review")
    
    return MockGoose()
```

### 12.3 Example Tests

```python
# tests/unit/test_spec_manager.py

import pytest
from sdd_server.core import SpecManager

class TestSpecManager:
    """Unit tests for SpecManager."""
    
    @pytest.mark.asyncio
    async def test_read_prd(self, spec_manager: SpecManager):
        """Test reading PRD content."""
        content = await spec_manager.read_prd()
        assert "Test Project" in content
        assert "Test PRD content" in content
    
    @pytest.mark.asyncio
    async def test_write_prd_atomic(self, spec_manager: SpecManager):
        """Test that PRD writes are atomic."""
        new_content = "# Updated PRD\n\nNew content"
        await spec_manager.write_prd(new_content)
        
        # Verify write
        content = await spec_manager.read_prd()
        assert content == new_content
    
    @pytest.mark.asyncio
    async def test_create_feature(self, spec_manager: SpecManager):
        """Test feature creation."""
        feature_path = await spec_manager.create_feature(
            name="test-feature",
            description="Test feature description"
        )
        
        assert feature_path.exists()
        assert (feature_path / "prd.md").exists()
        assert (feature_path / "arch.md").exists()
        assert (feature_path / "tasks.md").exists()
    
    @pytest.mark.asyncio
    async def test_feature_name_validation(self, spec_manager: SpecManager):
        """Test that invalid feature names are rejected."""
        with pytest.raises(ValidationError):
            await spec_manager.create_feature(
                name="Invalid Name!",  # Spaces and special chars
                description="Test"
            )
```

```python
# tests/integration/test_mcp_tools.py

import pytest
from sdd_server.mcp import MCPClient

class TestMCPTools:
    """Integration tests for MCP tools."""
    
    @pytest.mark.asyncio
    async def test_sdd_init_new_project(self, tmp_path):
        """Test sdd_init for new project."""
        client = MCPClient(project_root=tmp_path)
        
        result = await client.call_tool("sdd_init", {
            "project_type": "new",
            "description": "Test API project",
            "tech_stack": ["python", "fastapi"]
        })
        
        assert result["success"]
        assert "specs/prd.md" in result["specs_created"]
    
    @pytest.mark.asyncio
    async def test_sdd_commit_check_blocked(self, temp_project):
        """Test that commits are blocked without specs."""
        client = MCPClient(project_root=temp_project)
        
        # Add code without corresponding spec
        (temp_project / "src" / "new_file.py").write_text("def new_func(): pass")
        
        result = await client.call_tool("sdd_commit_check", {
            "checks": ["alignment"]
        })
        
        assert not result["allowed"]
        assert len(result["issues"]) > 0
```

```python
# tests/e2e/test_new_project.py

import pytest
import subprocess
from pathlib import Path

class TestNewProjectE2E:
    """End-to-end tests for new project workflow."""
    
    @pytest.mark.asyncio
    async def test_full_new_project_workflow(self, tmp_path: Path):
        """Test complete workflow from init to first commit."""
        
        # 1. Initialize project
        result = subprocess.run(
            ["sdd", "init"],
            cwd=tmp_path,
            input="New test project\npython\n",
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert (tmp_path / "specs" / "prd.md").exists()
        
        # 2. Create a task
        result = subprocess.run(
            ["sdd", "task", "create", "Implement hello world"],
            cwd=tmp_path,
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # 3. Check status
        result = subprocess.run(
            ["sdd", "status"],
            cwd=tmp_path,
            capture_output=True,
            text=True
        )
        assert "pending" in result.stdout.lower()
```

### 12.4 Test Coverage Requirements

| Component | Target Coverage |
|-----------|-----------------|
| Core Services | 90% |
| MCP Tools | 85% |
| Plugin System | 80% |
| CLI Commands | 75% |
| Utilities | 85% |
| **Overall** | **80%** |

---
## 13. Implementation Roadmap

### 13.1 Phase 1: Foundation (Weeks 1-3)

**Goal:** Core infrastructure and spec management

```
Week 1: Project Setup
├── Day 1-2: Project scaffolding
│   ├── uv init sdd-server
│   ├── pyproject.toml configuration
│   ├── uv add dependencies
│   ├── Directory structure
│   ├── CI/CD configuration (uv-based)
│   └── Development environment docs
│
├── Day 3-4: Core models
│   ├── models/spec.py
│   ├── models/task.py
│   ├── models/project.py
│   └── models/role.py
│
└── Day 5: Infrastructure
    ├── infrastructure/filesystem.py
    ├── infrastructure/git.py
    └── utils/logging.py

Week 2: Spec Management
├── Day 1-2: SpecManager implementation
│   ├── read_prd/arch/tasks
│   ├── write operations (atomic)
│   └── Validation
│
├── Day 3-4: Feature management
│   ├── create_feature
│   ├── list_features
│   └── Context inheritance
│
└── Day 5: Templates
    ├── templates/specs/*.j2
    └── infrastructure/templates.py

Week 3: MCP Server Setup
├── Day 1-2: MCP server skeleton
│   ├── mcp/server.py
│   └── Tool registration
│
├── Day 3-4: Basic MCP tools
│   ├── sdd_init
│   ├── sdd_spec_read
│   └── sdd_spec_write
│
└── Day 5: Testing & docs
    ├── Unit tests for Phase 1
    └── API documentation
```

**Deliverables:**
- [ ] Working MCP server with init, read, write tools
- [ ] Spec file templates
- [ ] Feature creation workflow
- [ ] Unit tests (80%+ coverage)
- [ ] Basic documentation

### 13.2 Phase 2: Role System (Weeks 4-6)

**Goal:** Role-based workflow engine

```
Week 4: Plugin System
├── Day 1-2: Plugin architecture
│   ├── plugins/base.py
│   ├── plugins/loader.py
│   └── Plugin discovery
│
├── Day 3-4: Built-in role plugins
│   ├── plugins/roles/architect.py
│   ├── plugins/roles/ui_designer.py
│   └── plugins/roles/security_analyst.py
│
└── Day 5: Plugin testing
    └── tests/unit/test_plugins.py

Week 5: Role Engine
├── Day 1-2: Role orchestration
│   ├── core/role_engine.py
│   ├── Dependency graph
│   └── Sequential execution
│
├── Day 3-4: Parallel execution
│   ├── asyncio integration
│   ├── Result aggregation
│   └── Error handling
│
└── Day 5: Review workflow
    ├── sdd_review_run tool
    └── sdd_review_status tool

Week 6: Recipe Generation
├── Day 1-2: Recipe templates
│   ├── templates/recipes/*.j2
│   └── Context-based generation
│
├── Day 3-4: Recipe management
│   ├── core/recipe_gen.py
│   ├── Recipe validation
│   └── User approval workflow
│
└── Day 5: Integration testing
    └── tests/integration/test_roles.py
```

**Deliverables:**
- [ ] Plugin system with discovery
- [ ] 5 built-in role plugins
- [ ] Role dependency graph
- [ ] Parallel execution engine
- [ ] Dynamic recipe generation
- [ ] Review workflow tools

### 13.3 Phase 3: Goose Integration (Weeks 7-8)

**Goal:** Seamless Goose CLI integration

```
Week 7: Goose Bridge
├── Day 1-2: AIClientBridge implementation
│   ├── core/ai_client.py (abstract) + core/goose_client.py (Goose impl)
│   ├── Command construction
│   └── Output parsing
│
├── Day 3-4: Task execution
│   ├── Task-to-Goose bridge
│   ├── Progress monitoring
│   └── Session management
│
└── Day 5: Error handling
    ├── Timeout handling
    ├── Retry logic
    └── Graceful degradation

Week 8: Context Management
├── Day 1-2: .goosehints management
│   ├── Automatic generation
│   ├── Update triggers
│   └── Validation
│
├── Day 3-4: Task tools
│   ├── sdd_task_create
│   ├── sdd_task_update
│   └── sdd_task_list
│
└── Day 5: Integration testing
    └── tests/integration/test_goose.py
```

**Deliverables:**
- [ ] AIClientBridge abstraction + GooseClientBridge implementation
- [ ] Task execution workflow
- [ ] Context hints management (`.goosehints` for Goose, client-agnostic internally)
- [ ] Task management tools
- [ ] MCP Prompts for all 6 roles
- [ ] Integration tests with mock AIClientBridge

### 13.4 Phase 4: Enforcement & Alignment (Weeks 9-11)

**Goal:** Strict enforcement and spec-code alignment

```
Week 9: Codebase Summarizer & LLM Alignment
├── Day 1-2: CodebaseSummarizer
│   ├── core/codebase_summary.py
│   ├── File tree generation (language-agnostic)
│   └── Focused git diff with token budget enforcement
│
├── Day 3-4: LLM-based AlignmentChecker
│   ├── core/alignment.py
│   └── AlignmentChecker.check_alignment() via AIClientBridge
│
└── Day 5: Alignment testing
    └── tests/unit/core/test_alignment.py (mock AIClientBridge)

Week 10: Alignment Checker
├── Day 1-2: Spec parsing
│   ├── Markdown parser
│   └── Section extraction
│
├── Day 3-4: Alignment algorithm
│   ├── core/alignment.py
│   ├── Diff generation
│   └── Suggestion engine
│
└── Day 5: Alignment tools
    ├── sdd_align_check tool
    └── Integration tests

Week 11: Enforcement
├── Day 1-2: Enforcement middleware
│   ├── core/enforcement.py
│   └── Blockade logic
│
├── Day 3-4: Pre-commit hooks
│   ├── Git hook integration
│   ├── sdd_commit_check tool
│   └── Guidance generation
│
└── Day 5: Status dashboard
    ├── sdd_status tool
    └── Progress visualization
```

**Deliverables:**
- [ ] Code analyzers (Python, TypeScript, Rust)
- [ ] Spec-code alignment checker
- [ ] Enforcement middleware
- [ ] Pre-commit hooks
- [ ] Status dashboard

### 13.5 Phase 5: Polish & Release (Week 12)

**Goal:** Testing, documentation, release

```
Week 12: Final Polish
├── Day 1-2: Comprehensive testing
│   ├── Unit test completion
│   ├── Integration test completion
│   └── E2E test completion
│
├── Day 3-4: Documentation
│   ├── README.md
│   ├── docs/getting-started.md
│   ├── docs/mcp-tools.md
│   └── docs/configuration.md
│
├── Day 5: Performance optimization
│   ├── Caching strategies
│   └── Benchmarking
│
└── Day 5: Release
    ├── Version tagging
    ├── PyPI publishing
    └── Release notes
```

**Deliverables:**
- [ ] 80%+ test coverage
- [ ] Complete documentation
- [ ] Performance benchmarks
- [ ] v0.1.0 release

---

## 14. Appendices

### Appendix A: Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SDD_SPECS_DIR` | `specs` | Override specs directory |
| `SDD_RECIPES_DIR` | `recipes` | Override recipes directory |
| `SDD_LOG_LEVEL` | `INFO` | Logging level |
| `SDD_LOG_FORMAT` | `json` | Log format (`json` or `text`) |
| `SDD_PLUGINS_PATH` | None | Additional plugin directory |
| `SDD_GOOSE_PATH` | `goose` | Path to Goose binary |
| `SDD_GOOSE_TIMEOUT` | `300` | Goose command timeout (seconds) |

### Appendix B: Configuration File

```yaml
# .sdd/config.yaml (Optional)

project:
  name: my-project
  tech_stack:
    - python
    - fastapi

roles:
  sequence:
    - architect
    - ui-designer
    - interface-designer
    - security-analyst
    - senior-developer
  
  parallel:
    - ui-designer
    - interface-designer

enforcement:
  strict: true  # Always true for MVP
  checks:
    - lint
    - security
    - alignment
    - documentation

linters:
  python:
    - ruff check
    - ruff format
  typescript:
    - eslint
    - prettier

templates:
  custom_dir: .sdd/templates
```

### Appendix C: MCP Server Configuration

#### Option 1: Using uv run (Recommended for Development)

```json
// goose-config.json (Goose configuration)

{
  "mcpServers": {
    "sdd": {
      "command": "uv",
      "args": ["run", "sdd-server"],
      "cwd": "/path/to/sdd-server",
      "env": {
        "SDD_LOG_LEVEL": "DEBUG"
      }
    }
  }
}
```

#### Option 2: Using uv tool (For Installed Package)

```json
// goose-config.json (Goose configuration)

{
  "mcpServers": {
    "sdd": {
      "command": "uv",
      "args": ["tool", "run", "sdd-server"],
      "env": {
        "SDD_LOG_LEVEL": "DEBUG"
      }
    }
  }
}
```

#### Option 3: Direct Python Execution

```json
// goose-config.json (Goose configuration)

{
  "mcpServers": {
    "sdd": {
      "command": "uv",
      "args": ["run", "python", "-m", "sdd_server"],
      "cwd": "/path/to/sdd-server",
      "env": {
        "SDD_LOG_LEVEL": "DEBUG"
      }
    }
  }
}
```

### Appendix D: File Size Limits

| File Type | Max Size | Warning Threshold |
|-----------|----------|-------------------|
| prd.md | 10 MB | 1 MB |
| arch.md | 10 MB | 1 MB |
| tasks.md | 10 MB | 500 KB |
| .metadata.json | 1 MB | 100 KB |
| Recipe files | 100 KB | 50 KB |

### Appendix E: Glossary

| Term | Definition |
|------|------------|
| **SDD** | Specs-Driven Development |
| **MCP** | Model Context Protocol |
| **PRD** | Product Requirements Document |
| **AST** | Abstract Syntax Tree |
| **Role** | A specialized review persona (e.g., Architect, Security Analyst) |
| **Recipe** | A Goose workflow definition in YAML |
| **Alignment** | The state of code matching its specification |
| **Enforcement** | Blocking actions that violate spec-driven principles |

---

## 11. Security Analysis

> **Review Date:** 2026-03-02  
> **Reviewer:** Security Analyst Role  
> **Status:** ✅ Complete

### 11.1 Threat Model

#### Assets Worth Protecting

| Asset | Sensitivity | Rationale |
|-------|-------------|-----------|
| `.metadata.json` | Medium | Contains bypass audit log, workflow state, feature states |
| `specs/` directory | Low-Medium | Contains project specifications (not secrets) |
| `recipes/` directory | Low | Contains workflow definitions |
| Source code (`src/`) | Low | Read-only access for alignment checks |
| Git repository integrity | High | All state relies on git history |

#### Threat Actors

| Actor | Capability | Motivation |
|-------|------------|------------|
| Local malicious user | Read/write access to project directory | Tamper with specs, bypass enforcement |
| Compromised MCP client | Can invoke any MCP tool | Manipulate specs, inject malicious content |
| Supply chain attacker | Can modify dependencies | Inject malicious code via PyPI |

#### Trust Boundaries

```
┌─────────────────────────────────────────────────────────────────┐
│                     UNTRUSTED ZONE                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ MCP Client  │  │   CLI User  │  │  Git Hooks  │             │
│  │  (Goose)    │  │  (Typer)    │  │ (pre-commit)│             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
└─────────┼────────────────┼────────────────┼─────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TRUSTED ZONE (SDD Server)                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Input Validation                      │   │
│  │  - Path traversal protection                             │   │
│  │  - Feature name sanitization                             │   │
│  │  - Content size limits                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              FileSystemClient (Constrained)              │   │
│  │  - Write: specs/, recipes/ only                          │   │
│  │  - Read: specs/, recipes/, src/ (configurable)           │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 11.2 Input Validation

#### Entry Points Requiring Validation

| Entry Point | Input Type | Validation Required | Risk Level |
|-------------|------------|---------------------|------------|
| `sdd_spec_write` | `spec_type`, `feature`, `content` | Enum validation, name sanitization, size limit | High |
| `sdd_feature_create` | `name`, `description` | Name format, path traversal check | High |
| `sdd_init` | Project description | Text sanitization, size limit | Medium |
| `sdd_task_create` | Task title, description | Text sanitization | Medium |
| MCP Resources | URI path | Path traversal protection | High |
| CLI arguments | Command-line args | Typer validation | Medium |

#### Validation Rules

```python
# Feature name validation (already in spec_manager.py)
FEATURE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")

def validate_feature_name(name: str) -> None:
    if not FEATURE_NAME_PATTERN.match(name):
        raise ValidationError(
            f"Feature name must be lowercase alphanumeric with hyphens, "
            f"starting with a letter. Got: '{name}'"
        )
    if len(name) > 64:
        raise ValidationError(f"Feature name too long (max 64 chars): '{name}'")

# Spec type validation (enum)
class SpecType(StrEnum):
    PRD = "prd"
    ARCH = "arch"
    TASKS = "tasks"
    CONTEXT_HINTS = "context-hints"

# Content size limits
MAX_SPEC_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_FEATURE_NAME = 64
MAX_DESCRIPTION = 1000
```

#### Path Traversal Protection

**Status:** ✅ Implemented in `FileSystemClient._validate_path()`

```python
def _validate_path(self, path: Path) -> Path:
    resolved = (
        (self.allowed_root / path).resolve() if not path.is_absolute() 
        else path.resolve()
    )
    try:
        resolved.relative_to(self.allowed_root)
    except ValueError as exc:
        raise PathTraversalError(...) from exc
    return resolved
```

**Test Coverage:** Path traversal tests exist in `tests/unit/infrastructure/test_filesystem.py`

### 11.3 File System Security

#### Access Control Matrix

| Operation | `specs/` | `recipes/` | `src/` | `.git/` |
|-----------|----------|------------|--------|---------|
| **MCP Read** | ✅ | ✅ | ✅ (configurable) | ❌ |
| **MCP Write** | ✅ | ✅ | ❌ | ❌ |
| **CLI Read** | ✅ | ✅ | ✅ | ✅ |
| **CLI Write** | ✅ | ✅ | ✅ | Via git only |

#### Atomic Write Pattern

**Status:** ✅ Implemented in `FileSystemClient.write_file()`

```python
def write_file(self, path: Path, content: str) -> None:
    safe_path = self._validate_path(path)
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=safe_path.parent, prefix=".sdd_tmp_")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, safe_path)  # Atomic on POSIX
    except OSError as exc:
        os.unlink(tmp_path)  # Cleanup on failure
        raise FileSystemError(...) from exc
```

**Security Properties:**
- No partial writes on crash (atomic `os.replace`)
- Temp files created in same directory (same filesystem guarantee)
- Temp file cleanup on failure

#### File Permission Considerations

| File | Recommended Mode | Rationale |
|------|------------------|-----------|
| `.metadata.json` | `0600` | Contains bypass audit log |
| `specs/*.md` | `0644` | Standard documentation |
| `recipes/*.yaml` | `0644` | Standard configuration |
| Pre-commit hook | `0755` | Executable script |

**Finding (Low):** Current implementation does not set explicit file permissions. Consider adding `os.chmod()` after atomic write for sensitive files.

### 11.4 Authentication & Authorization

#### Current State

**Authentication:** None (local tool, relies on OS user permissions)

**Authorization:** Path-based (FileSystemClient constrains writes to allowed directories)

#### Recommendations

| Finding | Severity | Recommendation |
|---------|----------|----------------|
| No authentication | Low | Acceptable for local development tool |
| No audit log for reads | Low | Consider logging read access for sensitive specs |
| Bypass audit exists | ✅ Good | `.metadata.json` logs all bypasses with reason |

### 11.5 Supply Chain Security

#### Dependencies

| Dependency | Risk | Mitigation |
|------------|------|------------|
| `mcp` | Medium | Pin version, verify checksums |
| `pydantic` | Low | Mature, well-maintained |
| `pyyaml` | Medium | Pin version (historical vulns) |
| `jinja2` | Low | No auto-rendering of user content |
| `watchdog` | Low | File monitoring only |
| `structlog` | Low | Logging only |

#### Recommendations

| Finding | Severity | Recommendation |
|---------|----------|----------------|
| No dependency pinning | Medium | Add `uv.lock` to version control ✅ (done) |
| No vulnerability scanning | Medium | Add `pip-audit` to pre-commit hooks |
| No SBOM generation | Low | Consider `cyclonedx-bom` for releases |

**Action Item:** Add to `.pre-commit-config.yaml`:
```yaml
- repo: https://github.com/pypa/pip-audit
  rev: v2.7.0
  hooks:
    - id: pip-audit
      args: ["--ignore-vuln", "PYSEC-2023-228"]  # If needed
```

### 11.6 Logging & Auditability

#### Current Logging

**Implemented:** `structlog` with JSON output

**Logged Events:**
- Tool invocations (via MCP)
- File operations (via FileSystemClient)
- State transitions (via StateManager)
- Bypass events (via EnforcementMiddleware)

#### Sensitive Data Handling

| Data Type | Should Log | Current Behavior |
|-----------|------------|------------------|
| Spec content | ❌ | Not logged (good) |
| Feature names | ✅ | Logged |
| File paths | ✅ | Logged |
| Bypass reasons | ✅ | Logged to `.metadata.json` |
| Error messages | ✅ | Logged |

**Finding (Low):** Ensure log files are not committed to git. Add `*.log` to `.gitignore`.

### 11.7 OWASP Top 10 Checklist (2021)

| # | Category | Applicable | Status | Notes |
|---|----------|------------|--------|-------|
| A01 | Broken Access Control | ✅ | ✅ Mitigated | Path traversal protection in FileSystemClient |
| A02 | Cryptographic Failures | Partial | ⚠️ Low Risk | No crypto used; bypass log could use integrity protection |
| A03 | Injection | ✅ | ✅ Mitigated | Input validation, no SQL, no shell execution with user input |
| A04 | Insecure Design | Partial | ✅ Good | Threat model documented, defense in depth |
| A05 | Security Misconfiguration | Partial | ⚠️ Medium | Add pip-audit, explicit file permissions |
| A06 | Vulnerable Components | ✅ | ⚠️ Medium | Add dependency scanning (pip-audit) |
| A07 | Auth Failures | N/A | - | No authentication (local tool) |
| A08 | Software & Data Integrity | Partial | ✅ Good | Atomic writes, git-based state |
| A09 | Logging & Monitoring | ✅ | ✅ Good | structlog with JSON, bypass audit |
| A10 | SSRF | N/A | - | No network requests |

### 11.8 Security Findings Summary

| ID | Finding | Severity | Status | Action Required |
|----|---------|----------|--------|-----------------|
| SEC-001 | Path traversal protection | N/A | ✅ Implemented | None |
| SEC-002 | Atomic file writes | N/A | ✅ Implemented | None |
| SEC-003 | Input validation (feature names) | N/A | ✅ Implemented | None |
| SEC-004 | Bypass audit log | N/A | ✅ Implemented | None |
| SEC-005 | No dependency vulnerability scanning | Medium | ⚠️ Pending | Add pip-audit to pre-commit |
| SEC-006 | No explicit file permissions | Low | ⚠️ Pending | Consider chmod for .metadata.json |
| SEC-007 | Log files in git | Low | ⚠️ Pending | Verify *.log in .gitignore |

### 11.9 Recommended Security Tasks

Add to `specs/tasks.md`:

| ID | Title | Priority | Phase |
|----|-------|----------|-------|
| SEC-TASK-001 | Add pip-audit to pre-commit hooks | Medium | Phase 2 |
| SEC-TASK-002 | Set explicit permissions on .metadata.json (0600) | Low | Phase 2 |
| SEC-TASK-003 | Verify *.log in .gitignore | Low | Phase 1 |
| SEC-TASK-004 | Add security tests for edge cases (empty names, unicode, etc.) | Medium | Phase 2 |

---

## 12. Edge Case Analysis

> **Review Date:** 2026-03-02  
> **Reviewer:** Edge Case Analyst Role  
> **Status:** ✅ Complete

### 12.1 User Interaction Edge Cases

#### Edge Case: Empty Feature Name
**Domain:** User Interaction  
**Trigger:** User calls `sdd_feature_create` with empty string or whitespace-only name  
**Expected Behaviour:** Clear validation error, no directory created  
**Test Scenario:** `sdd_feature_create(name="")` → ValidationError  
**Priority:** High  
**Status:** ✅ Mitigated — `_FEATURE_NAME_RE` rejects empty strings

#### Edge Case: Feature Name with Special Characters
**Domain:** User Interaction  
**Trigger:** User provides feature name with uppercase, underscores, or special chars like `My_Feature!`  
**Expected Behaviour:** Validation error with clear message explaining allowed format  
**Test Scenario:** `sdd_feature_create(name="My_Feature!")` → ValidationError  
**Priority:** High  
**Status:** ✅ Mitigated — Regex `^[a-z][a-z0-9-]*$` enforced

#### Edge Case: Duplicate Feature Creation
**Domain:** User Interaction  
**Trigger:** User calls `sdd_feature_create` for a feature that already exists  
**Expected Behaviour:** ValidationError, no overwrite  
**Test Scenario:** Create feature "auth" twice → second fails  
**Priority:** High  
**Status:** ✅ Mitigated — `directory_exists` check in `create_feature()`

#### Edge Case: Invalid Spec Type
**Domain:** User Interaction  
**Trigger:** User calls `sdd_spec_read` with unknown spec type like `"unknown"`  
**Expected Behaviour:** Clear error listing valid spec types  
**Test Scenario:** `sdd_spec_read(spec_type="unknown")` → Error with valid options  
**Priority:** Medium  
**Status:** ✅ Mitigated — `SpecType` enum validation

#### Edge Case: Invalid Write Mode
**Domain:** User Interaction  
**Trigger:** User calls `sdd_spec_write` with mode `"insert"` instead of valid modes  
**Expected Behaviour:** ValidationError listing valid modes  
**Test Scenario:** `sdd_spec_write(..., mode="insert")` → ValidationError  
**Priority:** Medium  
**Status:** ✅ Mitigated — Mode validation in `write_spec()`

#### Edge Case: Reading Non-Existent Feature Spec
**Domain:** User Interaction  
**Trigger:** User reads spec from feature that doesn't exist  
**Expected Behaviour:** SpecNotFoundError with helpful message  
**Test Scenario:** `sdd_spec_read(spec_type="prd", feature="nonexistent")`  
**Priority:** Medium  
**Status:** ✅ Mitigated — File existence check in `read_spec()`

#### Edge Case: Extremely Long Feature Name
**Domain:** User Interaction  
**Trigger:** User provides feature name with 1000+ characters  
**Expected Behaviour:** Validation error (max 64 chars)  
**Test Scenario:** `sdd_feature_create(name="a" * 1000)`  
**Priority:** Low  
**Status:** ⚠️ Partial — No explicit length limit in current implementation

#### Edge Case: Unicode in Feature Name
**Domain:** User Interaction  
**Trigger:** User provides feature name with unicode characters like `"功能"`  
**Expected Behaviour:** ValidationError (only ASCII alphanumeric + hyphens)  
**Test Scenario:** `sdd_feature_create(name="功能")`  
**Priority:** Low  
**Status:** ✅ Mitigated — Regex only matches ASCII

---

### 12.2 Data Flow Edge Cases

#### Edge Case: Empty Spec Content
**Domain:** Data Flow  
**Trigger:** User writes empty string to a spec file  
**Expected Behaviour:** File is created/overwritten with empty content (valid)  
**Test Scenario:** `sdd_spec_write(spec_type="prd", content="")`  
**Priority:** Low  
**Status:** ✅ Handled — Empty content is valid

#### Edge Case: Very Large Spec File
**Domain:** Data Flow  
**Trigger:** User writes spec content > 10MB  
**Expected Behaviour:** Either accepted with warning or rejected with clear error  
**Test Scenario:** Write 15MB markdown file to prd.md  
**Priority:** Medium  
**Status:** ⚠️ Partial — No size limit enforced in current implementation

#### Edge Case: Corrupted Metadata JSON
**Domain:** Data Flow  
**Trigger:** `.metadata.json` contains invalid JSON (manual edit, disk corruption)  
**Expected Behaviour:** FileSystemError with clear message, ability to reset  
**Test Scenario:** Write `{invalid json` to .metadata.json, then call `sdd_status`  
**Priority:** High  
**Status:** ✅ Mitigated — JSON parse error caught in `MetadataManager.load()`

#### Edge Case: Metadata Schema Mismatch
**Domain:** Data Flow  
**Trigger:** `.metadata.json` has old schema after upgrade  
**Expected Behaviour:** Graceful migration or clear error message  
**Test Scenario:** Old metadata format without new fields → load fails?  
**Priority:** Medium  
**Status:** ⚠️ Partial — Pydantic `model_validate` may fail on schema mismatch

#### Edge Case: Partial Write Recovery
**Domain:** Data Flow  
**Trigger:** Process killed during atomic write (after temp file created, before replace)  
**Expected Behaviour:** Orphaned temp file cleaned up on next operation; spec file intact  
**Test Scenario:** Kill process during `write_spec`, verify recovery  
**Priority:** High  
**Status:** ✅ Mitigated — Atomic write pattern with `os.replace()`

#### Edge Case: Concurrent Reads and Writes
**Domain:** Data Flow  
**Trigger:** Two MCP clients read/write same spec simultaneously  
**Expected Behaviour:** No corruption; last write wins  
**Test Scenario:** Parallel `sdd_spec_write` calls to same file  
**Priority:** Medium  
**Status:** ✅ Mitigated — Atomic writes prevent corruption

#### Edge Case: Binary Content in Spec File
**Domain:** Data Flow  
**Trigger:** User writes binary data (images, etc.) to spec file  
**Expected Behaviour:** Error (UTF-8 encoding required)  
**Test Scenario:** Write bytes to spec file  
**Priority:** Low  
**Status:** ✅ Mitigated — `write_text(encoding="utf-8")` will fail on binary

---

### 12.3 Process Flow Edge Cases

#### Edge Case: Operations Before Init
**Domain:** Process Flow  
**Trigger:** User calls `sdd_spec_read` before `sdd_init` creates specs directory  
**Expected Behaviour:** Clear error explaining project not initialized  
**Test Scenario:** In empty directory, call `sdd_status`  
**Priority:** High  
**Status:** ✅ Mitigated — StartupValidator checks specs_dir

#### Edge Case: Git Not Installed
**Domain:** Process Flow  
**Trigger:** System doesn't have git in PATH  
**Expected Behaviour:** Clear error from StartupValidator  
**Test Scenario:** Run with git not in PATH  
**Priority:** Medium  
**Status:** ✅ Mitigated — GitClient checks via `is_repo()`

#### Edge Case: Pre-commit Hook Not Installed
**Domain:** Process Flow  
**Trigger:** User runs `sdd_status` without pre-commit hook  
**Expected Behaviour:** Warning (non-fatal) suggesting to run `sdd init`  
**Test Scenario:** Remove .git/hooks/pre-commit, run `sdd_status`  
**Priority:** Medium  
**Status:** ✅ Mitigated — StartupValidator warns (non-fatal)

#### Edge Case: No Write Permission on Specs Directory
**Domain:** Process Flow  
**Trigger:** specs/ directory exists but is read-only  
**Expected Behaviour:** Clear error on write attempt  
**Test Scenario:** `chmod -w specs/`, then `sdd_spec_write`  
**Priority:** Medium  
**Status:** ⚠️ Partial — Check in StartupValidator, but OS error on write

#### Edge Case: Disk Full During Write
**Domain:** Process Flow  
**Trigger:** No disk space when writing temp file  
**Expected Behaviour:** FileSystemError, temp file cleaned up, original intact  
**Test Scenario:** Fill disk, attempt write  
**Priority:** Low  
**Status:** ✅ Mitigated — OSError caught, temp file cleanup attempted

#### Edge Case: Process Killed During Feature Creation
**Domain:** Process Flow  
**Trigger:** SIGKILL after some but not all feature spec files created  
**Expected Behaviour:** Partial feature directory; cleanup on next attempt or manual intervention  
**Test Scenario:** Kill during `create_feature()` after prd.md but before arch.md  
**Priority:** Medium  
**Status:** ⚠️ Partial — No transaction rollback for multi-file operations

#### Edge Case: Idempotency of sdd_init
**Domain:** Process Flow  
**Trigger:** User runs `sdd_init` twice on same project  
**Expected Behaviour:** Second run is safe (idempotent) — doesn't overwrite existing specs  
**Test Scenario:** Run `sdd_init` twice  
**Priority:** High  
**Status:** ⚠️ Needs Verification — Check initializer implementation

#### Edge Case: MCP Server Restart Mid-Operation
**Domain:** Process Flow  
**Trigger:** MCP server restarts while client is mid-workflow  
**Expected Behaviour:** State persisted in files; resume from last state  
**Test Scenario:** Start operation, restart server, continue  
**Priority:** Medium  
**Status:** ✅ Mitigated — Stateless design, state in .metadata.json

---

### 12.4 Edge Cases Requiring Test Coverage

| ID | Edge Case | Priority | Test File | Status |
|----|-----------|----------|-----------|--------|
| EC-001 | Empty feature name | High | `test_spec_manager.py` | ✅ Exists |
| EC-002 | Duplicate feature | High | `test_spec_manager.py` | ✅ Exists |
| EC-003 | Invalid spec type | Medium | `test_mcp_tools.py` | ✅ Exists |
| EC-004 | Corrupted metadata | High | `test_metadata.py` | ✅ Exists |
| EC-005 | Partial write recovery | High | `test_filesystem.py` | ⚠️ Add test |
| EC-006 | Concurrent writes | Medium | `test_filesystem.py` | ⚠️ Add test |
| EC-007 | Operations before init | High | `test_startup.py` | ✅ Exists |
| EC-008 | Idempotent init | High | `test_initializer.py` | ⚠️ Add test |
| EC-009 | Long feature name | Low | `test_spec_manager.py` | ⚠️ Add test |
| EC-010 | Large spec file | Medium | `test_spec_manager.py` | ⚠️ Add test |
| EC-011 | Schema migration | Medium | `test_metadata.py` | ⚠️ Add test |
| EC-012 | Kill during feature creation | Medium | Integration test | ⚠️ Add test |

### 12.5 Recommended Edge Case Tasks

Add to `specs/tasks.md`:

| ID | Title | Priority | Phase |
|----|-------|----------|-------|
| EC-TASK-001 | Add feature name length validation (max 64 chars) | Low | Phase 2 |
| EC-TASK-002 | Add spec file size limit (10MB warning, reject >50MB) | Medium | Phase 2 |
| EC-TASK-003 | Add test for partial write recovery | High | Phase 2 |
| EC-TASK-004 | Add test for concurrent write safety | Medium | Phase 2 |
| EC-TASK-005 | Add test for idempotent `sdd_init` | High | Phase 2 |
| EC-TASK-006 | Add metadata schema migration handling | Medium | Phase 2 |
| EC-TASK-007 | Add transaction-like rollback for multi-file operations | Low | Phase 3 |

---

## Document Status

**Version:** 1.0  
**Status:** ✅ Complete - Ready for Implementation  
**Last Updated:** 2026-03-02

**Review Status:**
- [x] Architecture overview complete
- [x] Tech stack defined
- [x] Component designs complete
- [x] MCP tools specified
- [x] User flows documented
- [x] Goose integration designed
- [x] Plugin architecture defined
- [x] Data models specified
- [x] Testing strategy defined
- [x] Implementation roadmap complete
- [x] Security analysis complete (2026-03-02)

**Next Steps:**
1. Set up development environment
2. Begin Phase 1 implementation
3. Create initial test suite
4. Document API as we build
5. Address medium-priority security findings (pip-audit)
