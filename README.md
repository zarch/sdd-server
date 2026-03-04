# SDD MCP Server

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Specs-Driven Development MCP Server** - An MCP server that implements the SDD workflow with role-based spec reviews executed via Goose recipes.

## What is SDD?

Specs-Driven Development (SDD) is a methodology that enforces writing specifications before implementation. This server provides:

- **MCP Protocol Support** - Full Model Context Protocol implementation for AI assistants
- **Role-Based Reviews** - 6 built-in review roles (Architect, Developer, Reviewer, QA, Security, DevOps)
- **Task Management** - Complete task lifecycle with dependencies and progress tracking
- **Code Generation** - Template-based scaffolding from specs
- **Spec Validation** - Rule-based validation with custom rules support

## Quick Start

### Installation

```bash
# Using pip
pip install sdd-server

# Using uv
uv pip install sdd-server

# From source
git clone https://github.com/block/sdd-server.git
cd sdd-server
uv sync
```

### Initialize a Project

```bash
# Create a new SDD project
sdd init my-project --description "My awesome project"

# Run preflight checks
sdd preflight

# Check project status
sdd status
```

### Start the Server

```bash
# Start with default settings
sdd-server

# With custom project root
SDD_PROJECT_ROOT=/path/to/project sdd-server

# With debug logging
SDD_LOG_LEVEL=DEBUG sdd-server
```

## MCP Integration

### With Goose

```yaml
# ~/.config/goose/config.yaml
extensions:
  sdd:
    command: sdd-server
    env:
      SDD_PROJECT_ROOT: /path/to/project
```

### With Claude Desktop

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

## Available Tools (44 Total)

| Category | Tools | Description |
|----------|-------|-------------|
| Initialization | `sdd_init`, `sdd_preflight` | Project setup and validation |
| Spec Management | `sdd_spec_read`, `sdd_spec_write`, `sdd_spec_list` | Spec file operations |
| Feature Management | `sdd_feature_create`, `sdd_feature_list` | Feature organization |
| Task Management | 11 tools | Full task CRUD with dependencies |
| Review Tools | 6 tools | Role-based code reviews |
| Lifecycle | 9 tools | Feature state management |
| Code Generation | 5 tools | Template-based scaffolding |
| Validation | 5 tools | Spec validation rules |

See the [API Documentation](docs/api/README.md) for complete details.

## Project Structure

```
my-project/
├── specs/
│   ├── prd.md           # Product Requirements
│   ├── arch.md          # Architecture Design
│   ├── tasks.md         # Task Breakdown
│   ├── context-hints.md # AI Context
│   ├── features/        # Feature-specific specs
│   ├── recipes/         # Generated Goose recipes
│   └── config.yaml      # SDD configuration
├── .sdd/
│   └── metadata.json    # Project state
└── .git/
    └── hooks/
        └── pre-commit   # Spec enforcement hook
```

## Built-in Roles

| Role | Stage | Dependencies | Purpose |
|------|-------|--------------|---------|
| Architect | Planning | - | System design |
| Developer | Development | Architect | Implementation |
| Reviewer | Review | Developer | Code quality |
| QA | Testing | Developer | Test coverage |
| Security | Review | Developer | Security audit |
| DevOps | Deployment | QA | Infrastructure |

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SDD_PROJECT_ROOT` | Project root | Current directory |
| `SDD_LOG_LEVEL` | Log level | `INFO` |
| `SDD_CONFIG_FILE` | Config file | `specs/config.yaml` |

### Configuration File

```yaml
# specs/config.yaml
server:
  host: "0.0.0.0"
  port: 8080

execution:
  max_parallel_roles: 4
  timeout_seconds: 300

logging:
  level: "INFO"
  format: "json"

security:
  rate_limit:
    requests_per_second: 10
    burst_size: 20
```

## Example Workflow

```python
# 1. Initialize project
result = await sdd_init(
    project_name="my-app",
    description="My application"
)

# 2. Create a feature
await sdd_feature_create(
    name="user-auth",
    description="User authentication"
)

# 3. Write specs
await sdd_spec_write(
    spec_type="prd",
    feature="user-auth",
    content="# User Auth PRD\n\n..."
)

# 4. Add tasks
await sdd_task_add(
    title="Implement login",
    feature="user-auth",
    priority="high"
)

# 5. Run reviews
results = await sdd_review_run(
    roles=["architect", "developer"],
    parallel=True
)

# 6. Generate code
await sdd_codegen_scaffold(
    name="auth_service",
    templates=["module", "test"]
)
```

## Documentation

- [API Reference](docs/api/README.md) - Complete MCP tools documentation
- [Usage Guide](docs/usage/README.md) - How to use the SDD Server
- [Architecture](docs/development/architecture.md) - Technical overview
- [Plugin Development](docs/development/plugins.md) - Creating custom plugins

## Development

```bash
# Install development dependencies
uv sync

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=sdd_server

# Type checking
uv run mypy src/

# Linting
uv run ruff check src/
uv run ruff format src/
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`uv run pytest`)
5. Commit your changes (`git commit -m 'feat: add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built on [FastMCP](https://github.com/anthropics/mcp) for MCP protocol support
- Inspired by spec-first development methodologies
- Part of the [Goose](https://github.com/block/goose) ecosystem
