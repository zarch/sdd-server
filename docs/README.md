# SDD MCP Server Documentation

**Version:** 0.1.0  
**Status:** Production Ready

Specs-Driven Development (SDD) MCP Server - An MCP server that implements the SDD workflow with role-based spec reviews executed via Goose recipes.

## Quick Start

```bash
# Install
pip install sdd-server

# Initialize a project
sdd init my-project --description "My awesome project"

# Start the server
sdd-server
```

## Documentation Sections

### API Reference

- **[API Overview](api/README.md)** - Quick reference for all MCP tools
- **[Tools Reference](api/tools.md)** - Complete MCP tools documentation (46 tools)
- **[Resources Reference](api/resources.md)** - MCP resources for spec files
- **[Prompts Reference](api/prompts.md)** - Role-specific AI prompts

### Usage Guides

- **[Usage Guide](usage/README.md)** - How to use the SDD Server
  - Installation and setup
  - CLI commands
  - Configuration
  - MCP integration
  - Workflow examples

### Development

- **[Architecture](development/architecture.md)** - Technical architecture overview
  - Component overview
  - Data models
  - Execution flow
  - Configuration reference
- **[Plugin Development](development/plugins.md)** - Creating custom plugins
  - Role plugins
  - Review context
  - Registration
  - Testing

## Key Features

### 🎯 Spec-First Development

- Enforce spec creation before implementation
- Validate specs against customizable rules
- Track spec changes and compliance

### 🤖 AI Integration

- MCP protocol support for AI assistants
- Role-based AI prompts
- Goose recipe generation

### 📋 Task Management

- Full task lifecycle management
- Dependency tracking
- Progress monitoring
- Spec synchronization

### 🔄 Role-Based Reviews

- 11 built-in review roles
- Dependency-aware execution
- Parallel review support
- Extensible plugin system

### 🏗️ Code Generation

- Jinja2 template-based
- Scaffold entire modules
- Custom template support

## Project Structure

```
sdd-server/
├── src/sdd_server/
│   ├── core/           # Business logic
│   ├── mcp/            # MCP implementation
│   │   ├── tools/      # 44 MCP tools
│   │   ├── resources/  # Spec resources
│   │   └── prompts/    # Role prompts
│   ├── plugins/        # Plugin system
│   ├── models/         # Data models
│   └── infrastructure/ # Cross-cutting concerns
├── tests/              # Test suite
├── docs/               # Documentation
└── specs/              # SDD specs
```

## Built-in Roles

| Priority | Role | Stage | Purpose |
|----------|------|-------|---------|
| 5 | `spec-linter` | SPEC_AUDIT | Validates spec structure before pipeline starts |
| 10 | `architect` | ARCHITECTURE | System design and component architecture |
| 20 | `interface-designer` | INTERFACE_DESIGN | API contracts, schemas, error catalogue |
| 20 | `ui-designer` | UI_DESIGN | User flows, WCAG 2.1, component inventory |
| 30 | `security-analyst` | SECURITY | OWASP Top 10, threat model, CVE scan |
| 40 | `edge-case-analyst` | EDGE_CASE_ANALYSIS | Edge cases and test scenarios |
| 50 | `senior-developer` | IMPLEMENTATION | Code quality, coverage gaps, tech debt |
| 60 | `qa-engineer` | QA | Acceptance criteria coverage, defect list |
| 60 | `tech-writer` | DOCUMENTATION | Doc inventory, changelog entry |
| 60 | `devops-engineer` | DEVOPS | CI/CD, Dockerfile, secrets, observability |
| 80 | `product-owner` | RELEASE | SHIP / HOLD release verdict |

## Configuration

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
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SDD_PROJECT_ROOT` | Project root directory | Current directory |
| `SDD_LOG_LEVEL` | Logging level | `INFO` |
| `SDD_CONFIG_FILE` | Config file path | `specs/config.yaml` |

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `uv run pytest`
5. Submit a pull request

## License

MIT License - See LICENSE file for details.
