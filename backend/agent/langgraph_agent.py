"""LangGraph-based agent implementation.

This module provides a LangGraph-based agent that can be used
as a drop-in replacement for the custom AgentGraph.
"""

import logging
from typing import Optional, AsyncIterator, Dict, Any
import asyncio
from datetime import datetime

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
    
    async def stream_invoke(
        self,
        user_message: str,
        request_id: str,
        session_id: Optional[str] = None,
        max_iterations: int = 10,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream agent execution with progress updates.
        
        Args:
            user_message: User message/query
            request_id: Request ID for correlation
            session_id: Optional session ID
            max_iterations: Maximum iterations
            temperature: Temperature override
            max_tokens: Max tokens override
            
        Yields:
            Dict with 'stage', 'data', 'timestamp' keys containing execution progress
        """
        if not self._initialized:
            await self.initialize()
        
        # Load system prompt
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
        
        # Verify graph is initialized
        if self.graph is None:
            logger.error("Graph is None - agent not properly initialized")
            yield {
                "stage": "error",
                "data": {
                    "error": "Agent graph not initialized",
                    "message": "The agent graph was not properly initialized. Please check the logs."
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            return
        
        # Send initializing stage
        yield {
            "stage": "initializing",
            "data": {"message": "Initializing agent..."},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            # Stream graph execution
            iteration_count = 0
            # Start with full initial state to ensure all fields are present
            # TypedDict can be converted to dict
            last_state = dict(initial_state)
            events_received = 0
            
            logger.info(f"Starting stream_invoke for request_id: {request_id}, message: {user_message[:50]}...")
            logger.debug(f"Initial state keys: {list(initial_state.keys())}, messages count: {len(initial_state.get('messages', []))}")
            
            async for event in self.graph.astream(initial_state):
                events_received += 1
                logger.debug(f"Received event #{events_received}: {list(event.keys())}")
                
                # Extract node name and state from event
                for node_name, state_update in event.items():
                    iteration_count += 1
                    logger.debug(f"Processing node: {node_name}, iteration: {iteration_count}")
                    
                    # Merge partial state updates with last_state
                    # LangGraph astream yields partial updates, so we need to merge them
                    if isinstance(state_update, dict):
                        # Merge all fields, handling messages specially
                        for key, value in state_update.items():
                            if key == "messages":
                                # Messages are already merged by the add_messages reducer
                                last_state[key] = value
                            else:
                                last_state[key] = value
                    else:
                        # If state_update is not a dict, convert it
                        # TypedDict instances can be treated as dicts
                        try:
                            state_dict = dict(state_update) if hasattr(state_update, "keys") else state_update
                            for key, value in state_dict.items():
                                if key == "messages":
                                    last_state[key] = value
                                else:
                                    last_state[key] = value
                        except (TypeError, AttributeError):
                            # Fallback: if we can't convert, log and skip
                            logger.warning(f"Could not merge state update from node {node_name}: {type(state_update)}")
                            continue
                    
                    # Extract and yield stage info
                    stage_info = self._extract_stage_info(node_name, last_state, iteration_count)
                    if stage_info:
                        logger.debug(f"Yielding stage: {stage_info.get('stage')}")
                        yield stage_info
                        # Small delay to make stages visible (helps with fast execution)
                        await asyncio.sleep(0.05)
            
            logger.info(f"Stream completed. Total events: {events_received}, iterations: {iteration_count}, last_state keys: {list(last_state.keys()) if isinstance(last_state, dict) else 'N/A'}")
            
            # If no events were received, the graph might not have executed
            if events_received == 0:
                logger.warning("No events received from graph.astream - graph may not have executed")
                yield {
                    "stage": "error",
                    "data": {
                        "error": "No execution events received",
                        "message": "Agent execution did not produce any events. The graph may not have started."
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
                return
            
            # Convert final state - ensure all required fields are present
            try:
                # Ensure final_state is a dict with all required fields
                if not isinstance(last_state, dict):
                    # Try to convert to dict
                    try:
                        final_state = dict(last_state)
                    except (TypeError, ValueError):
                        # If conversion fails, create a new dict from initial_state
                        final_state = dict(initial_state)
                        logger.warning("Could not convert last_state to dict, using initial_state")
                else:
                    final_state = last_state.copy()
                
                # Add missing required fields from initial_state
                if "request_id" not in final_state or not final_state.get("request_id"):
                    final_state["request_id"] = request_id
                if "session_id" not in final_state:
                    final_state["session_id"] = session_id
                if "prompt_version" not in final_state:
                    final_state["prompt_version"] = initial_state.get("prompt_version", "v1")
                if "model_name" not in final_state:
                    final_state["model_name"] = initial_state.get("model_name", "gemini-2.5-flash")
                if "current_step" not in final_state:
                    final_state["current_step"] = iteration_count
                if "finished" not in final_state:
                    final_state["finished"] = True
                if "error" not in final_state:
                    final_state["error"] = None
                if "tool_calls" not in final_state:
                    final_state["tool_calls"] = []
                if "tool_results" not in final_state:
                    final_state["tool_results"] = []
                
                logger.debug(f"Converting final_state with {len(final_state.get('messages', []))} messages")
                
                # Convert to custom state
                custom_state = convert_langgraph_state_to_agent(final_state)
                
                # Extract final assistant message
                assistant_messages = [m for m in reversed(custom_state.get("messages", [])) if m.get("role") == "assistant"]
                final_response_text = ""
                if assistant_messages:
                    final_response_text = assistant_messages[0].get("content", "")
                    logger.info(f"Extracted final response: {len(final_response_text)} characters")
                else:
                    logger.warning("No assistant messages found in custom_state")
                
                # Always yield completed stage, even if response is empty
                completed_data = {
                    "message": "Response ready",
                    "iterations": iteration_count,
                    "response": final_response_text,
                    "tool_calls": custom_state.get("tool_calls", []),
                    "tool_results": custom_state.get("tool_results", []),
                    "session_id": custom_state.get("session_id")
                }
                
                logger.info(f"Yielding completed stage with response length: {len(final_response_text)}, tool_calls: {len(completed_data['tool_calls'])}, tool_results: {len(completed_data['tool_results'])}")
                
                yield {
                    "stage": "completed",
                    "data": completed_data,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"Failed to extract final state: {e}", exc_info=True)
                # Try to extract response directly from messages as fallback
                try:
                    # Get messages from last_state
                    messages = []
                    if isinstance(last_state, dict):
                        messages = last_state.get("messages", [])
                    else:
                        # Try to get messages from object
                        messages = getattr(last_state, "messages", [])
                    
                    final_response_text = ""
                    
                    if messages:
                        # Get last AIMessage that doesn't have tool_calls
                        for msg in reversed(messages):
                            # Check if it's an AIMessage without tool calls
                            if hasattr(msg, "content"):
                                content = msg.content
                                # Check if it has tool_calls
                                has_tool_calls = hasattr(msg, "tool_calls") and msg.tool_calls
                                if content and not has_tool_calls:
                                    # Normalize content
                                    if isinstance(content, str):
                                        final_response_text = content
                                    elif isinstance(content, list):
                                        # Handle Gemini content blocks
                                        text_parts = []
                                        for block in content:
                                            if isinstance(block, dict) and block.get("type") == "text":
                                                text_parts.append(block.get("text", ""))
                                            elif isinstance(block, str):
                                                text_parts.append(block)
                                        final_response_text = "\n".join(text_parts)
                                    else:
                                        final_response_text = str(content)
                                    break
                            # Also check if it's a dict format message
                            elif isinstance(msg, dict) and msg.get("role") == "assistant":
                                content = msg.get("content", "")
                                if content and not msg.get("tool_calls"):
                                    final_response_text = str(content)
                                    break
                    
                    yield {
                        "stage": "completed",
                        "data": {
                            "message": "Response ready",
                            "iterations": iteration_count,
                            "response": final_response_text
                        },
                        "timestamp": datetime.utcnow().isoformat()
                    }
                except Exception as e2:
                    logger.error(f"Failed to extract response from messages: {e2}", exc_info=True)
                    yield {
                        "stage": "completed",
                        "data": {"message": "Response ready", "iterations": iteration_count},
                        "timestamp": datetime.utcnow().isoformat()
                    }
        
        except Exception as e:
            logger.error(f"Error in LangGraph agent streaming: {e}", exc_info=True)
            yield {
                "stage": "error",
                "data": {"error": str(e), "message": f"Error occurred: {str(e)}"},
                "timestamp": datetime.utcnow().isoformat()
            }
            raise
    
    def _extract_stage_info(
        self, 
        node_name: str, 
        state: LangGraphAgentState,
        iteration: int
    ) -> Optional[Dict[str, Any]]:
        """Extract stage information from node execution.
        
        Args:
            node_name: Name of the node being executed
            state: Current agent state
            iteration: Current iteration number
            
        Returns:
            Stage info dict or None if stage should be skipped
        """
        timestamp = datetime.utcnow().isoformat()
        
        # Ensure state is a dict for safe access
        if not isinstance(state, dict):
            try:
                state = dict(state)
            except (TypeError, ValueError):
                # If we can't convert, return None
                return None
        
        if node_name == "agent":
            messages = state.get("messages", [])
            last_message = messages[-1] if messages else None
            
            # Import AIMessage here to avoid circular imports
            try:
                from langchain_core.messages import AIMessage
            except ImportError:
                return None
            
            if isinstance(last_message, AIMessage):
                # Check if LLM has tool calls
                if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                    tool_names = []
                    for tc in last_message.tool_calls:
                        # Handle both dict and object formats
                        if isinstance(tc, dict):
                            tool_name = tc.get("name") or tc.get("tool_name") or "unknown"
                        else:
                            tool_name = getattr(tc, "name", None) or getattr(tc, "tool_name", None) or "unknown"
                        if tool_name not in tool_names:
                            tool_names.append(tool_name)
                    
                    return {
                        "stage": "tool_executing",
                        "data": {
                            "tools": tool_names,
                            "tools_count": len(tool_names),
                            "message": f"Executing {len(tool_names)} tool(s): {', '.join(tool_names)}",
                            "iteration": iteration
                        },
                        "timestamp": timestamp
                    }
                else:
                    # LLM is thinking (no tool calls)
                    return {
                        "stage": "agent_thinking",
                        "data": {
                            "message": "Processing with LLM...",
                            "iteration": iteration
                        },
                        "timestamp": timestamp
                    }
        
        elif node_name == "tools":
            # Tool execution completed
            # Extract tool calls from messages (LangGraph stores them in AIMessages, not state)
            messages = state.get("messages", []) if isinstance(state, dict) else getattr(state, "messages", [])
            
            # Count tool calls from AIMessages
            tool_calls_count = 0
            tool_names = []
            
            try:
                from langchain_core.messages import AIMessage, ToolMessage
            except ImportError:
                return None
            
            # Extract tool names from AIMessages that have tool_calls
            for msg in messages:
                if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls_count += 1
                        # Extract tool name
                        if isinstance(tc, dict):
                            tool_name = tc.get("name") or tc.get("tool_name") or "unknown"
                        else:
                            tool_name = getattr(tc, "name", None) or getattr(tc, "tool_name", None) or "unknown"
                        if tool_name not in tool_names:
                            tool_names.append(tool_name)
            
            # Also check ToolMessages to count executed tools
            tool_results_count = sum(1 for msg in messages if isinstance(msg, ToolMessage))
            
            # Use the higher count (tool_calls or tool_results)
            actual_count = max(tool_calls_count, tool_results_count)
            
            return {
                "stage": "tool_completed",
                "data": {
                    "tools_count": actual_count,
                    "tools": tool_names if tool_names else (["tools"] if actual_count > 0 else []),
                    "message": f"Completed {actual_count} tool execution(s)" if actual_count > 0 else "No tools executed",
                    "iteration": iteration
                },
                "timestamp": timestamp
            }
        
        # Skip other internal nodes
        return None
    
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
