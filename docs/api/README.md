# SDD Server API Documentation

This directory contains comprehensive API documentation for the SDD MCP Server.

## Contents

- **[tools.md](./tools.md)** - Complete reference for all MCP tools
- **[resources.md](./resources.md)** - MCP resources exposed by the server
- **[prompts.md](./prompts.md)** - Role-specific prompts for AI assistants

## Quick Links

### Tool Categories

| Category | Description | Count |
|----------|-------------|-------|
| [Initialization](./tools.md#project-initialization) | Project setup and preflight checks | 2 |
| [Spec Management](./tools.md#spec-management) | Read, write, list spec files | 3 |
| [Feature Management](./tools.md#feature-management) | Create and list features | 2 |
| [Task Management](./tools.md#task-management) | Full task CRUD operations | 11 |
| [Review Tools](./tools.md#review-tools) | Role-based code reviews | 6 |
| [Lifecycle Management](./tools.md#lifecycle-management) | Feature lifecycle states | 9 |
| [Code Generation](./tools.md#code-generation) | Template-based scaffolding | 5 |
| [Validation](./tools.md#validation) | Spec validation rules | 5 |
| [Status](./tools.md#status) | Project status reporting | 1 |

### Total: 44 MCP Tools

## Getting Started

1. Start the MCP server:
   ```bash
   sdd-server
   ```

2. Connect via an MCP client (e.g., Goose, Claude Desktop)

3. Call tools using the MCP protocol

## Example Usage

```python
# Initialize a new project
result = await sdd_init(
    project_name="my-app",
    description="My awesome application"
)

# Create a feature
await sdd_feature_create(name="user-auth", description="User authentication")

# Add a task
task = await sdd_task_add(
    title="Implement login",
    feature="user-auth",
    priority="high"
)

# Run reviews
results = await sdd_review_run(roles=["architect", "developer"])
```
