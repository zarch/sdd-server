"""MCP prompts: role-based review prompts.

Provides prompts for running role-based code reviews with proper context
and instructions for each role.

Each role has a dedicated prompt that:
- Sets up the role's context and responsibilities
- Provides instructions for the review task
- Includes relevant project information
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from sdd_server.plugins.registry import PluginRegistry
from sdd_server.plugins.roles import BUILTIN_ROLES
from sdd_server.utils.logging import get_logger

logger = get_logger(__name__)


def _get_registry() -> PluginRegistry:
    """Get the plugin registry with builtin roles."""
    registry = PluginRegistry()
    for role_class in BUILTIN_ROLES:
        role = role_class()
        registry.register(role.metadata.name, role)
    return registry


def register_prompts(mcp: FastMCP) -> None:
    """Register role prompts on the given FastMCP instance."""

    @mcp.prompt()
    def sdd_review_architect(project_name: str, feature: str = "") -> list[dict[str, Any]]:
        """Run an architecture review for the project.

        The Architect role is responsible for system structure, technology
        choices, data flow, and integration points.

        Args:
            project_name: Name of the project to review
            feature: Optional feature to focus the review on

        Returns:
            List of messages for the prompt
        """
        focus = f" Focus specifically on the '{feature}' feature." if feature else ""
        return [
            {
                "role": "user",
                "content": f"""You are the System Architect for the {project_name} project.{focus}

Your responsibilities:
1. Define system components and their boundaries
2. Document technology choices with rationale
3. Design data flow between components
4. Identify external dependencies
5. Create component interaction diagrams
6. Establish coding standards and patterns

Review Process:
1. Read the PRD at specs/prd.md to understand requirements
2. Review existing architecture in specs/arch.md (if exists)
3. Analyze the codebase structure
4. Update or create the architecture document

Output Requirements:
- Update specs/arch.md with your findings
- Include component diagrams using ASCII or Mermaid
- Document all significant technical decisions
- List assumptions and constraints
- Identify potential risks and mitigations

Begin by reading the PRD and existing specs, then provide your architecture review.""",
            }
        ]

    @mcp.prompt()
    def sdd_review_ui_designer(project_name: str, feature: str = "") -> list[dict[str, Any]]:
        """Run a UI/UX design review for the project.

        The UI Designer role is responsible for CLI commands, configuration,
        environment variables, and user-facing error messages.

        Args:
            project_name: Name of the project to review
            feature: Optional feature to focus the review on

        Returns:
            List of messages for the prompt
        """
        focus = f" Focus specifically on the '{feature}' feature." if feature else ""
        return [
            {
                "role": "user",
                "content": f"""You are the UI/UX Designer for the {project_name} project.{focus}

Your responsibilities:
1. Design CLI commands and arguments
2. Define configuration file formats
3. Document environment variables
4. Craft user-friendly error messages
5. Design user interaction flows
6. Ensure consistent user experience

Review Process:
1. Review the architecture document for UI/UX implications
2. Analyze existing CLI and configuration
3. Check error message clarity
4. Evaluate user interaction patterns

Output Requirements:
- Document CLI commands with examples
- List all configuration options
- Review error messages for clarity
- Suggest UX improvements

Begin your UI/UX review now.""",
            }
        ]

    @mcp.prompt()
    def sdd_review_interface_designer(project_name: str, feature: str = "") -> list[dict[str, Any]]:
        """Run an interface design review for the project.

        The Interface Designer role is responsible for APIs, file formats,
        and integration contracts.

        Args:
            project_name: Name of the project to review
            feature: Optional feature to focus the review on

        Returns:
            List of messages for the prompt
        """
        focus = f" Focus specifically on the '{feature}' feature." if feature else ""
        return [
            {
                "role": "user",
                "content": f"""You are the Interface Designer for the {project_name} project.{focus}

Your responsibilities:
1. Design and document APIs
2. Define file formats and schemas
3. Create integration contracts
4. Ensure interface consistency
5. Document interface versioning
6. Review backward compatibility

Review Process:
1. Review the architecture for interface requirements
2. Analyze existing API definitions
3. Check file format specifications
4. Validate integration contracts

Output Requirements:
- Document all public APIs
- Define request/response schemas
- List integration points
- Identify breaking change risks

Begin your interface design review now.""",
            }
        ]

    @mcp.prompt()
    def sdd_review_security_analyst(project_name: str, feature: str = "") -> list[dict[str, Any]]:
        """Run a security analysis review for the project.

        The Security Analyst role is responsible for threat modeling,
        input validation, and access controls.

        Args:
            project_name: Name of the project to review
            feature: Optional feature to focus the review on

        Returns:
            List of messages for the prompt
        """
        focus = f" Focus specifically on the '{feature}' feature." if feature else ""
        return [
            {
                "role": "user",
                "content": f"""You are the Security Analyst for the {project_name} project.{focus}

Your responsibilities:
1. Create threat models
2. Review input validation
3. Analyze access controls
4. Identify security vulnerabilities
5. Review authentication/authorization
6. Check data protection measures

Review Process:
1. Review architecture for security implications
2. Analyze input handling and validation
3. Check authentication mechanisms
4. Review authorization logic
5. Identify potential attack vectors

Output Requirements:
- Document threat model
- List security vulnerabilities found
- Provide remediation recommendations
- Review security best practices

Begin your security analysis now.""",
            }
        ]

    @mcp.prompt()
    def sdd_review_edge_case_analyst(project_name: str, feature: str = "") -> list[dict[str, Any]]:
        """Run an edge case analysis review for the project.

        The Edge Case Analyst role is responsible for identifying boundary
        conditions, failure modes, and test scenarios.

        Args:
            project_name: Name of the project to review
            feature: Optional feature to focus the review on

        Returns:
            List of messages for the prompt
        """
        focus = f" Focus specifically on the '{feature}' feature." if feature else ""
        return [
            {
                "role": "user",
                "content": f"""You are the Edge Case Analyst for the {project_name} project.{focus}

Your responsibilities:
1. Identify boundary conditions
2. Analyze failure modes
3. Design test scenarios
4. Find corner cases
5. Review error handling
6. Check resource limits

Review Process:
1. Review architecture and interfaces
2. Analyze security findings
3. Identify boundary conditions
4. Map failure scenarios
5. Design comprehensive tests

Output Requirements:
- List all edge cases identified
- Document failure modes
- Provide test scenarios
- Suggest robustness improvements

Begin your edge case analysis now.""",
            }
        ]

    @mcp.prompt()
    def sdd_review_senior_developer(project_name: str, feature: str = "") -> list[dict[str, Any]]:
        """Run a senior developer code review for the project.

        The Senior Developer role is responsible for KISS review, task
        breakdown, and testing strategy.

        Args:
            project_name: Name of the project to review
            feature: Optional feature to focus the review on

        Returns:
            List of messages for the prompt
        """
        focus = f" Focus specifically on the '{feature}' feature." if feature else ""
        return [
            {
                "role": "user",
                "content": f"""You are the Senior Developer for the {project_name} project.{focus}

Your responsibilities:
1. Apply KISS (Keep It Simple, Stupid) principle
2. Review code complexity
3. Break down implementation tasks
4. Define testing strategy
5. Ensure code quality
6. Mentor on best practices

Review Process:
1. Review all previous role findings
2. Analyze code complexity
3. Identify simplification opportunities
4. Create implementation task breakdown
5. Define testing approach

Output Requirements:
- KISS review findings
- Task breakdown for implementation
- Testing strategy recommendations
- Code quality assessment
- Best practice suggestions

Begin your senior developer review now.""",
            }
        ]

    @mcp.prompt()
    def sdd_review_full(project_name: str, feature: str = "") -> list[dict[str, Any]]:
        """Run a complete multi-role review for the project.

        Executes all roles in dependency order for a comprehensive review.

        Args:
            project_name: Name of the project to review
            feature: Optional feature to focus the review on

        Returns:
            List of messages for the prompt
        """
        focus = f" Focus specifically on the '{feature}' feature." if feature else ""
        return [
            {
                "role": "user",
                "content": f"""You are conducting a comprehensive multi-role review for the {project_name} project.{focus}

Execute the following roles in order, each building on the previous findings:

1. **Architect** - System structure, tech stack, data flow
2. **UI Designer** - CLI commands, config, error messages
3. **Interface Designer** - APIs, file formats, contracts
4. **Security Analyst** - Threat model, validation, access control
5. **Edge Case Analyst** - Boundary conditions, failure modes
6. **Senior Developer** - KISS review, task breakdown, testing

For each role:
- Review the project from that perspective
- Document your findings
- Pass relevant context to the next role

Final Deliverables:
- Complete review summary
- Prioritized issue list
- Implementation recommendations
- Testing strategy

Begin the comprehensive review now, starting with the Architect role.""",
            }
        ]

    logger.info("Registered role prompts", count=7)
