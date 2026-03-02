"""SDD exception hierarchy."""


class SDDError(Exception):
    """Base exception for all SDD errors."""


class FileSystemError(SDDError):
    """File system operation failed."""


class PathTraversalError(FileSystemError):
    """Attempted path traversal outside allowed root."""


class GitError(SDDError):
    """Git operation failed."""


class SpecNotFoundError(SDDError):
    """Requested spec file does not exist."""


class ValidationError(SDDError):
    """Validation failed."""


class EnforcementError(SDDError):
    """Enforcement check failed."""
