"""SDD MCP server — lifespan, context setup, and tool/resource registration."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from sdd_server.core.metadata import MetadataManager
from sdd_server.core.spec_manager import SpecManager
from sdd_server.core.startup import StartupValidator
from sdd_server.infrastructure.git import GitClient
from sdd_server.utils.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict[str, object]]:
    """Set up server context on startup; validate environment."""
    configure_logging(level=os.getenv("SDD_LOG_LEVEL", "INFO"))

    project_root = Path(os.getenv("SDD_PROJECT_ROOT", ".")).resolve()
    specs_dir = os.getenv("SPECS_DIR", "specs")

    logger.info("sdd_server_starting", project_root=str(project_root))

    spec_manager = SpecManager(project_root, specs_dir)
    metadata = MetadataManager(project_root, specs_dir)
    git_client = GitClient(project_root)

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

    yield {
        "project_root": project_root,
        "spec_manager": spec_manager,
        "metadata": metadata,
        "git_client": git_client,
    }

    logger.info("sdd_server_stopped")


def create_server() -> FastMCP:
    """Create and configure the FastMCP server with all tools and resources."""
    server = FastMCP("sdd-server", lifespan=lifespan)

    # Import tool/resource modules to trigger decorator registration
    # These imports must happen after server is created
    from sdd_server.mcp.prompts.review import register_prompts as reg_prompts
    from sdd_server.mcp.resources.specs import register_resources
    from sdd_server.mcp.tools.feature import register_tools as reg_feature
    from sdd_server.mcp.tools.init import register_tools as reg_init
    from sdd_server.mcp.tools.review import register_tools as reg_review
    from sdd_server.mcp.tools.spec import register_tools as reg_spec
    from sdd_server.mcp.tools.status import register_tools as reg_status

    reg_init(server)
    reg_spec(server)
    reg_feature(server)
    reg_status(server)
    reg_review(server)
    reg_prompts(server)
    register_resources(server)

    return server


mcp = create_server()
