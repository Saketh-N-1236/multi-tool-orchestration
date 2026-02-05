"""LangGraph-based agent implementation.

This module provides a LangGraph-based agent that can be used
as a drop-in replacement for the custom AgentGraph.
"""

import logging
from typing import Optional
import asyncio

from agent.langgraph_state import LangGraphAgentState, create_langgraph_initial_state
from agent.langgraph_builder import LangGraphAgentBuilder
from agent.mcp_sdk_client import MCPSDKClient
from agent.tool_converter import convert_mcp_tools_to_langchain
from agent.state_converter import convert_langgraph_state_to_agent
from agent.prompts.loader import load_system_prompt
from config.settings import get_settings

logger = logging.getLogger(__name__)


class LangGraphAgent:
    """LangGraph-based agent implementation."""
    
    def __init__(self):
        """Initialize LangGraph agent."""
        self.settings = get_settings()
        self.mcp_client: Optional[MCPSDKClient] = None
        self.graph = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the agent with tools and graph."""
        if self._initialized:
            return
        
        try:
            # Initialize MCP SDK client
            self.mcp_client = MCPSDKClient()
            await self.mcp_client.initialize()
            
            # Discover tools from all MCP servers
            try:
                mcp_tools = await self.mcp_client.discover_all_tools()
            except RuntimeError as e:
                # Re-raise with more context
                error_msg = (
                    f"Agent initialization failed: {str(e)}. "
                    f"Please start the MCP servers before using the agent. "
                    f"Run: python -m mcp_servers.catalog_server.server (and similar for other servers)"
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg) from e
            
            # Convert MCP tools to LangChain StructuredTools
            langchain_tools = convert_mcp_tools_to_langchain(
                mcp_tools,
                self.mcp_client.call_tool
            )
            
            if not langchain_tools:
                raise RuntimeError(
                    "No tools available after conversion. "
                    "This may indicate a problem with tool discovery or conversion."
                )
            
            # Load system prompt
            # Format tool list for prompt (for compatibility)
            tool_list = "\n".join([
                f"- {tool.name}: {tool.description}"
                for tool in langchain_tools
            ])
            system_prompt = load_system_prompt(tool_list=tool_list or "No tools available.")
            
            # Build LangGraph
            builder = LangGraphAgentBuilder(tools=langchain_tools)
            self.graph = builder.build()
            
            self._initialized = True
            logger.info(
                f"LangGraph agent initialized successfully with {len(langchain_tools)} tools"
            )
        
        except Exception as e:
            logger.error(f"Failed to initialize LangGraph agent: {e}", exc_info=True)
            raise
    
    async def invoke(
        self,
        user_message: str,
        request_id: str,
        session_id: Optional[str] = None,
        max_iterations: int = 10,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> dict:
        """Invoke the agent with a user message.
        
        Args:
            user_message: User message/query
            request_id: Request ID for correlation
            session_id: Optional session ID
            max_iterations: Maximum iterations (for compatibility, LangGraph handles this internally)
            temperature: Temperature override (not used in LangGraph version yet)
            max_tokens: Max tokens override (not used in LangGraph version yet)
            
        Returns:
            Agent state (converted to custom format for compatibility)
        """
        if not self._initialized:
            await self.initialize()
        
        # Load system prompt
        # Get tools from the graph builder (they're already set during initialization)
        from agent.langgraph_nodes import get_available_tools
        tools = get_available_tools()
        tool_list = "\n".join([
            f"- {tool.name}: {tool.description}"
            for tool in tools
        ]) if tools else "No tools available."
        system_prompt = load_system_prompt(tool_list=tool_list)
        
        # Create initial state
        initial_state = create_langgraph_initial_state(
            user_message=user_message,
            request_id=request_id,
            session_id=session_id,
            system_prompt=system_prompt
        )
        
        # Invoke graph
        try:
            final_state = await self.graph.ainvoke(initial_state)
            
            # Convert LangGraph state to custom format for compatibility
            custom_state = convert_langgraph_state_to_agent(final_state)
            
            return custom_state
        
        except Exception as e:
            logger.error(f"Error in LangGraph agent invocation: {e}", exc_info=True)
            raise
    
    async def close(self) -> None:
        """Close the agent and clean up resources."""
        if self.mcp_client:
            await self.mcp_client.close()
        self._initialized = False
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Helper will be imported when needed
