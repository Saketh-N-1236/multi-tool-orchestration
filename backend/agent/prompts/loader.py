"""Prompt loader for versioned prompts."""

from pathlib import Path
from typing import Dict, Any, Optional


def load_prompt(
    filename: str,
    **kwargs: Any
) -> str:
    """Load a prompt file and substitute variables.
    
    Args:
        filename: Name of the prompt file (e.g., "system_v1.txt")
        **kwargs: Variables to substitute in the prompt
        
    Returns:
        Loaded prompt with variables substituted
        
    Raises:
        FileNotFoundError: If prompt file doesn't exist
        ValueError: If required variables are missing
    """
    prompts_dir = Path(__file__).parent
    prompt_path = prompts_dir / filename
    
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    
    with open(prompt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Manually replace known variables using string replacement
    # This avoids issues with JSON examples in prompts that contain {key: value}
    result = content
    for key, value in kwargs.items():
        placeholder = f"{{{key}}}"
        if placeholder in result:
            result = result.replace(placeholder, str(value))
    
    # Check if any required placeholders remain (would indicate missing variables)
    import re
    remaining_placeholders = re.findall(r'\{(\w+)\}', result)
    if remaining_placeholders:
        # Filter out placeholders that are in kwargs (they should have been replaced)
        missing = [p for p in remaining_placeholders if p not in kwargs]
        if missing:
            raise ValueError(f"Missing required variable in prompt: '{missing[0]}'")
    
    return result


def load_tool_policy() -> str:
    """Load tool policy prompt.
    
    Returns:
        Tool policy content
    """
    return load_prompt("tool_policy.txt")


def load_system_prompt(
    tool_list: str,
    tool_policy: Optional[str] = None
) -> str:
    """Load system prompt with tool list and policy.
    
    Args:
        tool_list: Formatted list of available tools
        tool_policy: Tool policy content (loaded automatically if not provided)
        
    Returns:
        Complete system prompt
    """
    if tool_policy is None:
        tool_policy = load_tool_policy()
    
    return load_prompt("system_v1.txt", tool_list=tool_list, tool_policy=tool_policy)
