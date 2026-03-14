"""AIClientBridge — abstract interface and Goose CLI implementation.

Architecture reference: arch.md Section 5.3
"""

from __future__ import annotations

import asyncio
import re
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from sdd_server.core.goose_session import (
    GooseConfig,
    GooseSession,
    RecipeNotFoundError,
    SessionStatus,
)
from sdd_server.models.base import SDDBaseModel
from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Result model
# =============================================================================


class ClientResult(SDDBaseModel):
    """Result from an AI client invocation."""

    success: bool
    output: str
    error: str | None = None
    exit_code: int = 0
    tokens_used: int | None = None  # For cost tracking


# =============================================================================
# Abstract interface
# =============================================================================


class AIClientBridge(ABC):
    """Abstract interface for AI client execution.

    All role invocations, task executions, and alignment checks go through
    this interface so the underlying client is swappable (e.g. Goose → Claude).
    """

    @abstractmethod
    async def execute_task(
        self,
        task_id: str,
        prompt: str,
        recipe: str | None = None,
    ) -> ClientResult:
        """Execute a task prompt via the AI client."""
        ...

    @abstractmethod
    async def invoke_role(
        self,
        role_name: str,
        context: dict[str, Any],
        recipe_path: Path | None = None,
    ) -> ClientResult:
        """Invoke a role via the AI client."""
        ...

    @abstractmethod
    async def run_alignment_check(
        self,
        spec_context: str,
        code_diff: str,
    ) -> ClientResult:
        """Run LLM-based semantic alignment check."""
        ...

    @abstractmethod
    async def get_version(self) -> str:
        """Return client version string."""
        ...

    @abstractmethod
    async def check_compatibility(self) -> tuple[bool, str]:
        """Check if the client version is compatible with this server.

        Returns:
            (compatible, message) where compatible is True if OK.
        """
        ...

    @property
    def is_available(self) -> bool:
        """Return True if the AI client binary is reachable."""
        return False


# =============================================================================
# Goose implementation
# =============================================================================


class GooseClientBridge(AIClientBridge):
    """Goose CLI implementation of AIClientBridge.

    Wraps GooseSession to provide the abstract AIClientBridge interface.
    Each call creates a fresh GooseSession so there is no shared state.
    """

    def __init__(
        self,
        project_root: Path,
        timeout: float = 300.0,
        goose_path: str = "goose",
    ) -> None:
        self._project_root = project_root
        self._timeout = timeout
        self._goose_path = goose_path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_session(
        self,
        *,
        session_name: str | None = None,
        resume: bool = False,
        fork: bool = False,
    ) -> GooseSession:
        config = GooseConfig(
            goose_path=self._goose_path,
            timeout_seconds=self._timeout,
            working_dir=self._project_root,
            session_name=session_name,
            resume=resume,
            fork=fork,
        )
        return GooseSession(config)

    def _to_client_result(self, session_result: Any) -> ClientResult:
        """Convert SessionResult → ClientResult."""
        success = session_result.status == SessionStatus.COMPLETED
        exit_code = 0 if success else 1
        error = session_result.error
        if not success and session_result.needs_retry:
            error = f"needs_retry: {session_result.envelope.retry_hint or 'agent requested retry'}"
        return ClientResult(
            success=success,
            output=session_result.output,
            error=error,
            exit_code=exit_code,
        )

    # ------------------------------------------------------------------
    # AIClientBridge interface
    # ------------------------------------------------------------------

    async def execute_task(
        self,
        task_id: str,
        prompt: str,
        recipe: str | None = None,
    ) -> ClientResult:
        """Execute a task prompt.

        If *recipe* is a path to a recipe file it is used directly;
        otherwise a minimal inline recipe is generated from *prompt*.
        """
        session = self._make_session()

        if recipe and Path(recipe).exists():
            result = await session.execute_recipe(
                recipe_path=Path(recipe),
                params={"task_id": task_id},
            )
        else:
            # Fall back to text-only invocation (no recipe file)
            result = await session.execute_recipe(
                recipe_path=self._project_root / "recipes" / "default.yml",
                instructions=prompt,
                params={"task_id": task_id},
            )

        return self._to_client_result(result)

    async def invoke_role(
        self,
        role_name: str,
        context: dict[str, Any],
        recipe_path: Path | None = None,
    ) -> ClientResult:
        """Invoke a role via the AI client.

        Args:
            role_name: Name of the role (e.g. "architect").
            context: Dict of context values (spec paths, feature name, etc.).
            recipe_path: Explicit recipe file; defaults to recipes/<role_name>.yml.
        """
        if recipe_path is None:
            recipe_path = self._project_root / "recipes" / f"{role_name}.yml"

        # Build deterministic session name
        scope = context.get("scope", "all")
        feature = str(context.get("feature", "") or context.get("target", ""))
        qualifier = feature or scope
        # sanitize: lowercase, replace non-alphanumeric (except dashes) with dashes
        qualifier = re.sub(r"[^a-z0-9-]", "-", qualifier.lower()).strip("-") or "default"
        session_name = f"sdd-{role_name}-{qualifier}"

        session = self._make_session(session_name=session_name, resume=True)
        params = {k: str(v) for k, v in context.items() if isinstance(v, (str, int, float, Path))}
        try:
            result = await session.execute_recipe(recipe_path=recipe_path, params=params)
        except RecipeNotFoundError as exc:
            return ClientResult(success=False, output="", error=str(exc), exit_code=1)
        return self._to_client_result(result)

    async def run_alignment_check(
        self,
        spec_context: str,
        code_diff: str,
    ) -> ClientResult:
        """Send spec + diff to Goose for semantic alignment assessment.

        Uses the alignment recipe if available; otherwise uses an inline prompt.
        """
        alignment_recipe = self._project_root / "recipes" / "alignment.yml"
        session = self._make_session()

        prompt = (
            "You are a spec-code alignment checker.\n\n"
            "## Spec context\n"
            f"{spec_context}\n\n"
            "## Code diff\n"
            f"{code_diff}\n\n"
            "Identify any misalignment between the spec and the code changes. "
            "Return a JSON object with keys: overall_status (aligned|diverged|missing_spec|missing_code), "
            "issues (list of {file, spec_ref, status, description, suggested_action, severity}), "
            "summary ({aligned, diverged, missing_spec, missing_code counts})."
        )

        if alignment_recipe.exists():
            result = await session.execute_recipe(
                recipe_path=alignment_recipe,
                instructions=prompt,
            )
        else:
            # No recipe file — pass instructions to default recipe if available
            default_recipe = self._project_root / "recipes" / "default.yml"
            if default_recipe.exists():
                result = await session.execute_recipe(
                    recipe_path=default_recipe,
                    instructions=prompt,
                )
            else:
                # No recipe at all — return a stub result
                logger.warning("No recipe file found for alignment check; returning stub")
                return ClientResult(
                    success=False,
                    output="",
                    error="No recipe file configured for alignment checks",
                    exit_code=1,
                )

        return self._to_client_result(result)

    async def get_version(self) -> str:
        """Return the Goose CLI version string."""
        try:
            proc = await asyncio.create_subprocess_exec(
                self._goose_path,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)
            if proc.returncode == 0:
                return stdout.decode().strip() or stderr.decode().strip()
            return f"unknown (exit {proc.returncode})"
        except FileNotFoundError:
            return "unavailable"
        except TimeoutError:
            return "unavailable"

    async def check_compatibility(self) -> tuple[bool, str]:
        """Check whether Goose is reachable and at a usable version."""
        version = await self.get_version()
        if version == "unavailable":
            return False, "Goose CLI not found on PATH"
        return True, f"Goose available: {version}"

    @property
    def is_available(self) -> bool:
        """Return True if the goose binary exists on PATH."""
        return shutil.which(self._goose_path) is not None


# =============================================================================
# Factory
# =============================================================================


def create_ai_client(
    client_type: str,
    project_root: Path,
    timeout: float = 300.0,
) -> AIClientBridge:
    """Instantiate the correct bridge from a client-type string.

    Args:
        client_type: One of "goose". Controlled by SDD_AI_CLIENT env var.
        project_root: Project root directory.
        timeout: Subprocess timeout in seconds.

    Returns:
        Configured AIClientBridge instance.

    Raises:
        ValueError: If *client_type* is not recognised.
    """
    match client_type:
        case "goose":
            return GooseClientBridge(project_root=project_root, timeout=timeout)
        case _:
            raise ValueError(f"Unknown AI client type: {client_type!r}")
