"""Shared enums for the SDD plugin system.

Kept in models (not plugins) to avoid circular imports:
- plugins/base.py imports models.base → triggers models/__init__
- models/__init__ imports models.custom_plugin → needs RoleStage
- By living here, RoleStage/RoleStatus have no deps on plugins.*
"""

from enum import StrEnum


class RoleStage(StrEnum):
    """Workflow stages for role execution.

    Order defines the default execution sequence.
    Dependencies between stages are handled by RoleEngine.
    """

    SPEC_AUDIT = "spec-audit"
    ARCHITECTURE = "architecture"
    UI_DESIGN = "ui-design"
    INTERFACE_DESIGN = "interface-design"
    SECURITY = "security"
    EDGE_CASE_ANALYSIS = "edge-case-analysis"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"
    QA = "qa"
    DOCUMENTATION = "documentation"
    DEVOPS = "devops"
    RELEASE = "release"


class RoleStatus(StrEnum):
    """Status of a role execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
