"""LangGraph nodes for agent execution.

This module defines the nodes used in the LangGraph StateGraph:
- call_model: Agent node that calls the LLM
- should_continue: Conditional router to determine next step
"""

from typing import Dict, Any, Literal
import logging

try:
    from langchain_core.messages import BaseMessage, AIMessage, ToolMessage, HumanMessage
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.tools import StructuredTool
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    ChatGoogleGenerativeAI = None
    StructuredTool = None
    ToolMessage = None
    HumanMessage = None

from agent.langgraph_state import LangGraphAgentState
from config.settings import get_settings
from llm.factory import LLMFactory

logger = logging.getLogger(__name__)


# Global cache for LLM and tools (initialized once)
_langchain_llm = None
_available_tools: list[StructuredTool] = []


def get_langchain_llm():
    """Get or create LangChain LLM instance.
    
    Returns:
        LangChain ChatModel instance
    """
    global _langchain_llm
    
    if _langchain_llm is None:
        if not LANGCHAIN_AVAILABLE:
            raise ImportError(
                "LangChain is required. Install with: pip install langchain langchain-google-genai"
            )
        
        settings = get_settings()
        
        # Create LangChain LLM based on provider
        if settings.llm_provider == "gemini":
            if not settings.gemini_api_key:
                raise ValueError("Gemini API key is required")
            _langchain_llm = ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                google_api_key=settings.gemini_api_key,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens
            )
        else:
            # For other providers, we'd need to use their LangChain integrations
            # For now, fall back to Gemini or raise an error
            raise ValueError(
                f"LangChain integration not yet implemented for provider: {settings.llm_provider}. "
                f"Currently only 'gemini' is supported with LangGraph."
            )
    
    return _langchain_llm


def set_available_tools(tools: list[StructuredTool]) -> None:
    """Set the available tools for the agent.
    
    Args:
        tools: List of LangChain StructuredTool objects
    """
    global _available_tools
    _available_tools = tools


def get_available_tools() -> list[StructuredTool]:
    """Get the available tools.
    
    Returns:
        List of LangChain StructuredTool objects
    """
    return _available_tools


async def call_model(state: LangGraphAgentState) -> Dict[str, Any]:
    """Agent node: Call LLM with current messages and tools.
    
    This node:
    1. Gets the current messages from state
    2. Binds tools to the LLM
    3. Calls the LLM
    4. Returns updated state with the LLM response
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with LLM response message
    """
    try:
        # Get messages from state
        messages = state["messages"]
        
        # Log message history for debugging
        logger.debug(f"call_model: Processing {len(messages)} messages")
        for i, msg in enumerate(messages):
            msg_type = type(msg).__name__
            if isinstance(msg, AIMessage):
                has_tc = bool(getattr(msg, 'tool_calls', None))
                content_len = len(str(getattr(msg, 'content', '')))
                logger.debug(f"  Message {i}: {msg_type}, tool_calls={has_tc}, content_len={content_len}")
            elif isinstance(msg, ToolMessage):
                logger.debug(f"  Message {i}: {msg_type}, tool_call_id={getattr(msg, 'tool_call_id', 'N/A')}")
            else:
                logger.debug(f"  Message {i}: {msg_type}")
        
        # CRITICAL FIX: Check if we have tool results but the last message is not asking for a response
        # If tool results are present, add an explicit instruction to generate a final answer
        tool_messages = [msg for msg in messages if isinstance(msg, ToolMessage)]
        last_message_is_tool = messages and isinstance(messages[-1], ToolMessage)
        
        # Check if last message is already an instruction (avoid duplicates)
        last_message_is_instruction = False
        if messages and HumanMessage is not None:
            try:
                last_message_is_instruction = (
                    isinstance(messages[-1], HumanMessage) and 
                    "Based on the tool results" in str(messages[-1].content)
                )
            except Exception:
                pass  # If HumanMessage is None or check fails, assume not an instruction
        
        # If we have tool results and the last message is a ToolMessage (and not already an instruction), add explicit instruction
        if tool_messages and last_message_is_tool and not last_message_is_instruction and HumanMessage is not None:
            # Add explicit instruction to generate final answer after tool execution
            instruction_message = HumanMessage(
                content="Based on the tool results above, please provide a clear and complete answer to the user's question. If you need to use more tools, use them. Otherwise, provide the final answer now."
            )
            messages = list(messages) + [instruction_message]
            logger.info(f"Added explicit instruction message after {len(tool_messages)} tool results to force response generation")
        
        # Get LLM
        llm = get_langchain_llm()
        
        # Get available tools
        tools = get_available_tools()
        
        # Bind tools to LLM if tools are available
        if tools:
            llm_with_tools = llm.bind_tools(tools)
        else:
            llm_with_tools = llm
            logger.warning("No tools available for LLM binding")
        
        # Call LLM
        response = await llm_with_tools.ainvoke(messages)
        
        # Debug: Log response details
        has_content = bool(getattr(response, 'content', None))
        has_tool_calls = bool(getattr(response, 'tool_calls', None))
        content_preview = str(getattr(response, 'content', ''))[:100] if has_content else "No content"
        
        # CRITICAL: Check if we have tool results but no content
        tool_messages = [msg for msg in messages if isinstance(msg, ToolMessage)]
        if tool_messages and not has_content and not has_tool_calls:
            logger.error(
                f"CRITICAL: Agent received {len(tool_messages)} tool results but generated "
                f"no content and no tool_calls. This will cause the fallback response to be used."
            )
        elif tool_messages and not has_content and has_tool_calls:
            logger.warning(
                f"Agent received {len(tool_messages)} tool results and generated new tool_calls "
                f"but no content. This may indicate the agent needs more iterations."
            )
        elif tool_messages and has_content:
            logger.info(
                f"Agent received {len(tool_messages)} tool results and generated final response "
                f"({len(str(response.content))} chars)"
            )
        
        logger.debug(f"LLM response: has_content={has_content}, has_tool_calls={has_tool_calls}, content_preview={content_preview}")
        
        # Update state with response
        # The response is an AIMessage (possibly with tool_calls)
        return {
            "messages": [response]
        }
    
    except Exception as e:
        logger.error(f"Error in call_model node: {e}", exc_info=True)
        # Create error message
        error_message = AIMessage(
            content=f"I encountered an error: {str(e)}"
        )
        return {
            "messages": [error_message],
            "error": str(e)
        }


def should_continue(state: LangGraphAgentState) -> Literal["tools", "end"]:
    """Conditional router: Determine next step based on last message.
    
    This function checks if the last AIMessage from the LLM contains tool calls.
    If it does, route to "tools" node. Otherwise, route to "end".
    
    CRITICAL: Only end if there's actual content (final response), not just no tool_calls.
    
    Args:
        state: Current agent state
        
    Returns:
        "tools" if tool calls are present, "end" otherwise
    """
    messages = state["messages"]
    
    # Find the last AIMessage (not ToolMessage or other message types)
    # After tool execution, ToolMessages are added, so we need to find the last AIMessage
    last_ai_message = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            last_ai_message = msg
            break
    
    # If no AIMessage found, end the graph (shouldn't happen, but safety check)
    if not last_ai_message:
        logger.warning("No AIMessage found in state, ending graph")
        return "end"
    
    # Check if the last AIMessage has tool_calls
    has_tool_calls = hasattr(last_ai_message, "tool_calls") and last_ai_message.tool_calls
    
    # CRITICAL FIX: Check if there's actual content
    # If there are tool_calls, we need to execute them (route to tools)
    if has_tool_calls:
        logger.debug(
            f"Routing to tools node: {len(last_ai_message.tool_calls)} tool calls detected"
        )
        return "tools"
    
    # No tool calls - check if we have content (final response)
    content = getattr(last_ai_message, 'content', None)
    has_content = bool(content) and str(content).strip()
    
    if has_content:
        # We have content and no tool calls - this is a final response
        logger.debug("Routing to end: Final response with content detected")
        return "end"
    
    # No tool calls AND no content - this shouldn't happen, but if it does,
    # we need to check if we have tool results that need processing
    tool_messages = [msg for msg in messages if isinstance(msg, ToolMessage)]
    if tool_messages:
        # We have tool results but no final response - this is a problem
        logger.error(
            f"Agent did not generate content after {len(tool_messages)} tool results. "
            f"This is a problem - the agent should always provide a final answer. "
            f"Ending graph, but this will trigger fallback response."
        )
        return "end"
    
    # No tool calls, no content, no tool results - end the graph
    logger.debug("Routing to end: No tool calls, no content, no tool results")
    return "end"
