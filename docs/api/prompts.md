# MCP Prompts Reference

The SDD Server provides role-specific prompts to guide AI assistants through spec reviews.

## Available Prompts

### sdd_review_prompt

Generate a review prompt for a specific role.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `role` | string | Yes | Role name (`architect`, `developer`, `reviewer`, `qa`, `security`, `devops`) |
| `spec_type` | string | No | Spec type to focus on |
| `feature` | string | No | Feature to review |

**Returns:** Role-specific prompt text for guiding the review

---

## Built-in Role Prompts

### Architect Role

Focuses on system architecture, design patterns, and technical decisions.

**Prompt Focus:**

- System architecture and design patterns
- Component relationships and boundaries
- Scalability and performance considerations
- Technical debt identification

### Developer Role

Focuses on implementation details and code quality.

**Prompt Focus:**

- Implementation feasibility
- Code organization and structure
- API design and contracts
- Error handling patterns

### Reviewer Role

Focuses on code review and quality assurance.

**Prompt Focus:**

- Code quality and readability
- Best practices adherence
- Test coverage requirements
- Documentation completeness

### QA Role

Focuses on testing strategy and quality assurance.

**Prompt Focus:**

- Test coverage requirements
- Edge case identification
- Integration test scenarios
- Performance testing needs

### Security Role

Focuses on security considerations and vulnerabilities.

**Prompt Focus:**

- Security vulnerabilities
- Authentication/authorization
- Data protection requirements
- Security best practices

### DevOps Role

Focuses on deployment and infrastructure.

**Prompt Focus:**

- Deployment requirements
- Infrastructure needs
- Monitoring and logging
- CI/CD considerations

---

## Usage Example

```python
# Get a prompt for the architect role
prompt = await get_prompt("sdd_review_prompt", {
    "role": "architect",
    "spec_type": "arch"
})

# Use the prompt to guide the AI assistant
response = await ai_chat(prompt)
```

---

## Custom Prompts

You can extend the prompt system by creating custom role plugins. See the [Plugin Development Guide](../development/plugins.md) for details.
