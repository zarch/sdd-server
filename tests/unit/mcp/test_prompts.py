"""Unit tests for MCP review prompts."""

import pytest
from mcp.server.fastmcp import FastMCP

from sdd_server.mcp.prompts.review import register_prompts


@pytest.fixture
def mcp_server() -> FastMCP:
    """Create a FastMCP server with review prompts registered."""
    server = FastMCP("test-server")
    register_prompts(server)
    return server


class TestPromptRegistration:
    """Tests for prompt registration."""

    def test_prompts_registered(self, mcp_server: FastMCP) -> None:
        """Test that all prompts are registered."""
        # Access the prompt manager
        prompts = list(mcp_server._prompt_manager._prompts.keys())

        assert "sdd_review_architect" in prompts
        assert "sdd_review_ui_designer" in prompts
        assert "sdd_review_interface_designer" in prompts
        assert "sdd_review_security_analyst" in prompts
        assert "sdd_review_edge_case_analyst" in prompts
        assert "sdd_review_senior_developer" in prompts
        assert "sdd_review_full" in prompts

    def test_prompt_count(self, mcp_server: FastMCP) -> None:
        """Test that all 7 prompts are registered."""
        prompts = list(mcp_server._prompt_manager._prompts.keys())
        assert len(prompts) == 7


class TestArchitectPrompt:
    """Tests for sdd_review_architect prompt."""

    @pytest.mark.asyncio
    async def test_returns_messages(self, mcp_server: FastMCP) -> None:
        """Test that prompt returns messages."""
        prompts = mcp_server._prompt_manager._prompts
        prompt_fn = prompts["sdd_review_architect"]

        messages = prompt_fn.fn(project_name="TestProject")

        assert isinstance(messages, list)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_includes_project_name(self, mcp_server: FastMCP) -> None:
        """Test that project name is included in prompt."""
        prompts = mcp_server._prompt_manager._prompts
        prompt_fn = prompts["sdd_review_architect"]

        messages = prompt_fn.fn(project_name="MyAwesomeProject")

        assert "MyAwesomeProject" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_includes_feature_when_provided(self, mcp_server: FastMCP) -> None:
        """Test that feature is included when provided."""
        prompts = mcp_server._prompt_manager._prompts
        prompt_fn = prompts["sdd_review_architect"]

        messages = prompt_fn.fn(project_name="TestProject", feature="authentication")

        assert "authentication" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_no_feature_when_empty(self, mcp_server: FastMCP) -> None:
        """Test that feature is not mentioned when empty."""
        prompts = mcp_server._prompt_manager._prompts
        prompt_fn = prompts["sdd_review_architect"]

        messages = prompt_fn.fn(project_name="TestProject", feature="")

        # Should not have the focus sentence
        assert "Focus specifically on" not in messages[0]["content"]


class TestUIデザイナーPrompt:
    """Tests for sdd_review_ui_designer prompt."""

    @pytest.mark.asyncio
    async def test_returns_messages(self, mcp_server: FastMCP) -> None:
        """Test that prompt returns messages."""
        prompts = mcp_server._prompt_manager._prompts
        prompt_fn = prompts["sdd_review_ui_designer"]

        messages = prompt_fn.fn(project_name="TestProject")

        assert isinstance(messages, list)
        assert "UI/UX Designer" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_includes_responsibilities(self, mcp_server: FastMCP) -> None:
        """Test that UI responsibilities are included."""
        prompts = mcp_server._prompt_manager._prompts
        prompt_fn = prompts["sdd_review_ui_designer"]

        messages = prompt_fn.fn(project_name="TestProject")

        assert "CLI commands" in messages[0]["content"]
        assert "error messages" in messages[0]["content"]


class TestInterfaceDesignerPrompt:
    """Tests for sdd_review_interface_designer prompt."""

    @pytest.mark.asyncio
    async def test_returns_messages(self, mcp_server: FastMCP) -> None:
        """Test that prompt returns messages."""
        prompts = mcp_server._prompt_manager._prompts
        prompt_fn = prompts["sdd_review_interface_designer"]

        messages = prompt_fn.fn(project_name="TestProject")

        assert isinstance(messages, list)
        assert "Interface Designer" in messages[0]["content"]


class TestSecurityAnalystPrompt:
    """Tests for sdd_review_security_analyst prompt."""

    @pytest.mark.asyncio
    async def test_returns_messages(self, mcp_server: FastMCP) -> None:
        """Test that prompt returns messages."""
        prompts = mcp_server._prompt_manager._prompts
        prompt_fn = prompts["sdd_review_security_analyst"]

        messages = prompt_fn.fn(project_name="TestProject")

        assert isinstance(messages, list)
        assert "Security Analyst" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_includes_security_topics(self, mcp_server: FastMCP) -> None:
        """Test that security topics are included."""
        prompts = mcp_server._prompt_manager._prompts
        prompt_fn = prompts["sdd_review_security_analyst"]

        messages = prompt_fn.fn(project_name="TestProject")

        assert "threat" in messages[0]["content"].lower()
        assert "vulnerabilities" in messages[0]["content"].lower()


class TestEdgeCaseAnalystPrompt:
    """Tests for sdd_review_edge_case_analyst prompt."""

    @pytest.mark.asyncio
    async def test_returns_messages(self, mcp_server: FastMCP) -> None:
        """Test that prompt returns messages."""
        prompts = mcp_server._prompt_manager._prompts
        prompt_fn = prompts["sdd_review_edge_case_analyst"]

        messages = prompt_fn.fn(project_name="TestProject")

        assert isinstance(messages, list)
        assert "Edge Case Analyst" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_includes_edge_case_topics(self, mcp_server: FastMCP) -> None:
        """Test that edge case topics are included."""
        prompts = mcp_server._prompt_manager._prompts
        prompt_fn = prompts["sdd_review_edge_case_analyst"]

        messages = prompt_fn.fn(project_name="TestProject")

        assert "boundary" in messages[0]["content"].lower()
        assert "failure" in messages[0]["content"].lower()


class TestSeniorDeveloperPrompt:
    """Tests for sdd_review_senior_developer prompt."""

    @pytest.mark.asyncio
    async def test_returns_messages(self, mcp_server: FastMCP) -> None:
        """Test that prompt returns messages."""
        prompts = mcp_server._prompt_manager._prompts
        prompt_fn = prompts["sdd_review_senior_developer"]

        messages = prompt_fn.fn(project_name="TestProject")

        assert isinstance(messages, list)
        assert "Senior Developer" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_includes_kiss_principle(self, mcp_server: FastMCP) -> None:
        """Test that KISS principle is mentioned."""
        prompts = mcp_server._prompt_manager._prompts
        prompt_fn = prompts["sdd_review_senior_developer"]

        messages = prompt_fn.fn(project_name="TestProject")

        assert "KISS" in messages[0]["content"]


class TestFullReviewPrompt:
    """Tests for sdd_review_full prompt."""

    @pytest.mark.asyncio
    async def test_returns_messages(self, mcp_server: FastMCP) -> None:
        """Test that prompt returns messages."""
        prompts = mcp_server._prompt_manager._prompts
        prompt_fn = prompts["sdd_review_full"]

        messages = prompt_fn.fn(project_name="TestProject")

        assert isinstance(messages, list)

    @pytest.mark.asyncio
    async def test_includes_all_roles(self, mcp_server: FastMCP) -> None:
        """Test that all roles are mentioned in full review."""
        prompts = mcp_server._prompt_manager._prompts
        prompt_fn = prompts["sdd_review_full"]

        messages = prompt_fn.fn(project_name="TestProject")
        content = messages[0]["content"]

        assert "Architect" in content
        assert "UI Designer" in content
        assert "Interface Designer" in content
        assert "Security Analyst" in content
        assert "Edge Case Analyst" in content
        assert "Senior Developer" in content

    @pytest.mark.asyncio
    async def test_describes_execution_order(self, mcp_server: FastMCP) -> None:
        """Test that execution order is described."""
        prompts = mcp_server._prompt_manager._prompts
        prompt_fn = prompts["sdd_review_full"]

        messages = prompt_fn.fn(project_name="TestProject")
        content = messages[0]["content"]

        assert "dependency order" in content.lower() or "in order" in content.lower()
