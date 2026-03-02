"""Unit tests for MCP review tools."""

import pytest
from mcp.server.fastmcp import FastMCP

from sdd_server.mcp.tools.review import register_tools


@pytest.fixture
def mcp_server() -> FastMCP:
    """Create a FastMCP server with review tools registered."""
    server = FastMCP("test-server")
    register_tools(server)
    return server


class TestReviewList:
    """Tests for sdd_review_list tool."""

    @pytest.mark.asyncio
    async def test_list_returns_roles(self, mcp_server: FastMCP) -> None:
        """Test that list returns all available roles."""
        # Find the tool
        tools = {t.name: t for t in mcp_server._tool_manager._tools.values()}
        assert "sdd_review_list" in tools

        # Call the tool
        result = await tools["sdd_review_list"].fn()

        assert "roles" in result
        assert "count" in result
        assert result["count"] == 6

    @pytest.mark.asyncio
    async def test_list_roles_sorted_by_priority(self, mcp_server: FastMCP) -> None:
        """Test that roles are sorted by priority."""
        tools = {t.name: t for t in mcp_server._tool_manager._tools.values()}
        result = await tools["sdd_review_list"].fn()

        priorities = [r["priority"] for r in result["roles"]]
        assert priorities == sorted(priorities)

    @pytest.mark.asyncio
    async def test_list_includes_dependencies(self, mcp_server: FastMCP) -> None:
        """Test that role dependencies are included."""
        tools = {t.name: t for t in mcp_server._tool_manager._tools.values()}
        result = await tools["sdd_review_list"].fn()

        roles_by_name = {r["name"]: r for r in result["roles"]}

        # Architect has no dependencies
        assert roles_by_name["architect"]["dependencies"] == []

        # Senior developer depends on all others
        assert len(roles_by_name["senior-developer"]["dependencies"]) > 0


class TestReviewRun:
    """Tests for sdd_review_run tool."""

    @pytest.mark.asyncio
    async def test_run_returns_error_for_unknown_role(self, mcp_server: FastMCP) -> None:
        """Test that unknown role returns error."""
        tools = {t.name: t for t in mcp_server._tool_manager._tools.values()}

        result = await tools["sdd_review_run"].fn(roles=["unknown-role"])

        assert result["status"] == "error"
        assert "Unknown roles" in result["error"]

    @pytest.mark.asyncio
    async def test_run_single_role(self, mcp_server: FastMCP) -> None:
        """Test running a single role."""
        tools = {t.name: t for t in mcp_server._tool_manager._tools.values()}

        result = await tools["sdd_review_run"].fn(roles=["architect"])

        assert result["status"] == "completed"
        assert "architect" in result["roles_run"]

    @pytest.mark.asyncio
    async def test_run_returns_results(self, mcp_server: FastMCP) -> None:
        """Test that run returns role results."""
        tools = {t.name: t for t in mcp_server._tool_manager._tools.values()}

        result = await tools["sdd_review_run"].fn(roles=["architect"])

        assert "results" in result
        assert "architect" in result["results"]
        assert "status" in result["results"]["architect"]

    @pytest.mark.asyncio
    async def test_run_includes_summary(self, mcp_server: FastMCP) -> None:
        """Test that run includes summary."""
        tools = {t.name: t for t in mcp_server._tool_manager._tools.values()}

        result = await tools["sdd_review_run"].fn(roles=["architect"])

        assert "summary" in result
        assert "architect" in result["summary"]


class TestReviewStatus:
    """Tests for sdd_review_status tool."""

    @pytest.mark.asyncio
    async def test_status_returns_state(self, mcp_server: FastMCP) -> None:
        """Test that status returns engine state."""
        tools = {t.name: t for t in mcp_server._tool_manager._tools.values()}

        result = await tools["sdd_review_status"].fn()

        assert "running" in result
        assert "completed" in result
        assert "failed" in result
        assert "success_rate" in result

    @pytest.mark.asyncio
    async def test_status_includes_dependency_graph(self, mcp_server: FastMCP) -> None:
        """Test that status includes dependency graph."""
        tools = {t.name: t for t in mcp_server._tool_manager._tools.values()}

        result = await tools["sdd_review_status"].fn()

        assert "dependency_graph" in result
        assert isinstance(result["dependency_graph"], dict)


class TestReviewResults:
    """Tests for sdd_review_results tool."""

    @pytest.mark.asyncio
    async def test_results_empty_initially(self, mcp_server: FastMCP) -> None:
        """Test that results are empty before any run."""
        from sdd_server.mcp.tools import review as review_module

        review_module._engine = None  # Reset global state

        tools = {t.name: t for t in mcp_server._tool_manager._tools.values()}

        result = await tools["sdd_review_results"].fn()

        assert "results" in result
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_results_after_run(self, mcp_server: FastMCP) -> None:
        """Test that results are available after run."""
        tools = {t.name: t for t in mcp_server._tool_manager._tools.values()}

        # Run a review first
        await tools["sdd_review_run"].fn(roles=["architect"])

        # Get results
        result = await tools["sdd_review_results"].fn()

        assert result["count"] >= 1
        assert "architect" in result["results"]

    @pytest.mark.asyncio
    async def test_results_for_specific_role(self, mcp_server: FastMCP) -> None:
        """Test getting results for a specific role."""
        tools = {t.name: t for t in mcp_server._tool_manager._tools.values()}

        # Run a review
        await tools["sdd_review_run"].fn(roles=["architect"])

        # Get results for specific role
        result = await tools["sdd_review_results"].fn(role="architect")

        assert "architect" in result["results"]
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_results_unknown_role(self, mcp_server: FastMCP) -> None:
        """Test getting results for unknown role."""
        tools = {t.name: t for t in mcp_server._tool_manager._tools.values()}

        result = await tools["sdd_review_results"].fn(role="unknown")

        assert "error" in result
        assert "available_roles" in result


class TestReviewReset:
    """Tests for sdd_review_reset tool."""

    @pytest.mark.asyncio
    async def test_reset_clears_state(self, mcp_server: FastMCP) -> None:
        """Test that reset clears engine state."""
        tools = {t.name: t for t in mcp_server._tool_manager._tools.values()}

        # Run a review
        await tools["sdd_review_run"].fn(roles=["architect"])

        # Reset
        result = await tools["sdd_review_reset"].fn()

        assert result["success"] is True

        # Check status is cleared
        status = await tools["sdd_review_status"].fn()
        assert status["total_results"] == 0


class TestRecipesGenerate:
    """Tests for sdd_recipes_generate tool."""

    @pytest.mark.asyncio
    async def test_generate_creates_recipes(
        self,
        mcp_server: FastMCP,
        tmp_project,
    ) -> None:
        """Test that generate creates recipe files."""
        import os

        os.environ["SDD_PROJECT_ROOT"] = str(tmp_project)

        tools = {t.name: t for t in mcp_server._tool_manager._tools.values()}

        result = await tools["sdd_recipes_generate"].fn(
            project_name="TestProject",
            description="A test project",
        )

        assert "generated" in result
        assert result["count"] == 6

    @pytest.mark.asyncio
    async def test_generate_validates_recipes(self, mcp_server: FastMCP, tmp_project) -> None:
        """Test that generate validates created recipes."""
        import os

        os.environ["SDD_PROJECT_ROOT"] = str(tmp_project)

        # Reset generator to pick up new project root
        from sdd_server.mcp.tools import review as review_module

        review_module._generator = None

        tools = {t.name: t for t in mcp_server._tool_manager._tools.values()}

        result = await tools["sdd_recipes_generate"].fn(
            project_name="TestProject",
        )

        assert "validation" in result
        # All recipes should be valid
        for role, issues in result["validation"].items():
            assert issues == [], f"{role} has validation issues: {issues}"


class TestRecipeRender:
    """Tests for sdd_recipe_render tool."""

    @pytest.mark.asyncio
    async def test_render_returns_content(self, mcp_server: FastMCP) -> None:
        """Test that render returns rendered content."""
        tools = {t.name: t for t in mcp_server._tool_manager._tools.values()}

        result = await tools["sdd_recipe_render"].fn(
            role="architect",
            project_name="TestProject",
        )

        assert result["valid"] is True
        assert "content" in result
        assert "TestProject" in result["content"]

    @pytest.mark.asyncio
    async def test_render_unknown_role(self, mcp_server: FastMCP) -> None:
        """Test render with unknown role."""
        tools = {t.name: t for t in mcp_server._tool_manager._tools.values()}

        result = await tools["sdd_recipe_render"].fn(
            role="unknown",
            project_name="TestProject",
        )

        assert result["valid"] is False
        assert "error" in result
