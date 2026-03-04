# MCP Resources Reference

The SDD Server exposes the following MCP resources for reading spec files.

## Available Resources

### specs://prd

The project's Product Requirements Document.

**URI:** `specs://prd`

**Content:** Markdown content of `specs/prd.md`

**Example:**

```python
content = await read_resource("specs://prd")
```

---

### specs://arch

The project's Architecture Document.

**URI:** `specs://arch`

**Content:** Markdown content of `specs/arch.md`

---

### specs://tasks

The project's Tasks Document.

**URI:** `specs://tasks`

**Content:** Markdown content of `specs/tasks.md`

---

### specs://context-hints

Context hints for AI assistants.

**URI:** `specs://context-hints`

**Content:** Markdown content of `specs/context-hints.md`

---

### specs://features/{feature}/{type}

Feature-specific spec files.

**URI Pattern:** `specs://features/{feature}/{type}`

**Parameters:**

- `feature` - Feature name (e.g., `auth`, `payments`)
- `type` - Spec type (`prd`, `arch`, `tasks`, `context-hints`)

**Examples:**

- `specs://features/auth/prd` - Auth feature PRD
- `specs://features/auth/arch` - Auth feature architecture
- `specs://features/auth/tasks` - Auth feature tasks

---

## Resource Templates

The server supports the following resource templates:

| Template | Description |
|----------|-------------|
| `specs://prd` | Root PRD |
| `specs://arch` | Root Architecture |
| `specs://tasks` | Root Tasks |
| `specs://context-hints` | Root Context Hints |
| `specs://features/{feature}/prd` | Feature PRD |
| `specs://features/{feature}/arch` | Feature Architecture |
| `specs://features/{feature}/tasks` | Feature Tasks |
| `specs://features/{feature}/context-hints` | Feature Context Hints |

## Usage with MCP Client

```python
# List available resources
resources = await list_resources()

# Read a specific resource
content = await read_resource("specs://prd")

# Read a feature spec
auth_prd = await read_resource("specs://features/auth/prd")
```
