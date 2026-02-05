"""LangGraph-compatible agent state schema.

This module defines the state schema for use with LangGraph's StateGraph.
It uses LangChain BaseMessage types and the add_messages reducer pattern.
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from datetime import datetime
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph.message import add_messages


class LangGraphAgentState(TypedDict):
    """LangGraph-compatible agent state schema.
    
    This state is used with LangGraph's StateGraph and follows LangGraph patterns:
    - messages: Uses LangChain BaseMessage types with add_messages reducer
    - Additional fields for tracking and compatibility
    """
    
    # Conversation messages (LangGraph pattern with reducer)
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Tool execution tracking (for backward compatibility and logging)
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


def create_langgraph_initial_state(
    user_message: str,
    request_id: str,
    session_id: Optional[str] = None,
    system_prompt: Optional[str] = None,
    prompt_version: str = "v1",
    model_name: str = "gemini-2.5-flash"
) -> LangGraphAgentState:
    """Create initial LangGraph agent state.
    
    Args:
        user_message: Initial user message
        request_id: Request ID for correlation
        session_id: Optional session ID for multi-turn conversations
        system_prompt: Optional system prompt to include
        prompt_version: Prompt version to use
        model_name: LLM model name
        
    Returns:
        Initialized LangGraph agent state
    """
    messages: List[BaseMessage] = []
    
    # Add system prompt if provided
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    
    # Add user message
    messages.append(HumanMessage(content=user_message))
    
    return LangGraphAgentState(
        messages=messages,
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


def add_tool_call_to_state(
    state: LangGraphAgentState,
    tool_name: str,
    params: Dict[str, Any]
) -> None:
    """Add a tool call to the state (for tracking/logging).
    
    Args:
        state: Agent state to update
        tool_name: Name of the tool called
        params: Tool parameters
    """
    state["tool_calls"].append({
        "tool_name": tool_name,
        "params": params,
        "timestamp": datetime.utcnow().isoformat(),
        "step": state.get("current_step", 0)
    })


def add_tool_result_to_state(
    state: LangGraphAgentState,
    tool_name: str,
    result: Any,
    error: Optional[str] = None
) -> None:
    """Add a tool result to the state (for tracking/logging).
    
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
        "step": state.get("current_step", 0)
    })


def finish_langgraph_state(
    state: LangGraphAgentState,
    error: Optional[str] = None
) -> None:
    """Mark LangGraph state as finished.
    
    Args:
        state: Agent state to update
        error: Optional error message
    """
    state["finished"] = True
    state["end_time"] = datetime.utcnow().isoformat()
    if error:
        state["error"] = error
