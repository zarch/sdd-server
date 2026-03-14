"""MCP tools: sdd_init and sdd_preflight."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP

from sdd_server.core.initializer import ProjectInitializer
from sdd_server.core.spec_manager import SpecManager
from sdd_server.core.spec_validator import SpecValidator
from sdd_server.core.startup import StartupValidator
from sdd_server.infrastructure.git import GitClient
from sdd_server.infrastructure.observability.audit import AuditEventType, get_audit_logger
from sdd_server.mcp.tools._utils import check_rate_limit, format_error


def register_tools(mcp: FastMCP) -> None:
    """Register init tools on the given FastMCP instance."""

    @mcp.tool()
    async def sdd_init(
        project_name: str,
        description: str = "",
        project_root: str = "",
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, object]:
        """Initialize a new SDD project: create specs/ structure, render templates, install git hook.

        Args:
            project_name: Name of the project.
            description: Short project description.
            project_root: Override project root path (defaults to SDD_PROJECT_ROOT env var or cwd).
        """
        if rate_err := check_rate_limit("sdd_init"):
            return rate_err

        import os

        root = (
            Path(project_root).resolve()
            if project_root
            else Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()
        )

        audit = get_audit_logger()
        if ctx and hasattr(ctx, "request_context") and ctx.request_context:
            state = ctx.request_context.lifespan_context
            git_client = state["git_client"]
            spec_manager = state["spec_manager"]
        else:
            git_client = GitClient(root)
            spec_manager = SpecManager(root)

        try:
            initializer = ProjectInitializer(root, spec_manager, git_client)
            initializer.init_new_project(project_name, description)

            validator = StartupValidator(root)
            report = validator.run()

            audit.log_event(
                AuditEventType.SYSTEM_STARTUP,
                message=f"Initialized project: {project_name}",
                resource=str(root),
                result="success",
            )

            warnings = [c.message for c in report.warnings]
            return {
                "success": True,
                "project_root": str(root),
                "warnings": warnings,
                "message": f"Project '{project_name}' initialized at '{root}'",
            }
        except Exception as exc:
            audit.log_event(
                AuditEventType.SYSTEM_STARTUP,
                message=f"Failed to initialize project: {project_name}",
                resource=str(root),
                result="failure",
            )
            return format_error(exc)

    @mcp.tool()
    async def sdd_preflight(
        ctx: Context | None = None,  # type: ignore[type-arg]
    ) -> dict[str, object]:
        """Run preflight checks: validate spec structure and return enforcement status.

        Checks performed:
        1. Core spec files present (prd.md, arch.md, tasks.md)
        2. Spec validation rules (content, required sections)
        3. Git pre-commit hook installed

        Returns:
            allowed: True only when all blocking checks pass.
            structural_issues: Missing or malformed spec files.
            validation_errors: Rule violations found by the spec validator.
            warnings: Non-blocking issues (e.g. missing git hook).
            checks_passed: Count of checks that passed.
            checks_total: Total checks run.
        """
        try:
            import os

            if ctx and hasattr(ctx, "request_context") and ctx.request_context:
                state = ctx.request_context.lifespan_context
                spec_manager: SpecManager = state["spec_manager"]
                spec_validator: SpecValidator = state["spec_validator"]
                git_client = state["git_client"]
                root = state["project_root"]
            else:
                root = Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()
                spec_manager = SpecManager(root)
                spec_validator = SpecValidator(root)
                git_client = GitClient(root)

            checks_passed = 0
            checks_total = 0
            structural_issues: list[str] = []
            validation_errors: list[str] = []
            warnings: list[str] = []

            # --- Check 1: core spec files exist ---
            checks_total += 1
            structural_issues = spec_manager.validate_structure()
            if not structural_issues:
                checks_passed += 1

            # --- Check 2: spec validation rules ---
            checks_total += 1
            try:
                validation_result = spec_validator.validate_project(include_features=True)
                if validation_result.is_valid:
                    checks_passed += 1
                else:
                    for spec_res in validation_result.spec_results:
                        for issue in spec_res.issues:
                            from sdd_server.models.validation import ValidationSeverity

                            loc = spec_res.spec_type.value
                            if spec_res.feature:
                                loc = f"{spec_res.feature}/{loc}"
                            msg = f"[{loc}] {issue.rule_name}: {issue.message}"
                            if issue.severity == ValidationSeverity.ERROR:
                                validation_errors.append(msg)
                            else:
                                warnings.append(msg)
            except Exception:
                # Validation may fail if no spec files exist yet — treat as warning
                warnings.append("Spec validator could not run (no spec files found)")

            # --- Check 3: git pre-commit hook installed ---
            checks_total += 1
            hook_ok = git_client.is_hook_installed("pre-commit")
            if hook_ok:
                checks_passed += 1
            else:
                warnings.append("pre-commit hook not installed — run 'sdd init' to install it")

            allowed = len(structural_issues) == 0 and len(validation_errors) == 0
            return {
                "allowed": allowed,
                "structural_issues": structural_issues,
                "validation_errors": validation_errors,
                "warnings": warnings,
                "checks_passed": checks_passed,
                "checks_total": checks_total,
            }
        except Exception as exc:
            return format_error(exc)
