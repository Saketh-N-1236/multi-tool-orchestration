"""LangGraph StateGraph builder.

This module builds the LangGraph StateGraph with nodes and edges
for agent execution with tool orchestration.
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path

try:
    from langgraph.graph import StateGraph, END
    from langgraph.prebuilt import ToolNode
    from langchain_core.tools import StructuredTool
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    ToolNode = None

from agent.langgraph_state import LangGraphAgentState
from agent.langgraph_nodes import call_model, should_continue, set_available_tools
from config.settings import get_settings

logger = logging.getLogger(__name__)


class LangGraphAgentBuilder:
    """Builder for LangGraph agent graph."""
    
    def __init__(self, tools: Optional[list[StructuredTool]] = None):
        """Initialize the builder.
        
        Args:
            tools: Optional list of LangChain StructuredTool objects
        """
        if not LANGGRAPH_AVAILABLE:
            raise ImportError(
                "LangGraph is required. Install with: pip install langgraph"
            )
        
        self.tools = tools or []
        self._graph = None
    
    def build(self) -> StateGraph:
        """Build the LangGraph StateGraph.
        
        Returns:
            Compiled StateGraph ready for execution
        """
        # Set available tools for the agent node
        set_available_tools(self.tools)
        
        # Create the graph
        workflow = StateGraph(LangGraphAgentState)
        
        # Add agent node
        workflow.add_node("agent", call_model)
        
        # Add tool node (LangGraph's built-in ToolNode)
        if self.tools:
            tool_node = ToolNode(self.tools)
            workflow.add_node("tools", tool_node)
        else:
            logger.warning("No tools provided - tool node will not be added")
            # Create a no-op tool node
            async def noop_tools(state: LangGraphAgentState) -> Dict[str, Any]:
                return {}
            workflow.add_node("tools", noop_tools)
        
        # Set entry point
        workflow.set_entry_point("agent")
        
        # Add conditional edges from agent
        workflow.add_conditional_edges(
            "agent",
            should_continue,
            {
                "tools": "tools",
                "end": END
            }
        )
        
        # Add edge from tools back to agent
        workflow.add_edge("tools", "agent")
        
        # Create checkpointer for conversation history persistence
        checkpointer = self._create_checkpointer()
        
        # Compile the graph with checkpointer
        if checkpointer:
            self._graph = workflow.compile(checkpointer=checkpointer)
            logger.info(
                f"Built LangGraph with {len(self.tools)} tools and checkpointing enabled. "
                f"Graph structure: agent -> [tools/end] -> agent (loop)"
            )
        else:
            self._graph = workflow.compile()
            logger.warning(
                f"Built LangGraph with {len(self.tools)} tools but checkpointing is disabled. "
                f"Conversation history will not persist across requests."
            )
        
        # Optionally visualize the graph (non-blocking, doesn't affect execution)
        self._visualize_graph_if_enabled()
        
        return self._graph
    
    def get_graph(self) -> Optional[StateGraph]:
        """Get the compiled graph.
        
        Returns:
            Compiled StateGraph or None if not built yet
        """
        return self._graph
    
    def _visualize_graph_if_enabled(self) -> None:
        """Visualize the graph using IPython.display if enabled and available.
        
        This is a non-blocking operation that doesn't affect graph execution.
        """
        if not self._graph:
            return
        
        try:
            from config.settings import get_settings
            settings = get_settings()
            
            if not settings.enable_graph_visualization:
                return
            
            # Try to import IPython display
            try:
                from IPython.display import Image, display
                IPYTHON_AVAILABLE = True
            except ImportError:
                IPYTHON_AVAILABLE = False
                logger.debug("IPython not available - graph visualization skipped")
                return
            
            # Get the underlying graph from compiled graph
            try:
                # LangGraph compiled graphs have get_graph() method
                underlying_graph = self._graph.get_graph()
                
                # Check if the graph has draw_mermaid_png method
                if hasattr(underlying_graph, 'draw_mermaid_png'):
                    png_bytes = underlying_graph.draw_mermaid_png()
                    if png_bytes:
                        display(Image(png_bytes))
                        logger.info("Graph visualization displayed successfully")
                else:
                    logger.debug("Graph does not support draw_mermaid_png() method")
            except Exception as e:
                logger.debug(f"Graph visualization failed (non-critical): {e}")
        
        except Exception as e:
            # Silently fail - visualization is optional and shouldn't break execution
            logger.debug(f"Graph visualization error (non-critical): {e}")
    
    def _create_checkpointer(self):
        """Create a checkpointer for conversation history persistence.
        
        Returns:
            Checkpointer instance or None if checkpointing is not available
        """
        try:
            settings = get_settings()
            checkpoint_path = Path(settings.checkpoint_db_path)
            
            # Ensure parent directory exists
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Try to use SqliteSaver for persistent checkpointing
            try:
                from langgraph.checkpoint.sqlite import SqliteSaver
                checkpointer = SqliteSaver.from_conn_string(str(checkpoint_path))
                logger.info(f"Created SqliteSaver checkpointer at {checkpoint_path}")
                return checkpointer
            except ImportError as import_err:
                # Fallback to MemorySaver if SqliteSaver is not available
                logger.warning(
                    f"SqliteSaver not available ({import_err}), falling back to MemorySaver. "
                    "Conversation history will not persist across server restarts."
                )
            except Exception as e:
                # If SqliteSaver import succeeded but creation failed, log and fallback
                logger.warning(
                    f"Failed to create SqliteSaver checkpointer: {e}. "
                    "Falling back to MemorySaver. Conversation history will not persist across server restarts."
                )
            
            # Fallback to MemorySaver if SqliteSaver failed
            try:
                from langgraph.checkpoint.memory import MemorySaver
                checkpointer = MemorySaver()
                logger.info("Created MemorySaver checkpointer (in-memory only)")
                return checkpointer
            except ImportError:
                logger.error("Neither SqliteSaver nor MemorySaver available. Checkpointing disabled.")
                return None
        except Exception as e:
            logger.error(f"Failed to create checkpointer: {e}", exc_info=True)
            return None
    
    def get_graph_image(self) -> Optional[bytes]:
        """Get the graph visualization as PNG bytes.
        
        Returns:
            PNG image bytes or None if visualization is not available
        """
        if not self._graph:
            return None
        
        try:
            # Get the underlying graph from compiled graph
            underlying_graph = self._graph.get_graph()
            
            # Check if the graph has draw_mermaid_png method
            if hasattr(underlying_graph, 'draw_mermaid_png'):
                png_bytes = underlying_graph.draw_mermaid_png()
                return png_bytes
            else:
                logger.debug("Graph does not support draw_mermaid_png() method")
                return None
        except Exception as e:
            logger.warning(f"Failed to generate graph image: {e}")
            return None