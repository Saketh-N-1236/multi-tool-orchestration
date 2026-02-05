# Prompt Versioning System

This directory contains versioned prompts for the agent system.

## Current Prompts

### System Prompt v1
- **File:** `system_v1.txt`
- **Version:** 1.0.0
- **Description:** Main system prompt for the agent
- **Variables:**
  - `{tool_list}` - List of available tools with descriptions
  - `{tool_policy}` - Tool usage policy content

### Tool Policy
- **File:** `tool_policy.txt`
- **Version:** 1.0.0
- **Description:** Detailed tool usage guidelines and policies
- **Usage:** Included in system prompt via `{tool_policy}` variable

## Versioning Strategy

1. **Major Version Changes:**
   - Significant changes to agent behavior
   - New prompt structure
   - Breaking changes in instructions

2. **Minor Version Changes:**
   - Updates to guidelines
   - New tool instructions
   - Refinements to existing instructions

3. **Patch Version Changes:**
   - Typo fixes
   - Minor clarifications
   - Formatting improvements

## Loading Prompts

```python
from agent.prompts.loader import load_prompt

# Load system prompt
system_prompt = load_prompt("system_v1.txt", tool_list="...", tool_policy="...")

# Load tool policy
tool_policy = load_prompt("tool_policy.txt")
```

## Future Versions

When creating new versions:
1. Create new file: `system_v2.txt`
2. Update version number
3. Document changes in this README
4. Update agent code to use new version
5. Log version in MLflow for tracking

## Best Practices

- Keep prompts focused and clear
- Use placeholders for dynamic content
- Test prompts with various scenarios
- Track prompt performance in MLflow
- Version control all prompt changes
