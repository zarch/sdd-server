"""SDD MCP server — lifespan, context setup, and tool/resource registration."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TypedDict

from mcp.server.fastmcp import FastMCP

from sdd_server.core.ai_client import AIClientBridge, create_ai_client
from sdd_server.core.code_generator import CodeGenerator
from sdd_server.core.custom_plugin_manager import CustomPluginManager
from sdd_server.core.metadata import MetadataManager
from sdd_server.core.spec_manager import SpecManager
from sdd_server.core.spec_validator import SpecValidator
from sdd_server.core.startup import StartupValidator
from sdd_server.core.task_manager import TaskBreakdownManager
from sdd_server.infrastructure.config import get_config
from sdd_server.infrastructure.git import GitClient
from sdd_server.infrastructure.observability.audit import configure_audit_logger
from sdd_server.infrastructure.observability.health import FilesystemCheck, health_check_registry
from sdd_server.infrastructure.observability.metrics import get_metrics
from sdd_server.infrastructure.security.rate_limiter import RateLimitConfig, configure_rate_limiter
from sdd_server.utils.logging import configure_logging, get_logger

logger = get_logger(__name__)


class LifespanContext(TypedDict):
    """Typed context dict yielded by the MCP server lifespan."""

    project_root: Path
    spec_manager: SpecManager
    metadata: MetadataManager
    git_client: GitClient
    task_manager: TaskBreakdownManager
    code_generator: CodeGenerator
    spec_validator: SpecValidator
    custom_plugin_manager: CustomPluginManager
    ai_client: AIClientBridge


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[LifespanContext]:
    """Set up server context on startup; validate environment."""
    configure_logging(level=os.getenv("SDD_LOG_LEVEL", "INFO"))

    config = get_config()

    # Configure audit logger
    if config.observability.audit.enabled and config.observability.audit.file_path:
        configure_audit_logger(file_path=Path(config.observability.audit.file_path))

    # Configure rate limiter from config
    rate_cfg = RateLimitConfig(
        requests_per_window=config.security.rate_limit.requests_per_window,
        window_seconds=config.security.rate_limit.window_seconds,
    )
    configure_rate_limiter(rate_cfg)

    # Initialise metrics collector
    get_metrics()

    project_root = Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()
    specs_dir = os.getenv("SPECS_DIR", "specs")

    logger.info("sdd_server_starting", project_root=str(project_root))

    # Register filesystem health check
    health_check_registry.register(FilesystemCheck(str(project_root), name="project_root"))

    spec_manager = SpecManager(project_root, specs_dir)
    metadata = MetadataManager(project_root, specs_dir)
    git_client = GitClient(project_root)
    task_manager = TaskBreakdownManager(project_root, specs_dir)
    code_generator = CodeGenerator(project_root, specs_dir)
    spec_validator = SpecValidator(project_root, specs_dir)
    custom_plugin_manager = CustomPluginManager(project_root, specs_dir)

    # Load custom plugins from directory
    custom_plugin_manager.load_from_directory()

    # AI client (Goose by default; non-fatal if unavailable)
    ai_client_type = os.getenv("SDD_AI_CLIENT", "goose")
    ai_timeout = float(os.getenv("SDD_AI_TIMEOUT", "300"))
    try:
        ai_client = create_ai_client(ai_client_type, project_root, timeout=ai_timeout)
        ok, msg = await ai_client.check_compatibility()
        if ok:
            logger.info("ai_client_ready", client=ai_client_type, info=msg)
        else:
            logger.warning("ai_client_unavailable", client=ai_client_type, reason=msg)
    except Exception as exc:
        logger.warning("ai_client_init_failed", client=ai_client_type, error=str(exc))
        # Fall back to a GooseClientBridge that will gracefully report unavailability
        from sdd_server.core.ai_client import GooseClientBridge

        ai_client = GooseClientBridge(project_root=project_root)

    # Run startup validation (non-blocking: log warnings, raise on fatal)
    validator = StartupValidator(project_root, specs_dir)
    report = validator.run()
    for check in report.checks:
        if check.passed:
            logger.debug("startup_check_passed", check=check.name, msg=check.message)
        elif check.fatal:
            logger.error("startup_check_failed", check=check.name, msg=check.message)
        else:
            logger.warning("startup_check_warning", check=check.name, msg=check.message)

    logger.info("sdd_server_ready", config_source="env+defaults")

    yield {
        "project_root": project_root,
        "spec_manager": spec_manager,
        "metadata": metadata,
        "git_client": git_client,
        "task_manager": task_manager,
        "code_generator": code_generator,
        "spec_validator": spec_validator,
        "custom_plugin_manager": custom_plugin_manager,
        "ai_client": ai_client,
    }

    logger.info("sdd_server_stopped")


def create_server() -> FastMCP:
    """Create and configure the FastMCP server with all tools and resources."""
    server = FastMCP("sdd-server", lifespan=lifespan)

    # Import tool/resource modules to trigger decorator registration
    # These imports must happen after server is created
    from sdd_server.mcp.prompts.review import register_prompts as reg_prompts
    from sdd_server.mcp.resources.specs import register_resources
    from sdd_server.mcp.tools.align import register_tools as reg_align
    from sdd_server.mcp.tools.bootstrap import register_tools as reg_bootstrap
    from sdd_server.mcp.tools.codegen import register_tools as reg_codegen
    from sdd_server.mcp.tools.custom_plugins import register_tools as reg_custom_plugins
    from sdd_server.mcp.tools.decompose import register_tools as reg_decompose
    from sdd_server.mcp.tools.feature import register_tools as reg_feature
    from sdd_server.mcp.tools.health import register_tools as reg_health
    from sdd_server.mcp.tools.init import register_tools as reg_init
    from sdd_server.mcp.tools.review import register_tools as reg_review
    from sdd_server.mcp.tools.spec import register_tools as reg_spec
    from sdd_server.mcp.tools.status import register_tools as reg_status
    from sdd_server.mcp.tools.task import register_tools as reg_task
    from sdd_server.mcp.tools.validation import register_tools as reg_validation

    reg_init(server)
    reg_spec(server)
    reg_feature(server)
    reg_status(server)
    reg_review(server)
    reg_task(server)
    reg_codegen(server)
    reg_validation(server)
    reg_custom_plugins(server)
    reg_align(server)
    reg_bootstrap(server)
    reg_decompose(server)
    reg_health(server)
    reg_prompts(server)
    register_resources(server)

    return server


mcp = create_server()
