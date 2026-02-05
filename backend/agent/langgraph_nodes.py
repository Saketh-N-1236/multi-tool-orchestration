"""LangGraph nodes for agent execution.

This module defines the nodes used in the LangGraph StateGraph:
- call_model: Agent node that calls the LLM
- should_continue: Conditional router to determine next step
"""

from typing import Dict, Any, Literal
import logging

try:
    from langchain_core.messages import BaseMessage, AIMessage
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.tools import StructuredTool
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    ChatGoogleGenerativeAI = None
    StructuredTool = None

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
    
    This function checks if the last message from the LLM contains tool calls.
    If it does, route to "tools" node. Otherwise, route to "end".
    
    Args:
        state: Current agent state
        
    Returns:
        "tools" if tool calls are present, "end" otherwise
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    # Check if last message is an AIMessage with tool_calls
    if isinstance(last_message, AIMessage):
        # Check if the message has tool_calls
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            logger.debug(
                f"Routing to tools node: {len(last_message.tool_calls)} tool calls detected"
            )
            return "tools"
    
    # No tool calls, end the graph
    logger.debug("Routing to end: No tool calls detected")
    return "end"
