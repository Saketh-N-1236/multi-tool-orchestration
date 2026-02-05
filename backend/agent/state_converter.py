"""State converter between custom AgentState and LangGraphAgentState.

This module provides conversion functions to maintain backward compatibility
during the migration to LangGraph.
"""

from typing import List, Dict, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from agent.state import AgentState
from agent.langgraph_state import LangGraphAgentState


def normalize_message_content(content: Any) -> str:
    """Normalize message content to string format.
    
    Handles both string and list formats (e.g., Gemini content blocks).
    This is critical because Gemini/LangChain can return content as a list
    of content blocks like [{'type': 'text', 'text': '...'}] instead of a string.
    
    Args:
        content: Message content (string, list, or other format)
        
    Returns:
        Normalized string content
    """
    if content is None:
        return ""
    
    # If it's already a string, return it
    if isinstance(content, str):
        return content
    
    # If it's a list of content blocks (Gemini format)
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict):
                # Handle {'type': 'text', 'text': '...'} format
                if block.get("type") == "text" and "text" in block:
                    text_parts.append(str(block["text"]))
                # Handle {'text': '...'} format
                elif "text" in block:
                    text_parts.append(str(block["text"]))
            elif isinstance(block, str):
                text_parts.append(block)
            else:
                # Fallback: convert to string
                text_parts.append(str(block))
        return "\n".join(text_parts) if text_parts else ""
    
    # Fallback: convert to string
    return str(content)


def convert_to_langchain_messages(messages: List[Dict[str, Any]]) -> List[BaseMessage]:
    """Convert custom message format to LangChain BaseMessage types.
    
    Args:
        messages: List of message dictionaries with 'role' and 'content'
        
    Returns:
        List of LangChain BaseMessage objects
    """
    langchain_messages: List[BaseMessage] = []
    
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        
        if role == "user":
            langchain_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            langchain_messages.append(AIMessage(content=content))
        elif role == "system":
            langchain_messages.append(SystemMessage(content=content))
        elif role == "tool":
            # Tool messages need tool_call_id
            tool_call_id = msg.get("tool_call_id", "")
            langchain_messages.append(ToolMessage(content=content, tool_call_id=tool_call_id))
        else:
            # Default to human message for unknown roles
            langchain_messages.append(HumanMessage(content=content))
    
    return langchain_messages


def convert_from_langchain_messages(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    """Convert LangChain BaseMessage types to custom message format.
    
    Args:
        messages: List of LangChain BaseMessage objects
        
    Returns:
        List of message dictionaries with 'role' and 'content'
    """
    custom_messages: List[Dict[str, Any]] = []
    
    for msg in messages:
        # Normalize content to handle both string and list formats (Gemini content blocks)
        normalized_content = normalize_message_content(msg.content)
        
        msg_dict: Dict[str, Any] = {
            "content": normalized_content,  # Use normalized content
            "timestamp": getattr(msg, "timestamp", None) or None
        }
        
        if isinstance(msg, HumanMessage):
            msg_dict["role"] = "user"
        elif isinstance(msg, AIMessage):
            msg_dict["role"] = "assistant"
            # Include tool_calls if present with proper validation
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_calls_list = []
                for tc in msg.tool_calls:
                    # Handle both dict and object formats
                    if isinstance(tc, dict):
                        tool_name = tc.get("name") or tc.get("tool_name") or ""
                        tool_args = tc.get("args") or tc.get("arguments") or {}
                        tool_id = tc.get("id") or tc.get("tool_call_id") or ""
                    else:
                        # Handle object format (LangChain tool call objects)
                        tool_name = getattr(tc, "name", None) or getattr(tc, "tool_name", None) or ""
                        tool_args = getattr(tc, "args", None) or getattr(tc, "arguments", None) or {}
                        tool_id = getattr(tc, "id", None) or getattr(tc, "tool_call_id", None) or ""
                    
                    # Only add if we have a valid tool name
                    if tool_name:
                        tool_calls_list.append({
                            "name": tool_name,
                            "tool_name": tool_name,  # Add alias for consistency
                            "args": tool_args if isinstance(tool_args, dict) else {},
                            "arguments": tool_args if isinstance(tool_args, dict) else {},  # Alias
                            "id": tool_id
                        })
                
                if tool_calls_list:
                    msg_dict["tool_calls"] = tool_calls_list
        elif isinstance(msg, SystemMessage):
            msg_dict["role"] = "system"
        elif isinstance(msg, ToolMessage):
            msg_dict["role"] = "tool"
            msg_dict["tool_call_id"] = msg.tool_call_id
        else:
            # Default to user for unknown types
            msg_dict["role"] = "user"
        
        custom_messages.append(msg_dict)
    
    return custom_messages


def convert_agent_state_to_langgraph(custom_state: AgentState) -> LangGraphAgentState:
    """Convert custom AgentState to LangGraphAgentState.
    
    Args:
        custom_state: Custom AgentState from current implementation
        
    Returns:
        LangGraphAgentState compatible with LangGraph
    """
    from agent.langgraph_state import LangGraphAgentState
    
    # Convert messages
    langchain_messages = convert_to_langchain_messages(custom_state["messages"])
    
    return LangGraphAgentState(
        messages=langchain_messages,
        tool_calls=custom_state.get("tool_calls", []),
        tool_results=custom_state.get("tool_results", []),
        request_id=custom_state["request_id"],
        session_id=custom_state.get("session_id"),
        current_step=custom_state.get("current_step", 0),
        error=custom_state.get("error"),
        finished=custom_state.get("finished", False),
        prompt_version=custom_state.get("prompt_version", "v1"),
        model_name=custom_state.get("model_name", "gemini-2.5-flash"),
        start_time=custom_state.get("start_time"),
        end_time=custom_state.get("end_time")
    )


def convert_langgraph_state_to_agent(langgraph_state: LangGraphAgentState) -> AgentState:
    """Convert LangGraphAgentState to custom AgentState.
    
    Args:
        langgraph_state: LangGraphAgentState from LangGraph implementation
        
    Returns:
        AgentState compatible with current implementation
    """
    from agent.state import AgentState
    
    # Convert messages
    custom_messages = convert_from_langchain_messages(langgraph_state["messages"])
    
    # Get original LangChain messages for better tool call matching
    langchain_messages = langgraph_state["messages"]
    
    # Extract tool_calls from messages if not already in state
    # This ensures we capture all tool calls made during execution
    tool_calls = langgraph_state.get("tool_calls", [])
    
    # Always extract from original LangChain messages first (more reliable)
    # Then supplement with converted messages if needed
    from langchain_core.messages import AIMessage
    from datetime import datetime
    
    # Extract from original LangChain AIMessages (most reliable source)
    for langchain_msg in langchain_messages:
        if isinstance(langchain_msg, AIMessage) and hasattr(langchain_msg, "tool_calls") and langchain_msg.tool_calls:
            for tc in langchain_msg.tool_calls:
                # Handle both dict and object formats
                tool_name = None
                tool_id = None
                tool_args = {}
                
                if isinstance(tc, dict):
                    tool_name = tc.get("name") or tc.get("tool_name") or ""
                    tool_id = tc.get("id") or tc.get("tool_call_id") or ""
                    tool_args = tc.get("args") or tc.get("arguments") or {}
                else:
                    # Object format
                    tool_name = getattr(tc, "name", None) or getattr(tc, "tool_name", None) or ""
                    tool_id = getattr(tc, "id", None) or getattr(tc, "tool_call_id", None) or ""
                    tool_args = getattr(tc, "args", None) or getattr(tc, "arguments", None) or {}
                
                # Only add if we have a tool name or ID
                if tool_name or tool_id:
                    # Check if this tool call is already in the list (avoid duplicates)
                    existing = any(
                        (tc_item.get("id") == tool_id and tool_id) or 
                        (tc_item.get("tool_name") == tool_name and tool_name)
                        for tc_item in tool_calls
                    )
                    if not existing:
                        # Get current step from state
                        current_step = langgraph_state.get("current_step", 0)
                        tool_calls.append({
                            "tool_name": tool_name,
                            "name": tool_name,  # Alias
                            "params": tool_args if isinstance(tool_args, dict) else {},
                            "arguments": tool_args if isinstance(tool_args, dict) else {},  # Alias
                            "id": tool_id,
                            "timestamp": datetime.utcnow().isoformat(),
                            "step": current_step  # Required by frontend interface
                        })
    
    # If still no tool_calls, try extracting from converted messages as fallback
    if not tool_calls:
        for msg in custom_messages:
            if msg.get("role") == "assistant" and "tool_calls" in msg:
                for tc in msg.get("tool_calls", []):
                    # Add ALL tool calls, even duplicates/retries (important for matching)
                    tool_name = tc.get("tool_name") or tc.get("name") or ""
                    tool_id = tc.get("id") or ""
                    if tool_name or tool_id:  # Add if we have either name or ID
                        # Get current step from state
                        current_step = langgraph_state.get("current_step", 0)
                        tool_calls.append({
                            "tool_name": tool_name,
                            "name": tool_name,  # Alias
                            "params": tc.get("args") or tc.get("arguments") or {},
                            "arguments": tc.get("args") or tc.get("arguments") or {},  # Alias
                            "id": tool_id,
                            "timestamp": datetime.utcnow().isoformat(),
                            "step": current_step  # Required by frontend interface
                        })
    
    # Extract tool_results from ToolMessages
    tool_results = langgraph_state.get("tool_results", [])
    
    # Always extract from original LangChain ToolMessages first (more reliable)
    from langchain_core.messages import ToolMessage
    
    # Extract from original LangChain ToolMessages
    for langchain_msg in langchain_messages:
        if isinstance(langchain_msg, ToolMessage):
            tool_call_id = langchain_msg.tool_call_id
            content = normalize_message_content(langchain_msg.content)
            
            # Try to find corresponding tool call to get tool name
            tool_name = "unknown"
            
            # Strategy 1: Try to match from tool_calls list we just extracted
            for tc in tool_calls:
                if tc.get("id") == tool_call_id:
                    tool_name = tc.get("tool_name") or tc.get("name") or "unknown"
                    break
            
            # Strategy 2: If not found, search through original LangChain AIMessages
            if tool_name == "unknown":
                for aimsg in langchain_messages:
                    if isinstance(aimsg, AIMessage) and hasattr(aimsg, "tool_calls") and aimsg.tool_calls:
                        for tc in aimsg.tool_calls:
                            # Handle both dict and object formats
                            tc_id = None
                            tc_name = None
                            
                            if isinstance(tc, dict):
                                tc_id = tc.get("id") or tc.get("tool_call_id")
                                tc_name = tc.get("name") or tc.get("tool_name")
                            else:
                                tc_id = getattr(tc, "id", None) or getattr(tc, "tool_call_id", None)
                                tc_name = getattr(tc, "name", None) or getattr(tc, "tool_name", None)
                            
                            if tc_id == tool_call_id and tc_name:
                                tool_name = tc_name
                                break
                    
                    if tool_name != "unknown":
                        break
            
            # Add tool result (avoid duplicates)
            existing = any(tr.get("tool_call_id") == tool_call_id for tr in tool_results)
            if not existing:
                # Get current step from state
                current_step = langgraph_state.get("current_step", 0)
                tool_results.append({
                    "tool_name": tool_name,
                    "result": content,
                    "error": None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "tool_call_id": tool_call_id,
                    "step": current_step  # Required by frontend interface
                })
    
    # If still no tool_results, try extracting from converted messages as fallback
    if not tool_results:
        # Extract tool results from ToolMessages in the converted messages
        for msg in custom_messages:
            if msg.get("role") == "tool":
                tool_call_id = msg.get("tool_call_id", "")
                content = msg.get("content", "")
                
                # Try to find corresponding tool call to get tool name
                tool_name = "unknown"
                
                # Strategy 1: Try to match from tool_calls list
                for tc in tool_calls:
                    if tc.get("id") == tool_call_id:
                        tool_name = tc.get("tool_name") or tc.get("name") or "unknown"
                        break
                
                # Strategy 2: If not found, search through original LangChain AIMessages
                if tool_name == "unknown":
                    for langchain_msg in langchain_messages:
                        if isinstance(langchain_msg, AIMessage) and hasattr(langchain_msg, "tool_calls"):
                            for tc in langchain_msg.tool_calls or []:
                                # Handle both dict and object formats
                                tc_id = None
                                tc_name = None
                                
                                if isinstance(tc, dict):
                                    tc_id = tc.get("id") or tc.get("tool_call_id")
                                    tc_name = tc.get("name") or tc.get("tool_name")
                                else:
                                    tc_id = getattr(tc, "id", None) or getattr(tc, "tool_call_id", None)
                                    tc_name = getattr(tc, "name", None) or getattr(tc, "tool_name", None)
                                
                                if tc_id == tool_call_id and tc_name:
                                    tool_name = tc_name
                                    break
                        
                        if tool_name != "unknown":
                            break
                
                # Strategy 3: If still unknown, search backwards from ToolMessage
                # to find the corresponding AIMessage that called this tool
                if tool_name == "unknown":
                    for langchain_msg in langchain_messages:
                        if isinstance(langchain_msg, ToolMessage):
                            if langchain_msg.tool_call_id == tool_call_id:
                                # Search backwards through messages to find the AIMessage
                                # that contains the tool call with this ID
                                msg_index = langchain_messages.index(langchain_msg)
                                for i in range(msg_index - 1, -1, -1):
                                    prev_msg = langchain_messages[i]
                                    if isinstance(prev_msg, AIMessage) and hasattr(prev_msg, "tool_calls"):
                                        for tc in prev_msg.tool_calls or []:
                                            tc_id = None
                                            tc_name = None
                                            
                                            if isinstance(tc, dict):
                                                tc_id = tc.get("id") or tc.get("tool_call_id")
                                                tc_name = tc.get("name") or tc.get("tool_name")
                                            else:
                                                tc_id = getattr(tc, "id", None) or getattr(tc, "tool_call_id", None)
                                                tc_name = getattr(tc, "name", None) or getattr(tc, "tool_name", None)
                                            
                                            if tc_id == tool_call_id and tc_name:
                                                tool_name = tc_name
                                                break
                                        
                                        if tool_name != "unknown":
                                            break
                                
                                if tool_name != "unknown":
                                    break
                
                # Get current step from state
                current_step = langgraph_state.get("current_step", 0)
                tool_results.append({
                    "tool_name": tool_name,
                    "result": content,
                    "error": None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "step": current_step  # Required by frontend interface
                })
    
    return AgentState(
        messages=custom_messages,
        tool_calls=tool_calls,
        tool_results=tool_results,
        request_id=langgraph_state["request_id"],
        session_id=langgraph_state.get("session_id"),
        current_step=langgraph_state.get("current_step", 0),
        error=langgraph_state.get("error"),
        finished=langgraph_state.get("finished", False),
        prompt_version=langgraph_state.get("prompt_version", "v1"),
        model_name=langgraph_state.get("model_name", "gemini-2.5-flash"),
        start_time=langgraph_state.get("start_time"),
        end_time=langgraph_state.get("end_time")
    )
