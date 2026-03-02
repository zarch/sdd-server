"""Spec file models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from sdd_server.models.base import SDDBaseModel


class SpecType(StrEnum):
    """Types of spec files."""

    PRD = "prd"
    ARCH = "arch"
    TASKS = "tasks"
    CONTEXT_HINTS = "context-hints"


class SpecFile(SDDBaseModel):
    """Represents a spec file on disk."""

    spec_type: SpecType
    path: Path
    feature: str | None = None
    exists: bool = False
    size_bytes: int = 0
    last_modified: datetime | None = None


class PRDMetadata(SDDBaseModel):
    """Metadata extracted from a PRD file."""

    project_name: str
    description: str
    version: str = "1.0"
    date: str = ""


class Feature(SDDBaseModel):
    """A feature in the project."""

    name: str
    description: str = ""
    spec_dir: Path | None = None
