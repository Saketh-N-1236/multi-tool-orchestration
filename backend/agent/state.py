"""Agent state schema."""

from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime


class AgentState(TypedDict):
    """Agent state schema for tracking conversation and tool usage.
    
    This state is passed through all agent nodes and maintains:
    - Conversation history
    - Tool calls and results
    - Request tracking
    - Error handling
    """
    
    # Conversation messages
    messages: List[Dict[str, Any]]
    
    # Tool execution tracking
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    
    # Request tracking
    request_id: str  # For correlation across system
    session_id: Optional[str]  # For multi-turn conversations
    
    # Execution state
    current_step: Optional[int]  # Current step in execution
    error: Optional[str]  # Error message if any
    finished: bool  # Whether agent has finished processing
    
    # Metadata
    prompt_version: str  # Version of prompt being used
    model_name: str  # LLM model being used
    start_time: Optional[str]  # ISO timestamp when started
    end_time: Optional[str]  # ISO timestamp when finished


def create_initial_state(
    user_message: str,
    request_id: str,
    session_id: Optional[str] = None,
    prompt_version: str = "v1",
    model_name: str = "gemini-2.5-flash"
) -> AgentState:
    """Create initial agent state.
    
    Args:
        user_message: Initial user message
        request_id: Request ID for correlation
        session_id: Optional session ID for multi-turn conversations
        prompt_version: Prompt version to use
        model_name: LLM model name
        
    Returns:
        Initialized agent state
    """
    return AgentState(
        messages=[
            {
                "role": "user",
                "content": user_message,
                "timestamp": datetime.utcnow().isoformat()
            }
        ],
        tool_calls=[],
        tool_results=[],
        request_id=request_id,
        session_id=session_id,
        current_step=0,
        error=None,
        finished=False,
        prompt_version=prompt_version,
        model_name=model_name,
        start_time=datetime.utcnow().isoformat(),
        end_time=None
    )


def add_message(state: AgentState, role: str, content: str) -> None:
    """Add a message to the state.
    
    Args:
        state: Agent state to update
        role: Message role (user, assistant, system)
        content: Message content
    """
    state["messages"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat()
    })


def add_tool_call(state: AgentState, tool_name: str, params: Dict[str, Any]) -> None:
    """Add a tool call to the state.
    
    Args:
        state: Agent state to update
        tool_name: Name of the tool called
        params: Tool parameters
    """
    state["tool_calls"].append({
        "tool_name": tool_name,
        "params": params,
        "timestamp": datetime.utcnow().isoformat(),
        "step": state["current_step"]
    })


def add_tool_result(
    state: AgentState,
    tool_name: str,
    result: Any,
    error: Optional[str] = None
) -> None:
    """Add a tool result to the state.
    
    Args:
        state: Agent state to update
        tool_name: Name of the tool that was called
        result: Tool execution result
        error: Error message if any
    """
    state["tool_results"].append({
        "tool_name": tool_name,
        "result": result,
        "error": error,
        "timestamp": datetime.utcnow().isoformat(),
        "step": state["current_step"]
    })


def finish_state(state: AgentState, error: Optional[str] = None) -> None:
    """Mark state as finished.
    
    Args:
        state: Agent state to update
        error: Optional error message
    """
    state["finished"] = True
    state["end_time"] = datetime.utcnow().isoformat()
    if error:
        state["error"] = error
