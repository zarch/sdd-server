# SDD Server Architecture

This document provides a technical overview of the SDD MCP Server architecture.

## Overview

The SDD (Specs-Driven Development) MCP Server implements a Model Context Protocol server that enforces spec-first development workflows through role-based reviews and AI integration.

```
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Clients                               │
│   (Goose, Claude Desktop, Custom Clients)                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │ MCP Protocol
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SDD MCP Server                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Tools     │  │  Resources  │  │   Prompts   │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                │                │                     │
│         └────────────────┼────────────────┘                     │
│                          ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Core Services                          │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐            │  │
│  │  │SpecManager │ │RoleEngine  │ │TaskManager │            │  │
│  │  └────────────┘ └────────────┘ └────────────┘            │  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐            │  │
│  │  │ CodeGen    │ │ Validator  │ │ Lifecycle  │            │  │
│  │  └────────────┘ └────────────┘ └────────────┘            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Plugin System                          │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │  │
│  │  │Architect│ │Developer│ │ Reviewer│ │   QA    │ ...    │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  Infrastructure Layer                     │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │  │
│  │  │FileSystem│ │   Git   │ │ Config  │ │Logging  │        │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘        │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │  │
│  │  │  Retry  │ │Metrics  │ │  Audit  │ │Security │        │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘        │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      File System                                │
│   specs/  features/  recipes/  .sdd/                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. MCP Layer (`src/sdd_server/mcp/`)

The MCP layer implements the Model Context Protocol interface.

#### Tools (`mcp/tools/`)

44 MCP tools organized by domain:

| Module | Tools | Purpose |
|--------|-------|---------|
| `init.py` | 2 | Project initialization |
| `spec.py` | 3 | Spec file operations |
| `feature.py` | 2 | Feature management |
| `task.py` | 11 | Task CRUD operations |
| `review.py` | 6 | Role-based reviews |
| `lifecycle.py` | 9 | Feature lifecycle |
| `codegen.py` | 5 | Code generation |
| `validation.py` | 5 | Spec validation |
| `status.py` | 1 | Project status |

#### Resources (`mcp/resources/`)

Exposes spec files as MCP resources:

- `specs://prd` - Root PRD
- `specs://arch` - Root Architecture
- `specs://tasks` - Root Tasks
- `specs://features/{feature}/{type}` - Feature specs

#### Prompts (`mcp/prompts/`)

Role-specific prompts for AI guidance:

- Review prompts for each role
- Context-aware prompt generation

### 2. Core Services (`src/sdd_server/core/`)

Business logic layer implementing SDD workflows.

#### SpecManager

Manages spec file operations:

- Read/write spec files
- Validate structure
- Feature creation
- Template rendering

#### RoleEngine

Executes role-based reviews:

- Dependency resolution
- Parallel execution
- Result aggregation
- Progress tracking

#### TaskBreakdownManager

Task management system:

- Task CRUD operations
- Dependency tracking
- Progress statistics
- Spec synchronization

#### CodeGenerator

Template-based code generation:

- Jinja2 templates
- Scaffold generation
- Preview mode
- Custom templates

#### SpecValidator

Spec validation engine:

- Rule-based validation
- Custom rules
- Severity levels
- Issue reporting

#### FeatureLifecycleManager

Feature state management:

- State transitions
- History tracking
- Metrics collection
- Archival

### 3. Plugin System (`src/sdd_server/plugins/`)

Extensible plugin architecture for roles.

#### Base Classes

```python
class BasePlugin:
    metadata: PluginMetadata
    
    def initialize(self, context: dict) -> None: ...
    def shutdown(self) -> None: ...

class RolePlugin(BasePlugin):
    @abstractmethod
    async def review(self, context: ReviewContext) -> ReviewResult: ...
```

#### Built-in Roles

| Role | Stage | Dependencies | Purpose |
|------|-------|--------------|---------|
| Architect | planning | - | System design |
| Developer | development | architect | Implementation |
| Reviewer | review | developer | Code quality |
| QA | testing | developer | Test coverage |
| Security | review | developer | Security audit |
| DevOps | deployment | qa | Infrastructure |

#### Plugin Registry

```python
class PluginRegistry:
    def register(self, name: str, plugin: BasePlugin) -> None
    def get_role(self, name: str) -> RolePlugin | None
    def list_roles(self) -> list[str]
```

### 4. Infrastructure Layer (`src/sdd_server/infrastructure/`)

Cross-cutting concerns and utilities.

#### FileSystem (`filesystem.py`)

File operations with safety:

- Path validation
- Atomic writes
- Error handling

#### Git (`git.py`)

Git operations:

- Repository validation
- Hook installation
- Branch operations

#### Configuration (`config.py`)

Hierarchical configuration:

- Environment variables
- Config files (YAML/JSON)
- Default values
- Runtime reloading

#### Observability (`observability/`)

Monitoring and logging:

- Metrics collection
- Health checks
- Audit logging
- Structured logging

#### Security (`security.py`)

Security utilities:

- Input sanitization
- Path validation
- Rate limiting

#### Retry (`retry.py`)

Resilient operations:

- Exponential backoff
- Retry strategies
- Circuit breaker

---

## Data Models (`src/sdd_server/models/`)

### Core Models

```python
@dataclass
class WorkflowState:
    state: str
    features: dict[str, FeatureState]
    bypasses: list[BypassEntry]

@dataclass  
class FeatureState:
    name: str
    status: str
    spec_types: list[str]
    
@dataclass
class Task:
    id: str
    title: str
    status: TaskStatus
    priority: TaskPriority
    dependencies: list[str]
```

### Review Models

```python
@dataclass
class ReviewResult:
    role: str
    status: ReviewStatus
    issues: list[Issue]
    suggestions: list[Suggestion]
    
@dataclass
class ReviewContext:
    spec_type: SpecType
    content: str
    feature: str | None
```

---

## Execution Flow

### Review Execution

```
1. sdd_review_run(roles=["architect", "developer"])
          │
          ▼
2. RoleEngine.run_roles()
          │
          ├─► Resolve dependencies (topological sort)
          │
          ├─► Execute roles in parallel (independent) or sequence (dependent)
          │
          │   For each role:
          │   ├─► Load role plugin
          │   ├─► Prepare context
          │   ├─► role.review(context)
          │   └─► Collect results
          │
          ▼
3. Aggregate results
          │
          ▼
4. Return summary
```

### Task Synchronization

```
1. sdd_task_sync(feature="auth")
          │
          ▼
2. Parse tasks.md
          │
          ├─► Extract task blocks
          ├─► Parse metadata (priority, dependencies)
          │
          ▼
3. Compare with stored tasks
          │
          ├─► New tasks → Add
          ├─► Changed tasks → Update
          ├─► Removed tasks → Archive
          │
          ▼
4. Return changes
```

---

## Extension Points

### Custom Roles

Create a custom role plugin:

```python
from sdd_server.plugins import RolePlugin, PluginMetadata

class CustomReviewer(RolePlugin):
    metadata = PluginMetadata(
        name="custom-reviewer",
        version="1.0.0",
        description="Custom review logic",
        stage=Stage.review,
        dependencies=["developer"],
        priority=50
    )
    
    async def review(self, context: ReviewContext) -> ReviewResult:
        # Custom review logic
        return ReviewResult(
            role=self.metadata.name,
            status=ReviewStatus.COMPLETED,
            issues=[...],
            suggestions=[...]
        )
```

### Custom Validation Rules

Add validation rules:

```python
await sdd_add_validation_rule(
    rule_id="custom_prd_section",
    name="Custom PRD Section",
    description="Ensures custom section exists",
    rule_type="required_section",
    spec_types="prd",
    severity="warning",
    section="## Custom Section"
)
```

### Custom Code Templates

Add code templates in `specs/templates/`:

```jinja2
# {{ module_name }}.py
"""{{ description }}"""

class {{ class_name }}:
    """{{ class_description }}"""
    
    def __init__(self):
        pass
```

---

## Configuration Reference

### Server Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `host` | string | "0.0.0.0" | Server host |
| `port` | int | 8080 | Server port |
| `debug` | bool | false | Debug mode |

### Execution Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `max_parallel_roles` | int | 4 | Max concurrent roles |
| `timeout_seconds` | int | 300 | Execution timeout |
| `retry.max_attempts` | int | 3 | Retry attempts |
| `retry.backoff_factor` | float | 2.0 | Backoff multiplier |

### Logging Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `level` | string | "INFO" | Log level |
| `format` | string | "json" | Log format |
| `output` | string | "stdout" | Output destination |

---

## Performance Considerations

### Parallel Execution

- Independent roles run in parallel
- Configurable concurrency limit
- Async I/O for file operations

### Caching

- Spec content cached in memory
- Plugin instances reused
- Configuration cached with reload

### Resource Management

- Connection pooling for Goose sessions
- Lazy loading of plugins
- Background task cleanup
