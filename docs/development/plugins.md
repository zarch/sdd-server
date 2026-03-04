# Plugin Development Guide

This guide explains how to create custom plugins for the SDD Server.

## Table of Contents

- [Plugin Types](#plugin-types)
- [Creating a Role Plugin](#creating-a-role-plugin)
- [Plugin Metadata](#plugin-metadata)
- [Review Context](#review-context)
- [Review Results](#review-results)
- [Registering Plugins](#registering-plugins)
- [Testing Plugins](#testing-plugins)
- [Best Practices](#best-practices)

---

## Plugin Types

### BasePlugin

The foundation for all plugins. Provides:

- Metadata storage
- Lifecycle methods
- Context management

### RolePlugin

Extends BasePlugin for review roles:

- Review execution
- Issue reporting
- Suggestion generation

---

## Creating a Role Plugin

### Basic Structure

```python
from sdd_server.plugins import RolePlugin, PluginMetadata
from sdd_server.models.review import ReviewContext, ReviewResult, ReviewStatus

class MyCustomReviewer(RolePlugin):
    """A custom review role."""
    
    metadata = PluginMetadata(
        name="my-custom-reviewer",
        version="1.0.0",
        description="Performs custom reviews",
        stage=Stage.review,
        dependencies=["developer"],
        priority=50
    )
    
    async def review(self, context: ReviewContext) -> ReviewResult:
        """Execute the review."""
        issues = []
        suggestions = []
        
        # Your review logic here
        content = context.content
        
        # Example: Check for TODO comments
        if "TODO" in content:
            issues.append(Issue(
                severity=Severity.WARNING,
                message="Unresolved TODO found",
                location="line 10"
            ))
        
        return ReviewResult(
            role=self.metadata.name,
            status=ReviewStatus.COMPLETED,
            issues=issues,
            suggestions=suggestions,
            output="Review completed successfully"
        )
```

### Complete Example

```python
"""Custom security reviewer plugin."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sdd_server.models.review import (
    Issue,
    ReviewContext,
    ReviewResult,
    ReviewStatus,
    Severity,
    Suggestion,
)
from sdd_server.plugins import PluginMetadata, RolePlugin
from sdd_server.models.spec import Stage


class SecurityReviewer(RolePlugin):
    """Reviews code for security vulnerabilities."""
    
    metadata = PluginMetadata(
        name="security-reviewer",
        version="1.0.0",
        description="Security-focused code review",
        stage=Stage.review,
        dependencies=["developer"],
        priority=60  # Run after developer
    )
    
    # Patterns to check
    DANGEROUS_PATTERNS = [
        (r"eval\s*\(", "Use of eval() is dangerous"),
        (r"exec\s*\(", "Use of exec() is dangerous"),
        (r"__import__\s*\(", "Dynamic imports can be unsafe"),
        (r"password\s*=\s*['\"]", "Hardcoded password detected"),
        (r"api_key\s*=\s*['\"]", "Hardcoded API key detected"),
    ]
    
    def initialize(self, context: dict[str, Any]) -> None:
        """Initialize with custom context."""
        self.custom_rules = context.get("security_rules", [])
    
    async def review(self, context: ReviewContext) -> ReviewResult:
        """Execute security review."""
        issues = []
        suggestions = []
        
        content = context.content
        lines = content.split("\n")
        
        # Check dangerous patterns
        for pattern, message in self.DANGEROUS_PATTERNS:
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append(Issue(
                        severity=Severity.ERROR,
                        message=message,
                        location=f"line {i}",
                        code_snippet=line.strip()
                    ))
        
        # Add suggestions
        if any(i.severity == Severity.ERROR for i in issues):
            suggestions.append(Suggestion(
                message="Consider using environment variables for secrets",
                priority=1
            ))
        
        return ReviewResult(
            role=self.metadata.name,
            status=ReviewStatus.COMPLETED if not issues else ReviewStatus.COMPLETED,
            issues=issues,
            suggestions=suggestions,
            output=f"Found {len(issues)} security issues"
        )
```

---

## Plugin Metadata

### PluginMetadata Fields

```python
@dataclass
class PluginMetadata:
    name: str           # Unique identifier (lowercase, hyphens)
    version: str        # Semantic version (e.g., "1.0.0")
    description: str    # Human-readable description
    stage: Stage        # Execution stage
    dependencies: list[str]  # Required roles
    priority: int       # Execution order (lower = earlier)
```

### Stage Values

| Stage | When it Runs |
|-------|--------------|
| `planning` | Before development |
| `development` | During implementation |
| `review` | Code review phase |
| `testing` | QA/testing phase |
| `deployment` | Release preparation |

### Priority Guidelines

| Range | Usage |
|-------|-------|
| 0-20 | Foundation roles (architect) |
| 21-40 | Core development roles |
| 41-60 | Review and QA roles |
| 61-80 | Specialized checks |
| 81-100 | Final validation |

---

## Review Context

### ReviewContext Fields

```python
@dataclass
class ReviewContext:
    spec_type: SpecType     # Type of spec being reviewed
    content: str            # Spec content
    feature: str | None     # Feature name (if applicable)
    project_root: Path      # Project root path
    metadata: dict          # Additional context
```

### Accessing Context

```python
async def review(self, context: ReviewContext) -> ReviewResult:
    # Get spec type
    if context.spec_type == SpecType.PRD:
        # PRD-specific logic
        pass
    
    # Get feature context
    if context.feature:
        feature_spec = self._load_feature_spec(context.feature)
    
    # Access project files
    config_path = context.project_root / "specs" / "config.yaml"
```

---

## Review Results

### ReviewResult Fields

```python
@dataclass
class ReviewResult:
    role: str                      # Role name
    status: ReviewStatus           # Completion status
    issues: list[Issue]            # Problems found
    suggestions: list[Suggestion]  # Improvement suggestions
    output: str                    # Summary message
    started_at: datetime           # Start timestamp
    completed_at: datetime         # End timestamp
    duration_seconds: float        # Execution time
```

### Issue Severity

```python
class Severity(Enum):
    ERROR = "error"      # Must fix
    WARNING = "warning"  # Should fix
    INFO = "info"        # Consider fixing
```

### Creating Issues

```python
issues.append(Issue(
    severity=Severity.ERROR,
    message="Missing required section: ## Security",
    location="prd.md",
    code_snippet=None,
    suggestion="Add a security section covering authentication"
))
```

### Creating Suggestions

```python
suggestions.append(Suggestion(
    message="Consider adding rate limiting to API endpoints",
    priority=2,  # 1 = high, 5 = low
    code_example="@rate_limit(calls=100, period=60)"
))
```

---

## Registering Plugins

### Method 1: Entry Points

Add to `pyproject.toml`:

```toml
[project.entry-points."sdd_server.plugins"]
my_reviewer = "my_package.plugins:SecurityReviewer"
```

### Method 2: Direct Registration

```python
from sdd_server.plugins import PluginRegistry
from my_package.plugins import SecurityReviewer

registry = PluginRegistry()
registry.register("security-reviewer", SecurityReviewer())
```

### Method 3: Custom Plugin Loader

```python
from pathlib import Path
from sdd_server.plugins import PluginLoader

loader = PluginLoader(
    discovery_paths=[
        Path("./plugins"),
        Path("~/.sdd/plugins")
    ]
)

plugins = loader.discover()
for plugin in plugins:
    registry.register(plugin.metadata.name, plugin)
```

---

## Testing Plugins

### Unit Tests

```python
import pytest
from sdd_server.models.review import ReviewContext, SpecType
from sdd_server.plugins import PluginRegistry
from my_package.plugins import SecurityReviewer


@pytest.fixture
def reviewer():
    return SecurityReviewer()


@pytest.fixture
def context():
    return ReviewContext(
        spec_type=SpecType.ARCH,
        content="# Architecture\n\n...",
        feature=None,
        project_root=Path("/tmp/test"),
        metadata={}
    )


async def test_reviewer_finds_hardcoded_secrets(reviewer, context):
    context.content = 'password = "secret123"'
    
    result = await reviewer.review(context)
    
    assert result.status == ReviewStatus.COMPLETED
    assert len(result.issues) == 1
    assert "password" in result.issues[0].message.lower()


async def test_reviewer_passes_clean_content(reviewer, context):
    context.content = "# Clean architecture\n\nNo secrets here"
    
    result = await reviewer.review(context)
    
    assert result.status == ReviewStatus.COMPLETED
    assert len(result.issues) == 0
```

### Integration Tests

```python
async def test_plugin_with_registry():
    registry = PluginRegistry()
    reviewer = SecurityReviewer()
    registry.register("security-reviewer", reviewer)
    
    # Verify registration
    assert "security-reviewer" in registry.list_roles()
    
    # Get and execute
    plugin = registry.get_role("security-reviewer")
    result = await plugin.review(context)
    
    assert result is not None
```

---

## Best Practices

### 1. Keep Reviews Focused

Each role should have a single responsibility:

```python
# Good: Focused on one aspect
class SecurityReviewer(RolePlugin):
    metadata = PluginMetadata(name="security", ...)
    
    async def review(self, context):
        # Only security checks
        pass

# Bad: Multiple responsibilities
class EverythingReviewer(RolePlugin):
    async def review(self, context):
        # Security + Performance + Style
        pass
```

### 2. Use Appropriate Severity

```python
# Error: Must be fixed before proceeding
if missing_critical_section:
    issues.append(Issue(severity=Severity.ERROR, ...))

# Warning: Should be addressed but not blocking
if missing_optional_section:
    issues.append(Issue(severity=Severity.WARNING, ...))

# Info: Nice to have
if formatting_issue:
    issues.append(Issue(severity=Severity.INFO, ...))
```

### 3. Provide Actionable Suggestions

```python
# Good: Specific and actionable
suggestions.append(Suggestion(
    message="Add rate limiting to prevent API abuse",
    code_example="@rate_limit(calls=100, period=60)\nasync def api_endpoint(): ..."
))

# Bad: Vague
suggestions.append(Suggestion(
    message="Improve security"
))
```

### 4. Handle Errors Gracefully

```python
async def review(self, context: ReviewContext) -> ReviewResult:
    try:
        # Review logic
        pass
    except Exception as e:
        return ReviewResult(
            role=self.metadata.name,
            status=ReviewStatus.FAILED,
            issues=[Issue(
                severity=Severity.ERROR,
                message=f"Review failed: {e}"
            )],
            suggestions=[],
            output="Review failed"
        )
```

### 5. Use Dependencies Wisely

```python
# Security depends on developer being done
metadata = PluginMetadata(
    name="security",
    dependencies=["developer"],  # Run after developer
    priority=60  # Higher priority = runs later
)
```

### 6. Cache Expensive Operations

```python
class ExpensiveReviewer(RolePlugin):
    def initialize(self, context: dict) -> None:
        self._cache = {}
    
    async def review(self, context: ReviewContext) -> ReviewResult:
        cache_key = f"{context.spec_type}:{context.feature}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        result = await self._do_expensive_review(context)
        self._cache[cache_key] = result
        return result
```

---

## Example: Complete Custom Plugin Package

```
my_sdd_plugins/
├── __init__.py
├── security/
│   ├── __init__.py
│   ├── plugin.py        # SecurityReviewer class
│   └── rules.py         # Security rules/patterns
├── performance/
│   ├── __init__.py
│   ├── plugin.py        # PerformanceReviewer class
│   └── benchmarks.py    # Performance benchmarks
└── pyproject.toml       # Package configuration
```

```toml
# pyproject.toml
[project]
name = "my-sdd-plugins"
version = "1.0.0"

[project.entry-points."sdd_server.plugins"]
security = "my_sdd_plugins.security:SecurityReviewer"
performance = "my_sdd_plugins.performance:PerformanceReviewer"
```
