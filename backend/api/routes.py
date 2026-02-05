"""API routes for agent queries."""

from fastapi import APIRouter, Request, HTTPException, Depends, UploadFile, File, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uuid
import json
import logging
from io import BytesIO

# LangGraph imports (required - we're using LangGraph only)
from agent.agent_pool import get_agent
from agent.state_converter import convert_langgraph_state_to_agent
from agent.langgraph_state import LangGraphAgentState
from agent.mcp_sdk_client import MCPSDKClient
from agent.tool_result_normalizer import normalize_result
from config.settings import get_settings

# Type alias for compatibility
AgentState = dict  # LangGraph state is converted to dict format
from mcp_servers.vector_search_server.text_chunker import chunk_document
from inference_logging import get_inference_logger
from analytics.aggregator import AnalyticsAggregator
import httpx
# get_tracker will be imported locally in functions to avoid conflict with installed mlflow package

logger = logging.getLogger(__name__)

router = APIRouter()
settings = get_settings()


def validate_collection_name(collection_name: str) -> str:
    """Validate and normalize collection name for ChromaDB.
    
    ChromaDB collection name requirements:
    1. Contains 3-63 characters
    2. Starts and ends with an alphanumeric character
    3. Otherwise contains only alphanumeric characters, underscores or hyphens (-)
    4. Contains no two consecutive periods (..)
    5. Is not a valid IPv4 address
    
    Args:
        collection_name: Original collection name
        
    Returns:
        Normalized collection name
        
    Raises:
        HTTPException: If collection name cannot be normalized
    """
    if not collection_name:
        collection_name = "default"
    
    import re
    
    # Remove invalid characters, keep only alphanumeric, underscore, hyphen
    clean_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in collection_name)
    
    # Remove consecutive underscores/hyphens
    clean_name = re.sub(r'[_-]{2,}', '_', clean_name)
    
    # Remove leading/trailing non-alphanumeric characters
    clean_name = clean_name.strip('_-')
    
    # Ensure it starts and ends with alphanumeric
    if clean_name and not clean_name[0].isalnum():
        clean_name = 'c' + clean_name
    if clean_name and not clean_name[-1].isalnum():
        clean_name = clean_name + '1'
    
    # Ensure minimum length of 3 characters (ChromaDB requirement)
    if len(clean_name) < 3:
        # Pad with numbers to reach minimum length
        clean_name = clean_name.ljust(3, '0')
    
    # Ensure maximum length of 63 characters
    if len(clean_name) > 63:
        clean_name = clean_name[:63]
        # Ensure it still ends with alphanumeric
        if not clean_name[-1].isalnum():
            clean_name = clean_name[:-1] + '1'
    
    # Convert to lowercase for consistency
    clean_name = clean_name.lower()
    
    # Final validation: ensure it's not an IPv4 address pattern
    if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', clean_name):
        clean_name = 'collection_' + clean_name.replace('.', '_')
    
    # Warn if name was changed significantly
    if clean_name != collection_name.lower():
        logger.info(f"Collection name normalized: '{collection_name}' -> '{clean_name}'")
    
    return clean_name


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str = Field(..., description="User message/query")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    max_iterations: int = Field(10, ge=1, le=20, description="Maximum agent iterations")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="LLM temperature override")
    max_tokens: Optional[int] = Field(None, ge=50, le=4000, description="Max tokens override (minimum 50 for meaningful responses)")


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str = Field(..., description="Agent response")
    request_id: str = Field(..., description="Request ID for tracing")
    session_id: Optional[str] = Field(None, description="Session ID")
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list, description="Tools used")
    tool_results: List[Dict[str, Any]] = Field(default_factory=list, description="Tool results")
    iterations: int = Field(..., description="Number of iterations")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    llm_provider: str
    embedding_provider: Optional[str] = None
    mcp_servers: Dict[str, str]
    features: Optional[Dict[str, Any]] = None


async def get_request_id(request: Request) -> str:
    """Get request ID from request state.
    
    Args:
        request: FastAPI request
        
    Returns:
        Request ID
    """
    return getattr(request.state, "request_id", str(uuid.uuid4()))


def format_tool_name(tool_name: str) -> str:
    """Format tool name to be user-friendly.
    
    Converts "server_tool" format to "Tool Name (Server)" format.
    
    Args:
        tool_name: Tool name in format "server_tool" or "tool"
        
    Returns:
        Formatted tool name like "List Tables (catalog)" or "Tool Name"
    """
    if not tool_name:
        return "Unknown Tool"
    
    # Check if it's in server_tool format
    if "_" in tool_name:
        parts = tool_name.split("_", 1)
        if len(parts) == 2:
            server, tool = parts
            # Convert tool name to title case (e.g., "list_tables" -> "List Tables")
            tool_formatted = tool.replace("_", " ").title()
            return f"{tool_formatted} ({server})"
    
    # If no server prefix, just format the tool name
    return tool_name.replace("_", " ").title()


def extract_tool_names_from_calls(tool_calls: List[Dict[str, Any]]) -> List[str]:
    """Extract and format tool names from tool_calls list.
    
    Args:
        tool_calls: List of tool call dictionaries
        
    Returns:
        List of formatted tool names
    """
    tool_names = []
    seen = set()  # Track unique tool names
    
    for tc in tool_calls:
        if not isinstance(tc, dict):
            continue
            
        # Try different possible keys for tool name
        tool_name = (
            tc.get("tool_name") or 
            tc.get("name") or 
            tc.get("tool") or
            ""
        )
        
        if tool_name and tool_name not in seen:
            formatted_name = format_tool_name(tool_name)
            tool_names.append(formatted_name)
            seen.add(tool_name)
    
    return tool_names


def normalize_content_to_string(content: Any) -> str:
    """Normalize content to string format (performance-optimized).
    
    Handles both string and list formats (e.g., Gemini content blocks).
    This is a safety check in case content wasn't normalized earlier.
    
    Args:
        content: Content in any format
        
    Returns:
        String content
    """
    if content is None:
        return ""
    
    if isinstance(content, str):
        return content
    
    if isinstance(content, list):
        # Fast path for common Gemini format: single block with text
        if len(content) == 1 and isinstance(content[0], dict):
            block = content[0]
            if block.get("type") == "text":
                return str(block.get("text", ""))
            if "text" in block:
                return str(block["text"])
        
        # General case: join all text parts
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
        
        return "\n".join(text_parts) if text_parts else ""
    
    # Fallback: convert to string
    return str(content) if content else ""


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request_body: ChatRequest,
    request: Request,
    request_id: str = Depends(get_request_id)
):
    """Chat endpoint for agent queries.
    
    Args:
        request_body: Chat request
        request: FastAPI request
        request_id: Request ID from middleware
        
    Returns:
        Chat response with agent output
    """
    # Store request body data in request.state for middleware logging
    setattr(request.state, "body_data", {
        "session_id": request_body.session_id,
        "max_iterations": request_body.max_iterations,
        "temperature": request_body.temperature,
        "max_tokens": request_body.max_tokens
    })
    import asyncio
    import time
    max_retries = 2  # Maximum 2 retries for rate limits
    retry_delay = None
    
    # Initialize MLflow tracker (lazy import to avoid circular imports)
    tracker = None
    try:
        import importlib.util
        from pathlib import Path
        
        # Use explicit file path import to avoid namespace conflict with installed mlflow package
        _mlflow_tracking_path = Path(__file__).parent.parent / "mlflow" / "tracking.py"
        _spec = importlib.util.spec_from_file_location("mlflow_tracking_chat", _mlflow_tracking_path)
        _mlflow_tracking_module = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mlflow_tracking_module)
        get_tracker = _mlflow_tracking_module.get_tracker
        tracker = get_tracker()
    except Exception as e:
        logger.debug(f"MLflow tracker not available or failed to initialize: {e}")
        tracker = None
    
    # Use LangGraph implementation (only implementation)
    # Use MLflow context manager if tracker is enabled
    # We'll enter the context at the start and exit at the end
    mlflow_run_info = None
    mlflow_start_time = None
    
    if tracker and tracker.enabled and settings.enable_mlflow_tracking:
        # Create context manager (don't enter yet - we'll enter it in the try block)
        try:
            mlflow_context = tracker.start_run(
                request_id=request_id,
                prompt_version="v1",  # Will be updated from state after agent invocation
                model_name="gemini-2.5-flash",  # Will be updated from state after agent invocation
                session_id=request_body.session_id,
                max_iterations=request_body.max_iterations,
                temperature=request_body.temperature,
                max_tokens=request_body.max_tokens
            )
            # Enter the context
            mlflow_run_info = mlflow_context.__enter__()
            mlflow_start_time = time.time()
            
            if mlflow_run_info:
                logger.info(f"MLflow run created for request: {request_id}, run_id: {mlflow_run_info.get('run_id', 'unknown')}")
            else:
                logger.warning(f"MLflow context entered but run_info is None for request: {request_id}")
                mlflow_context = None
        except Exception as e:
            logger.error(f"Failed to create MLflow run for request {request_id}: {e}", exc_info=True)
            mlflow_context = None
            mlflow_run_info = None
            mlflow_start_time = None
    else:
        mlflow_context = None
        mlflow_run_info = None
        mlflow_start_time = None
        if not tracker:
            logger.debug("MLflow tracker is None")
        elif not tracker.enabled:
            logger.debug("MLflow tracker is disabled")
        elif not settings.enable_mlflow_tracking:
            logger.debug("MLflow tracking is disabled in settings")
    
    try:
        for attempt in range(max_retries + 1):
            try:
                # Get singleton agent instance (reused across requests)
                agent = await get_agent()
                
                # Invoke agent with timeout protection
                # Calculate timeout: max_iterations * 30 seconds per iteration + buffer
                timeout_seconds = (request_body.max_iterations * 30) + 60  # 30s per iteration + 60s buffer
                timeout_seconds = min(timeout_seconds, 300)  # Cap at 5 minutes
                
                try:
                    state: AgentState = await asyncio.wait_for(
                        agent.invoke(
                            user_message=request_body.message,
                            request_id=request_id,
                            session_id=request_body.session_id or str(uuid.uuid4()),
                            max_iterations=request_body.max_iterations,
                            temperature=request_body.temperature,
                            max_tokens=request_body.max_tokens
                        ),
                        timeout=timeout_seconds
                    )
                except asyncio.TimeoutError:
                    raise HTTPException(
                        status_code=504,  # Gateway Timeout
                        detail=f"Agent execution timed out after {timeout_seconds} seconds. "
                               f"The request may be too complex or the agent is taking too long. "
                               f"Try reducing max_iterations or simplifying your query."
                    )
                
                # Extract final assistant message (optimized - use reversed to get last one faster)
                assistant_messages = [m for m in reversed(state["messages"]) if m.get("role") == "assistant"]
                
                if not assistant_messages:
                    raise HTTPException(
                        status_code=500,
                        detail="No response from agent"
                    )
                
                # Get the last assistant message (first in reversed list)
                last_assistant = assistant_messages[0]
                # Normalize content to handle list format (safety check)
                final_response = normalize_content_to_string(last_assistant.get("content", "No response"))
                
                # Get tool calls and results for logging
                tool_calls = state.get("tool_calls", [])
                tool_results = state.get("tool_results", [])
                
                # Validate and clean tool_calls
                validated_tool_calls = []
                for tc in tool_calls:
                    if isinstance(tc, dict) and ("tool_name" in tc or "name" in tc or "tool" in tc):
                        validated_tool_calls.append(tc)
                    else:
                        logger.warning(f"Invalid tool_call format skipped: {tc}")
                tool_calls = validated_tool_calls
                
                # Extract and format tool names for reference
                tool_names_used = extract_tool_names_from_calls(tool_calls)
                
                # Store tool_calls in request state for middleware to access
                # Use setattr to ensure it's properly set
                setattr(request.state, "tool_calls", tool_calls)
                setattr(request.state, "tool_results", tool_results)
                setattr(request.state, "iterations", state.get("current_step", 0))
                
                # Store question and answer for inference logging
                setattr(request.state, "question", request_body.message)
                setattr(request.state, "answer", final_response)
                
                # Also store request body data if available for metadata
                if hasattr(request, "body_data"):
                    setattr(request.state, "body_data", getattr(request, "body_data"))
                
                # Log to MLflow if tracker is enabled and MLflow tracking is enabled in settings
                if tracker and tracker.enabled and mlflow_run_info and settings.enable_mlflow_tracking:
                    try:
                        run_id = mlflow_run_info.get("run_id") if isinstance(mlflow_run_info, dict) else None
                        
                        # Calculate duration
                        duration = time.time() - mlflow_start_time if mlflow_start_time else None
                        
                        # Log agent execution metrics
                        tracker.log_agent_execution(
                            run_id=run_id,
                            request_id=request_id,
                            iterations=state.get("current_step", 0),
                            tool_calls=tool_calls,
                            tool_results=tool_results,
                            duration_seconds=duration,
                            error=state.get("error")
                        )
                        
                        logger.debug(f"Logged agent execution to MLflow for request: {request_id}, run_id: {run_id}")
                    except Exception as e:
                        logger.warning(f"Failed to log to MLflow: {e}", exc_info=True)
                        # Don't fail the request if MLflow logging fails
                
                # Build metadata with tool references
                metadata = {
                    "prompt_version": state.get("prompt_version", "v1"),
                    "model": state.get("model_name", "gemini-2.5-flash"),
                    "error": state.get("error"),
                    "tools_used": tool_names_used,  # List of formatted tool names
                    "tool_count": len(tool_names_used),  # Count of unique tools used
                    "tool_names": tool_names_used  # Alias for backward compatibility
                }
                
                # Optionally append tool references to response text (if tools were used)
                response_text = final_response
                if tool_names_used:
                    # Append tool references in a clear format
                    tools_reference = f"\n\n[Tools used: {', '.join(tool_names_used)}]"
                    response_text = final_response + tools_reference
                
                # Build response
                response = ChatResponse(
                    response=response_text,
                    request_id=request_id,
                    session_id=state.get("session_id"),
                    tool_calls=tool_calls,
                    tool_results=tool_results,
                    iterations=state.get("current_step", 0),
                    metadata=metadata
                )
                
                return response
            
            except Exception as e:
                error_msg = str(e)
                
                # Log error to MLflow if tracker is enabled and MLflow tracking is enabled in settings
                if tracker and tracker.enabled and mlflow_run_info and settings.enable_mlflow_tracking:
                    try:
                        run_id = mlflow_run_info.get("run_id") if isinstance(mlflow_run_info, dict) else None
                        duration = time.time() - mlflow_start_time if mlflow_start_time else None
                        
                        # Log error metrics
                        tracker.log_agent_execution(
                            run_id=run_id,
                            request_id=request_id,
                            iterations=0,  # No iterations completed on error
                            tool_calls=[],
                            tool_results=[],
                            duration_seconds=duration,
                            error=error_msg
                        )
                    except Exception as mlflow_error:
                        logger.warning(f"Failed to log error to MLflow: {mlflow_error}")
                
                # Check if it's a rate limit error and we should retry
                if ("429" in error_msg or "rate limit" in error_msg.lower()) and attempt < max_retries:
                    # Extract retry delay from exception if available
                    retry_delay = getattr(e, 'retry_delay', None)
                    if not retry_delay:
                        # Try to extract from error message
                        import re
                        match = re.search(r"retry.*?(\d+(?:\.\d+)?)\s*s", error_msg, re.IGNORECASE)
                        if match:
                            retry_delay = float(match.group(1))
                        else:
                            retry_delay = 60.0  # Default 60 seconds
                    
                    # Add small buffer
                    retry_delay = retry_delay + 2.0
                    
                    logger.warning(
                        f"Rate limit hit (attempt {attempt + 1}/{max_retries + 1}), "
                        f"retrying in {retry_delay:.1f} seconds... [routes.py]"
                    )
                    await asyncio.sleep(retry_delay)
                    continue  # Retry
                
                # Determine appropriate status code based on error type
                status_code = 500
                if "503" in error_msg or "temporarily unavailable" in error_msg.lower():
                    status_code = 503  # Service Unavailable
                elif "429" in error_msg or "rate limit" in error_msg.lower():
                    status_code = 429  # Too Many Requests
                elif "401" in error_msg or "403" in error_msg or "authentication" in error_msg.lower():
                    status_code = 401  # Unauthorized
                
                raise HTTPException(
                    status_code=status_code,
                    detail=f"Agent error [routes.py]: {error_msg}"
                )
    finally:
        # Always exit MLflow context if it was entered
        if mlflow_context and mlflow_run_info:
            try:
                mlflow_context.__exit__(None, None, None)
                logger.debug(f"Exited MLflow context for request: {request_id}")
            except Exception as e:
                logger.warning(f"Error closing MLflow context: {e}")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint with system status.
    
    Returns:
        Health status with system information
    """
    # Get MLflow tracking info with error handling
    try:
        # Import from our local mlflow.tracking module using explicit file path
        import importlib.util
        from pathlib import Path
        
        # Use explicit file path import to avoid namespace conflict with installed mlflow package
        _mlflow_tracking_path = Path(__file__).parent.parent / "mlflow" / "tracking.py"
        _spec = importlib.util.spec_from_file_location("mlflow_tracking_health", _mlflow_tracking_path)
        _mlflow_tracking_module = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mlflow_tracking_module)
        get_tracker = _mlflow_tracking_module.get_tracker
        
        tracker = get_tracker()
        mlflow_tracking = tracker.enabled if tracker else False
        mlflow_tracking_uri = tracker.tracking_uri if tracker and tracker.enabled else None
        mlflow_experiment_name = tracker.experiment_name if tracker and tracker.enabled else None
    except Exception as e:
        logger.debug(f"Failed to get MLflow tracker info: {e}")
        mlflow_tracking = False
        mlflow_tracking_uri = None
        mlflow_experiment_name = None
    
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        llm_provider=settings.llm_provider,
        embedding_provider=settings.embedding_provider,
        mcp_servers={
            "catalog": f"http://localhost:{settings.catalog_mcp_port}",
            "vector_search": f"http://localhost:{settings.vector_mcp_port}",
            "sql_query": f"http://localhost:{settings.sql_mcp_port}"
        },
        features={
            "mlflow_tracking": mlflow_tracking,
            "mlflow_tracking_uri": mlflow_tracking_uri,
            "mlflow_experiment_name": mlflow_experiment_name
        }
    )


@router.get("/tools")
async def list_tools():
    """List available tools from all MCP servers.
    
    Returns:
        List of available tools with server status information
    """
    try:
        from agent.mcp_sdk_client import MCPSDKClient
        import logging
        logger = logging.getLogger(__name__)
        
        # Use MCP SDK client to discover tools with proper resource management
        async with MCPSDKClient() as client:
            # Try to discover tools from all servers
            # This will handle partial failures gracefully
            try:
                all_tools = await client.discover_all_tools()
            except RuntimeError as e:
                # If no tools discovered from any server, return empty with helpful error
                error_msg = str(e)
                if "Failed to discover tools from any MCP server" in error_msg:
                    logger.warning(f"MCP servers not available: {error_msg}")
                    return {
                        "tools": [],
                        "count": 0,
                        "servers": {},
                        "error": "MCP servers are not running. Please start them with: python scripts/start_servers.py",
                        "status": "error",
                        "message": "No MCP servers are currently available. Please ensure all MCP servers are running."
                    }
                # Re-raise other RuntimeErrors
                raise
            
            tools = []
            servers_status = {}
            has_errors = False
            
            for server_name, server_tools in all_tools.items():
                if server_tools:
                    servers_status[server_name] = {
                        "status": "ok",
                        "error": None,
                        "tool_count": len(server_tools)
                    }
                    
                    for tool in server_tools:
                        tools.append({
                            "name": tool.name,
                            "description": tool.description,
                            "server": server_name,
                            "version": "1.0.0"  # MCP SDK tools don't have version in this format
                        })
                else:
                    servers_status[server_name] = {
                        "status": "error",
                        "error": "No tools returned",
                        "tool_count": 0
                    }
                    has_errors = True
            
            # Build response
            response = {
                "tools": tools,
                "count": len(tools),
                "servers": servers_status
            }
            
            # Add status field based on results
            if len(tools) == 0:
                response["status"] = "error"
                response["message"] = "No tools available from any MCP server"
            elif has_errors:
                response["status"] = "partial"
                response["message"] = "Some MCP servers are unavailable, but tools from available servers are listed"
            else:
                response["status"] = "ok"
                response["message"] = "All tools discovered successfully"
            
            return response
    
    except RuntimeError as e:
        # Handle RuntimeError from discover_all_tools
        error_msg = str(e)
        logger.error(f"Failed to discover tools: {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=503,  # Service Unavailable
            detail=f"MCP servers are not available: {error_msg}. Please ensure all MCP servers are running."
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to list tools: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list tools: {str(e)}"
        )


@router.get("/graph/visualization")
async def get_graph_visualization():
    """Get the LangGraph visualization as PNG image.
    
    Returns:
        PNG image of the compiled graph structure
    """
    try:
        # Get the agent instance
        agent = await get_agent()
        
        # Get the graph from the agent
        if not agent.graph:
            raise HTTPException(
                status_code=503,
                detail="Graph not yet initialized. Please make a chat request first to initialize the agent."
            )
        
        # Get the graph image from the compiled graph
        try:
            # Try to get the underlying graph
            underlying_graph = agent.graph.get_graph()
            
            # Check if the graph has draw_mermaid_png method
            if hasattr(underlying_graph, 'draw_mermaid_png'):
                png_bytes = underlying_graph.draw_mermaid_png()
                if png_bytes:
                    return Response(
                        content=png_bytes,
                        media_type="image/png",
                        headers={
                            "Content-Disposition": "inline; filename=langgraph_visualization.png"
                        }
                    )
                else:
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to generate graph visualization image"
                    )
            else:
                raise HTTPException(
                    status_code=501,
                    detail="Graph visualization not supported. The graph does not have draw_mermaid_png() method."
                )
        except AttributeError:
            # If get_graph() doesn't exist, try direct access
            if hasattr(agent.graph, 'draw_mermaid_png'):
                png_bytes = agent.graph.draw_mermaid_png()
                if png_bytes:
                    return Response(
                        content=png_bytes,
                        media_type="image/png",
                        headers={
                            "Content-Disposition": "inline; filename=langgraph_visualization.png"
                        }
                    )
            raise HTTPException(
                status_code=501,
                detail="Graph visualization not available. The compiled graph does not support visualization methods."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get graph visualization: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate graph visualization: {str(e)}"
        )


@router.get("/status")
async def status():
    """Get API status and configuration.
    
    Returns:
        API status information
    """
    # Get MLflow tracking info with error handling
    try:
        # Import from our local mlflow.tracking module using explicit file path
        import importlib.util
        from pathlib import Path
        
        # Use explicit file path import to avoid namespace conflict with installed mlflow package
        _mlflow_tracking_path = Path(__file__).parent.parent / "mlflow" / "tracking.py"
        _spec = importlib.util.spec_from_file_location("mlflow_tracking_status", _mlflow_tracking_path)
        _mlflow_tracking_module = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mlflow_tracking_module)
        get_tracker = _mlflow_tracking_module.get_tracker
        
        tracker = get_tracker()
        mlflow_tracking = tracker.enabled if tracker else False
        mlflow_tracking_uri = tracker.tracking_uri if tracker and tracker.enabled else None
        mlflow_experiment_name = tracker.experiment_name if tracker and tracker.enabled else None
    except Exception as e:
        logger.debug(f"Failed to get MLflow tracker info: {e}")
        mlflow_tracking = False
        mlflow_tracking_uri = None
        mlflow_experiment_name = None
    
    return {
        "api_version": "1.0.0",
        "llm_provider": settings.llm_provider,
        "embedding_provider": settings.embedding_provider,
        "model": {
            "chat": getattr(settings, f"{settings.llm_provider}_model", "unknown"),
            "embedding": getattr(settings, f"{settings.embedding_provider}_model", "unknown")
        },
        "mcp_servers": {
            "catalog": {
                "port": settings.catalog_mcp_port,
                "url": f"http://localhost:{settings.catalog_mcp_port}"
            },
            "vector_search": {
                "port": settings.vector_mcp_port,
                "url": f"http://localhost:{settings.vector_mcp_port}"
            },
            "sql_query": {
                "port": settings.sql_mcp_port,
                "url": f"http://localhost:{settings.sql_mcp_port}"
            }
        },
        "features": {
            "request_id_propagation": True,
            "inference_logging": True,
            "rate_limiting": bool(settings.api_key),
            "mlflow_tracking": mlflow_tracking,
            "mlflow_tracking_uri": mlflow_tracking_uri,
            "mlflow_experiment_name": mlflow_experiment_name
        }
    }


class DocumentUploadRequest(BaseModel):
    """Document upload request model."""
    documents: List[Dict[str, Any]] = Field(..., description="List of documents with 'id', 'text', and optional 'metadata'")
    collection: str = Field("default", description="Collection name")


class DocumentUploadResponse(BaseModel):
    """Document upload response model."""
    collection: str
    added_count: int
    total_documents: int
    request_id: str


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_documents(
    request_body: DocumentUploadRequest,
    request: Request,
    request_id: str = Depends(get_request_id)
):
    """Upload documents to the vector store.
    
    Args:
        request_body: Document upload request
        request: FastAPI request
        request_id: Request ID from middleware
        
    Returns:
        Upload response with collection info
    """
    try:
        server_url = f"http://localhost:{settings.vector_mcp_port}"
        
        # Note: Health check removed - MCP connection will fail gracefully if server is down
        # This saves ~50-100ms per request
        
        # Use longer timeout for document uploads (embedding generation can take time)
        # 24 chunks * ~2 seconds per embedding = ~48 seconds minimum, use 5 minutes for safety
        async with MCPSDKClient(timeout=300) as client:  # 5 minutes for large uploads
            # Validate collection name before sending to server
            normalized_collection = validate_collection_name(request_body.collection)
            
            # Chunk documents if they are large
            chunked_documents = []
            chunk_size = 1000
            chunk_overlap = 200
            
            for doc in request_body.documents:
                # Ensure metadata exists
                if "metadata" not in doc:
                    doc["metadata"] = {}
                
                # Add file_name to metadata if source exists but file_name doesn't
                if "source" in doc.get("metadata", {}) and "file_name" not in doc.get("metadata", {}):
                    doc["metadata"]["file_name"] = doc["metadata"]["source"]
                
                # Chunk the document (now async)
                doc_chunks = await chunk_document(
                    doc,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    min_chunk_size=100
                )
                
                # Add collection_name to each chunk's metadata
                for chunk in doc_chunks:
                    if "metadata" not in chunk:
                        chunk["metadata"] = {}
                    chunk["metadata"]["collection_name"] = normalized_collection
                    # Ensure file_name is set
                    if "file_name" not in chunk["metadata"] and "source" in chunk["metadata"]:
                        chunk["metadata"]["file_name"] = chunk["metadata"]["source"]
                
                chunked_documents.extend(doc_chunks)
            
            if len(chunked_documents) != len(request_body.documents):
                logger.info(
                    f"Chunked {len(request_body.documents)} documents into "
                    f"{len(chunked_documents)} chunks for collection '{normalized_collection}'"
                )
            
            result = await client.call_tool(
                server_name="vector_search",
                tool_name="add_documents",
                arguments={
                    "collection": normalized_collection,
                    "documents": chunked_documents
                },
                request_id=request_id
            )
            # Check for errors first
            if result.get("isError"):
                error_msg = result.get("error", "Unknown error")
                raise HTTPException(
                    status_code=500,
                    detail=f"Tool execution failed: {error_msg}"
                )
            
            # Parse the JSON string from result["result"]
            # MCPSDKClient returns {"tool_name": "...", "result": "<JSON_STRING>", ...}
            try:
                parsed_result = json.loads(result["result"])
            except (json.JSONDecodeError, TypeError, KeyError):
                # Fallback if result is already a dict or not JSON
                parsed_result = result.get("result", result)
            
            # Now normalize the parsed result
            normalized = normalize_result(parsed_result, "add_documents")
            
            if normalized["status"] != "success":
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to upload documents: {normalized.get('error')}"
                )
            
            data = normalized["data"]
            
            return DocumentUploadResponse(
                collection=data.get("collection", request_body.collection),
                added_count=data.get("added_count", 0),
                total_documents=data.get("total_documents", 0),
                request_id=request_id
            )
    
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        # Provide more helpful error messages for embedding errors
        if "embedding" in error_msg.lower() or "ollama" in error_msg.lower():
            raise HTTPException(
                status_code=500,
                detail=f"Document upload error: {error_msg}. "
                       f"Please ensure your embedding model is installed and running. "
                       f"For Ollama, try: ollama pull nomic-embed-text"
            )
        raise HTTPException(
            status_code=500,
            detail=f"Document upload error: {error_msg}"
        )


@router.post("/documents/upload-file")
async def upload_documents_from_file(
    file: UploadFile = File(...),
    collection: str = Query("default", description="Collection name (must be 3-63 characters, alphanumeric with underscores/hyphens)"),
    request: Request = None,
    request_id: str = Depends(get_request_id)
):
    """Upload documents from a JSON file or PDF file.
    
    Supported formats:
    1. JSON file - Array of document objects:
       [
           {
               "id": "doc1",
               "text": "Document content...",
               "metadata": {"source": "file.pdf"}
           },
           ...
       ]
    
    2. PDF file - Text will be extracted automatically:
       - Single document created from all pages
       - Metadata includes filename and page count
       - Requires PyPDF2 or pypdf library (install with: pip install PyPDF2)
    
    Args:
        file: Uploaded JSON or PDF file
        collection: Collection name (default: "default")
        request: FastAPI request
        request_id: Request ID from middleware
        
    Returns:
        Upload response with collection info
        
    Raises:
        HTTPException: If file is invalid, empty, or not supported format
    """
    try:
        # Read file content
        content = await file.read()
        
        # Check if file is empty
        if not content or len(content) == 0:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty. Please upload a valid JSON file or PDF file."
            )
        
        # Detect file type
        file_extension = file.filename.split('.')[-1].lower() if file.filename else ''
        content_type = file.content_type or ''
        is_pdf = file_extension == 'pdf' or content_type == 'application/pdf' or content.startswith(b'%PDF')
        documents = None
        
        if is_pdf:
            # Handle PDF file
            # Try to import PDF library
            pdf_library = None
            try:
                import PyPDF2
                pdf_library = PyPDF2
            except ImportError:
                # Fallback to pypdf if PyPDF2 not available
                try:
                    import pypdf
                    pdf_library = pypdf
                except ImportError:
                    raise HTTPException(
                        status_code=400,
                        detail="PDF support requires PyPDF2 or pypdf library. Install with: pip install PyPDF2 or pip install pypdf"
                    )
            
            # Extract text from PDF
            pdf_text = ""
            try:
                pdf_file = BytesIO(content)
                pdf_reader = pdf_library.PdfReader(pdf_file)
                
                # Convert pages to list to avoid iterator/coroutine issues
                # This ensures we can safely get length and iterate multiple times
                pages_list = list(pdf_reader.pages)
                page_count = len(pages_list)
                
                for page_num, page in enumerate(pages_list, 1):
                    try:
                        page_text = page.extract_text()
                        
                        # Handle async extract_text if it's a coroutine (unlikely but safe)
                        import inspect
                        if inspect.iscoroutine(page_text):
                            page_text = await page_text
                        
                        if page_text:
                            # Clean up the text - remove excessive whitespace and special characters
                            page_text = " ".join(page_text.split())  # Normalize whitespace
                            pdf_text += page_text + "\n\n"
                    except Exception as page_error:
                        # Log but continue with other pages
                        logger.warning(f"Failed to extract text from page {page_num}: {page_error}")
                
                if not pdf_text.strip():
                    raise HTTPException(
                        status_code=400,
                        detail="PDF file appears to be empty or contains no extractable text. The PDF might be image-based or encrypted."
                    )
                
                # Clean and validate the extracted text
                pdf_text = pdf_text.strip()
                
                # Create a document from the PDF
                doc_id = file.filename or f"pdf_doc_{request_id[:8]}"
                # Remove extension from filename for cleaner ID
                if '.' in doc_id:
                    doc_id = '.'.join(doc_id.split('.')[:-1])
                
                # Create base document
                base_document = {
                    "id": doc_id,
                    "text": pdf_text.strip(),
                    "metadata": {
                        "source": file.filename or "uploaded_pdf",
                        "file_name": file.filename or "uploaded_pdf",
                        "file_type": "pdf",
                        "page_count": str(page_count)
                    }
                }
                
                # Chunk the document if it's large
                # Default chunk size: 1000 chars, overlap: 200 chars
                # This ensures better embedding quality for large documents
                chunk_size = 1000
                chunk_overlap = 200
                
                documents = await chunk_document(
                    base_document,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    min_chunk_size=100
                )
                
                logger.info(
                    f"PDF '{file.filename}' processed: {page_count} pages, "
                    f"{len(pdf_text)} characters, split into {len(documents)} chunks"
                )
                
            except HTTPException:
                raise
            except Exception as pdf_error:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to extract text from PDF: {str(pdf_error)}. The PDF might be corrupted, encrypted, or image-based."
                )
        else:
            # Handle JSON file
            # Try to decode with multiple encodings
            text_content = None
            encodings_to_try = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
            
            for encoding in encodings_to_try:
                try:
                    text_content = content.decode(encoding)
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            
            if text_content is None:
                raise HTTPException(
                    status_code=400,
                    detail="Unable to decode file. Supported formats: JSON files (UTF-8, Latin-1, Windows-1252) or PDF files. If uploading a PDF, ensure it's not corrupted."
                )
            
            # Strip whitespace and check if content is empty after decoding
            text_content = text_content.strip()
            if not text_content:
                raise HTTPException(
                    status_code=400,
                    detail="File appears to be empty or contains only whitespace. Please upload a valid JSON file or PDF file."
                )
            
            # Parse JSON
            try:
                documents = json.loads(text_content)
            except json.JSONDecodeError as e:
                # Provide more helpful error message
                error_msg = str(e)
                if "Expecting value: line 1 column 1" in error_msg or "char 0" in error_msg:
                    raise HTTPException(
                        status_code=400,
                        detail="File appears to be empty or not valid JSON. Expected format: [{\"id\": \"doc1\", \"text\": \"Document content...\", \"metadata\": {...}}, ...]. Please ensure the file contains a JSON array of document objects."
                    )
                else:
                    # Use regular string concatenation to avoid f-string curly brace issues
                    format_example = '[{"id": "...", "text": "...", "metadata": {...}}, ...]'
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid JSON file: {error_msg}. Please ensure the file contains valid JSON in the format: {format_example}"
                    )
        
        # At this point, documents should be set (either from PDF or JSON)
        if documents is None:
            raise HTTPException(
                status_code=500,
                detail="Internal error: Failed to process file"
            )
        
        if not isinstance(documents, list):
            raise HTTPException(
                status_code=400,
                detail="File must contain a JSON array of documents. Expected format: [{\"id\": \"...\", \"text\": \"...\", \"metadata\": {...}}, ...]"
            )
        
        # Validate document structure
        for i, doc in enumerate(documents):
            if not isinstance(doc, dict):
                raise HTTPException(
                    status_code=400,
                    detail=f"Document at index {i} must be a JSON object"
                )
            if "id" not in doc or "text" not in doc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Document at index {i} must have 'id' and 'text' fields"
                )
        
        # Validate and normalize collection name
        try:
            normalized_collection = validate_collection_name(collection)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid collection name '{collection}': {str(e)}. Collection names must be 3-63 characters, start and end with alphanumeric characters, and contain only alphanumeric characters, underscores, or hyphens."
            )
        
        # Chunk documents if they are large
        # Process each document and chunk if needed
        chunked_documents = []
        chunk_size = 1000
        chunk_overlap = 200
        
        for doc in documents:
            # Ensure metadata exists
            if "metadata" not in doc:
                doc["metadata"] = {}
            
            # Add file_name to metadata if source exists but file_name doesn't
            if "source" in doc.get("metadata", {}) and "file_name" not in doc.get("metadata", {}):
                doc["metadata"]["file_name"] = doc["metadata"]["source"]
            
            # Chunk the document (async - must await)
            doc_chunks = await chunk_document(
                doc,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                min_chunk_size=100
            )
            
            # Add collection_name to each chunk's metadata
            for chunk in doc_chunks:
                if "metadata" not in chunk:
                    chunk["metadata"] = {}
                chunk["metadata"]["collection_name"] = normalized_collection
                # Ensure file_name is set
                if "file_name" not in chunk["metadata"] and "source" in chunk["metadata"]:
                    chunk["metadata"]["file_name"] = chunk["metadata"]["source"]
            
            chunked_documents.extend(doc_chunks)
        
        logger.info(
            f"Processed {len(documents)} documents into {len(chunked_documents)} chunks "
            f"for collection '{normalized_collection}'"
        )
        # Use the upload_documents endpoint
        request_body = DocumentUploadRequest(
            documents=chunked_documents,
            collection=normalized_collection
        )
        
        result = await upload_documents(request_body, request, request_id)
        return result
    
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON file: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON file: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in upload_documents_from_file: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading file: {str(e)}"
        )


@router.get("/documents/collections")
async def list_collections(
    request_id: str = Depends(get_request_id)
):
    """List all collections in the vector store.
    
    Args:
        request_id: Request ID from middleware
        
    Returns:
        List of collections
    """
    try:
        server_url = f"http://localhost:{settings.vector_mcp_port}"
        
        async with MCPSDKClient() as client:
            result = await client.call_tool(
                server_name="vector_search",
                tool_name="list_collections",
                arguments={},
                request_id=request_id
            )
            
            # Check for errors first
            if result.get("isError"):
                error_msg = result.get("error", "Unknown error")
                raise HTTPException(
                    status_code=500,
                    detail=f"Tool execution failed: {error_msg}"
                )
            
            # Parse the JSON string from result["result"]
            try:
                parsed_result = json.loads(result["result"])
            except (json.JSONDecodeError, TypeError, KeyError):
                # Fallback if result is already a dict or not JSON
                parsed_result = result.get("result", result)
            
            # Now normalize the parsed result
            normalized = normalize_result(parsed_result, "list_collections")
            
            if normalized["status"] != "success":
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to list collections: {normalized.get('error')}"
                )
            
            data = normalized["data"]
            
            # Calculate total documents across all collections
            collections = data.get("collections", [])
            total_documents = sum(
                col.get("document_count", 0) 
                for col in collections 
                if isinstance(col, dict) and col.get("document_count") is not None
            )
            
            return {
                "collections": collections,
                "collection_count": data.get("count", 0),
                "total_documents": total_documents,
                "request_id": request_id
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error listing collections: {str(e)}"
        )


@router.delete("/documents/collections/{collection_name}")
async def delete_collection(
    collection_name: str,
    request_id: str = Depends(get_request_id)
):
    """Delete a collection and all its documents.
    
    Args:
        collection_name: Name of collection to delete
        request_id: Request ID from middleware
        
    Returns:
        Deletion result
    """
    try:
        server_url = f"http://localhost:{settings.vector_mcp_port}"
        
        async with MCPSDKClient() as client:
            # Validate collection name
            try:
                normalized_collection = validate_collection_name(collection_name)
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid collection name: {str(e)}"
                )
            
            try:
                result = await client.call_tool(
                    server_name="vector_search",
                    tool_name="delete_collection",
                    arguments={"collection": normalized_collection},
                    request_id=request_id
                )
            except Exception as e:
                logger.error(f"Error calling delete_collection tool: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to connect to vector search server: {str(e)}. Make sure the MCP server is running."
                )
            
            # Check for errors first
            if result.get("isError"):
                error_msg = result.get("error", "Unknown error")
                raise HTTPException(
                    status_code=500,
                    detail=f"Tool execution failed: {error_msg}"
                )
            
            # Parse the JSON string from result["result"]
            try:
                parsed_result = json.loads(result["result"])
            except (json.JSONDecodeError, TypeError, KeyError):
                # Fallback if result is already a dict or not JSON
                parsed_result = result.get("result", result)
            
            # Now normalize the parsed result
            normalized = normalize_result(parsed_result, "delete_collection")
            
            if normalized["status"] != "success":
                error_msg = normalized.get('error', {})
                if isinstance(error_msg, dict):
                    error_msg = error_msg.get('message', str(error_msg))
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to delete collection: {error_msg}"
                )
            
            data = normalized["data"]
            
            if not data.get("deleted", False):
                raise HTTPException(
                    status_code=404,
                    detail=data.get("message", f"Collection '{collection_name}' not found or could not be deleted")
                )
            
            return {
                "success": True,
                "message": data.get("message", f"Collection '{normalized_collection}' deleted successfully"),
                "collection": normalized_collection,
                "request_id": request_id
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting collection: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting collection: {str(e)}"
        )


# ============================================================================
# Inference Logging API Endpoints
# ============================================================================

inference_logger = get_inference_logger()


class InferenceLogResponse(BaseModel):
    """Response model for inference log entry."""
    id: int
    request_id: str
    timestamp: str
    method: str
    path: str
    status_code: int
    duration: float
    error: Optional[str] = None
    question: Optional[str] = None
    answer: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class InferenceLogsListResponse(BaseModel):
    """Response model for inference logs list."""
    logs: List[InferenceLogResponse]
    total: int
    limit: int
    offset: int
    request_id: str


class InferenceLogStatsResponse(BaseModel):
    """Response model for inference log statistics."""
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_duration: float
    total_duration: float
    error_rate: float
    requests_by_status: Dict[str, int]
    requests_by_path: Dict[str, int]
    requests_by_method: Dict[str, int]
    request_id: str


@router.get("/logs/{request_id}", response_model=InferenceLogResponse)
async def get_inference_log(
    request_id: str,
    api_request_id: str = Depends(get_request_id)
):
    """Get inference log by request ID.
    
    Args:
        request_id: Request ID to look up
        api_request_id: Request ID from middleware
        
    Returns:
        Inference log entry
        
    Raises:
        HTTPException: If log not found
    """
    try:
        log = await inference_logger.get_log(request_id)
        
        if not log:
            raise HTTPException(
                status_code=404,
                detail=f"Inference log not found for request_id: {request_id}"
            )
        
        # Parse metadata JSON if present
        metadata = None
        if log.get("metadata"):
            try:
                metadata = json.loads(log["metadata"]) if isinstance(log["metadata"], str) else log["metadata"]
            except (json.JSONDecodeError, TypeError):
                metadata = log.get("metadata")
        
        return InferenceLogResponse(
            id=log["id"],
            request_id=log["request_id"],
            timestamp=log["timestamp"],
            method=log["method"],
            path=log["path"],
            status_code=log["status_code"],
            duration=log["duration"],
            error=log.get("error"),
            question=log.get("question"),
            answer=log.get("answer"),
            metadata=metadata
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get inference log: {str(e)}"
        )


@router.get("/logs", response_model=InferenceLogsListResponse)
async def list_inference_logs(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of logs to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    status_code: Optional[int] = Query(None, description="Filter by status code"),
    path: Optional[str] = Query(None, description="Filter by path (partial match)"),
    method: Optional[str] = Query(None, description="Filter by HTTP method"),
    request_id: str = Depends(get_request_id)
):
    """List inference logs with optional filters.
    
    Args:
        limit: Maximum number of logs to return (1-1000)
        offset: Offset for pagination
        status_code: Filter by status code (optional)
        path: Filter by path (partial match, optional)
        method: Filter by HTTP method (optional)
        request_id: Request ID from middleware
        
    Returns:
        List of inference logs
    """
    try:
        logs = await inference_logger.get_logs(limit=limit, offset=offset)
        
        # Apply filters if provided
        filtered_logs = logs
        if status_code is not None:
            filtered_logs = [log for log in filtered_logs if log.get("status_code") == status_code]
        if path:
            filtered_logs = [log for log in filtered_logs if path.lower() in log.get("path", "").lower()]
        if method:
            filtered_logs = [log for log in filtered_logs if log.get("method", "").upper() == method.upper()]
        
        # Parse metadata for each log
        parsed_logs = []
        for log in filtered_logs:
            metadata = None
            if log.get("metadata"):
                try:
                    metadata = json.loads(log["metadata"]) if isinstance(log["metadata"], str) else log["metadata"]
                except (json.JSONDecodeError, TypeError):
                    metadata = log.get("metadata")
            
            parsed_logs.append(InferenceLogResponse(
                id=log["id"],
                request_id=log["request_id"],
                timestamp=log["timestamp"],
                method=log["method"],
                path=log["path"],
                status_code=log["status_code"],
                duration=log["duration"],
                error=log.get("error"),
                question=log.get("question"),
                answer=log.get("answer"),
                metadata=metadata
            ))
        
        return InferenceLogsListResponse(
            logs=parsed_logs,
            total=len(parsed_logs),
            limit=limit,
            offset=offset,
            request_id=request_id
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list inference logs: {str(e)}"
        )


@router.get("/logs/stats/summary", response_model=InferenceLogStatsResponse)
async def get_inference_log_stats(
    request_id: str = Depends(get_request_id)
):
    """Get inference log statistics.
    
    Args:
        request_id: Request ID from middleware
        
    Returns:
        Statistics about inference logs
    """
    try:
        # Get all logs (with reasonable limit for stats)
        all_logs = await inference_logger.get_logs(limit=10000, offset=0)
        
        if not all_logs:
            return InferenceLogStatsResponse(
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                avg_duration=0.0,
                total_duration=0.0,
                error_rate=0.0,
                requests_by_status={},
                requests_by_path={},
                requests_by_method={},
                request_id=request_id
            )
        
        # Calculate statistics
        total_requests = len(all_logs)
        successful_requests = sum(1 for log in all_logs if 200 <= log.get("status_code", 0) < 300)
        failed_requests = sum(1 for log in all_logs if log.get("status_code", 0) >= 400)
        
        durations = [log.get("duration", 0.0) for log in all_logs if log.get("duration") is not None]
        total_duration = sum(durations)
        avg_duration = total_duration / len(durations) if durations else 0.0
        
        error_rate = (failed_requests / total_requests * 100) if total_requests > 0 else 0.0
        
        # Count by status code
        requests_by_status = {}
        for log in all_logs:
            status = str(log.get("status_code", "unknown"))
            requests_by_status[status] = requests_by_status.get(status, 0) + 1
        
        # Count by path
        requests_by_path = {}
        for log in all_logs:
            path = log.get("path", "unknown")
            requests_by_path[path] = requests_by_path.get(path, 0) + 1
        
        # Count by method
        requests_by_method = {}
        for log in all_logs:
            method = log.get("method", "unknown")
            requests_by_method[method] = requests_by_method.get(method, 0) + 1
        
        return InferenceLogStatsResponse(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_duration=round(avg_duration, 3),
            total_duration=round(total_duration, 3),
            error_rate=round(error_rate, 2),
            requests_by_status=requests_by_status,
            requests_by_path=requests_by_path,
            requests_by_method=requests_by_method,
            request_id=request_id
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get inference log statistics: {str(e)}"
        )


# ============================================================================
# Analytics & Monitoring API Endpoints
# ============================================================================

analytics_aggregator = AnalyticsAggregator()


class OverviewStatsResponse(BaseModel):
    """Response model for overview statistics."""
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float
    avg_duration: float
    median_duration: float
    min_duration: float
    max_duration: float
    total_duration: float
    error_rate: float
    requests_by_status: Dict[str, int]
    requests_by_path: Dict[str, int]
    requests_by_method: Dict[str, int]
    total_tool_calls: int
    total_iterations: int
    avg_iterations: float
    avg_tool_calls_per_request: float
    requests_with_tools: int
    request_id: str


class ToolUsageStatsResponse(BaseModel):
    """Response model for tool usage statistics."""
    tools: Dict[str, Dict[str, Any]]
    total_unique_tools: int
    total_tool_calls: int
    request_id: str


class ResponseTimeStatsResponse(BaseModel):
    """Response model for response time statistics."""
    total_requests: int
    avg_duration: float
    median_duration: float
    p95_duration: float
    p99_duration: float
    min_duration: float
    max_duration: float
    duration_by_path: Dict[str, Dict[str, Any]]
    duration_by_status: Dict[str, Dict[str, Any]]
    time_window_hours: Optional[int] = None
    request_id: str


class ErrorPatternsResponse(BaseModel):
    """Response model for error patterns."""
    total_errors: int
    error_rate: float
    errors_by_status: Dict[str, int]
    errors_by_path: Dict[str, int]
    common_errors: List[Dict[str, Any]]
    error_messages: List[Dict[str, Any]]
    request_id: str


class TimeSeriesStatsResponse(BaseModel):
    """Response model for time series statistics."""
    time_series: List[Dict[str, Any]]
    time_window_hours: int
    interval_minutes: int
    request_id: str


@router.get("/analytics/overview", response_model=OverviewStatsResponse)
async def get_analytics_overview(
    request_id: str = Depends(get_request_id)
):
    """Get overview analytics statistics.
    
    Args:
        request_id: Request ID from middleware
        
    Returns:
        Overview statistics
    """
    try:
        stats = await analytics_aggregator.get_overview_stats()
        stats["request_id"] = request_id
        return OverviewStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get analytics overview: {str(e)}"
        )


@router.get("/analytics/tools", response_model=ToolUsageStatsResponse)
async def get_tool_usage_stats(
    request_id: str = Depends(get_request_id)
):
    """Get tool usage statistics.
    
    Args:
        request_id: Request ID from middleware
        
    Returns:
        Tool usage statistics
    """
    try:
        stats = await analytics_aggregator.get_tool_usage_stats()
        stats["request_id"] = request_id
        return ToolUsageStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get tool usage statistics: {str(e)}"
        )


@router.get("/analytics/response-times", response_model=ResponseTimeStatsResponse)
async def get_response_time_stats(
    time_window_hours: Optional[int] = Query(None, ge=1, le=168, description="Time window in hours (1-168)"),
    request_id: str = Depends(get_request_id)
):
    """Get response time statistics.
    
    Args:
        time_window_hours: Optional time window in hours (e.g., 24 for last 24 hours)
        request_id: Request ID from middleware
        
    Returns:
        Response time statistics
    """
    try:
        stats = await analytics_aggregator.get_response_time_stats(time_window_hours)
        stats["request_id"] = request_id
        return ResponseTimeStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get response time statistics: {str(e)}"
        )


@router.get("/analytics/errors", response_model=ErrorPatternsResponse)
async def get_error_patterns(
    request_id: str = Depends(get_request_id)
):
    """Get error pattern analysis.
    
    Args:
        request_id: Request ID from middleware
        
    Returns:
        Error patterns and analysis
    """
    try:
        stats = await analytics_aggregator.get_error_patterns()
        stats["request_id"] = request_id
        return ErrorPatternsResponse(**stats)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get error patterns: {str(e)}"
        )


@router.get("/analytics/time-series", response_model=TimeSeriesStatsResponse)
async def get_time_series_stats(
    time_window_hours: int = Query(24, ge=1, le=168, description="Time window in hours (1-168)"),
    interval_minutes: int = Query(60, ge=1, le=1440, description="Interval in minutes (1-1440)"),
    request_id: str = Depends(get_request_id)
):
    """Get time series statistics.
    
    Args:
        time_window_hours: Time window in hours (default: 24)
        interval_minutes: Interval in minutes for bucketing (default: 60)
        request_id: Request ID from middleware
        
    Returns:
        Time series statistics
    """
    try:
        stats = await analytics_aggregator.get_time_series_stats(time_window_hours, interval_minutes)
        stats["request_id"] = request_id
        return TimeSeriesStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get time series statistics: {str(e)}"
        )


# ============================================================================
# MLflow API Endpoints
# ============================================================================

class MLflowRunResponse(BaseModel):
    """Response model for MLflow run."""
    run_id: str
    run_name: str
    status: str
    start_time: int
    end_time: Optional[int] = None
    request_id: Optional[str] = None
    prompt_version: Optional[str] = None
    model_name: Optional[str] = None
    metrics: Dict[str, float] = {}
    params: Dict[str, str] = {}


class MLflowExperimentResponse(BaseModel):
    """Response model for MLflow experiment."""
    experiment_id: str
    experiment_name: str
    artifact_location: str
    lifecycle_stage: str
    run_count: int
    runs: List[MLflowRunResponse] = []
    request_id: str


@router.get("/mlflow/experiment", response_model=MLflowExperimentResponse)
async def get_mlflow_experiment(
    limit: int = Query(50, ge=1, le=500, description="Maximum number of runs to return"),
    request_id: str = Depends(get_request_id)
):
    """Get MLflow experiment information and recent runs.
    
    Args:
        limit: Maximum number of runs to return
        request_id: Request ID from middleware
        
    Returns:
        MLflow experiment information with runs
    """
    try:
        # Import get_tracker from our local mlflow.tracking module
        import importlib.util
        from pathlib import Path
        
        _mlflow_tracking_path = Path(__file__).parent.parent / "mlflow" / "tracking.py"
        _spec = importlib.util.spec_from_file_location("mlflow_tracking_api_exp", _mlflow_tracking_path)
        _mlflow_tracking_module = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mlflow_tracking_module)
        get_tracker = _mlflow_tracking_module.get_tracker
        
        tracker = get_tracker()
        
        if not tracker.enabled:
            raise HTTPException(
                status_code=503,
                detail="MLflow tracking is not enabled or MLflow is not available. "
                       "To enable MLflow, ensure the 'mlflow' package is installed (pip install mlflow) "
                       "and MLflow tracking URI is configured in settings."
            )
        
        try:
            import mlflow
            # Import MlflowClient from installed mlflow package (not our local module)
            from mlflow.tracking import MlflowClient
            
            client = MlflowClient(tracking_uri=tracker.tracking_uri)
            
            # Try to get experiment by exact name first
            experiment = mlflow.get_experiment_by_name(tracker.experiment_name)
            
            # If not found, search for experiments matching the pattern (handles timestamped experiments)
            if experiment is None or experiment.lifecycle_stage == "deleted":
                all_experiments = mlflow.search_experiments()
                # Find experiments that start with the base name and are not deleted
                matching_experiments = [
                    exp for exp in all_experiments 
                    if exp.name.startswith(tracker.experiment_name) and exp.lifecycle_stage != "deleted"
                ]
                
                if matching_experiments:
                    # Use the most recent matching experiment (first one, as they're sorted)
                    experiment = matching_experiments[0]
                    logger.info(f"Using matching experiment: {experiment.name} (original: {tracker.experiment_name})")
                else:
                    # No matching experiment found
                    return MLflowExperimentResponse(
                        experiment_id="",
                        experiment_name=tracker.experiment_name,
                        artifact_location="",
                        lifecycle_stage="",
                        run_count=0,
                        runs=[],
                        request_id=request_id
                    )
            
            # Get recent runs from the experiment
            runs = client.search_runs(
                experiment_ids=[experiment.experiment_id],
                max_results=limit,
                order_by=["start_time DESC"]
            )
            
            run_responses = []
            for run in runs:
                run_data = {
                    "run_id": run.info.run_id,
                    "run_name": run.info.run_name or run.info.run_id[:8],
                    "status": run.info.status,
                    "start_time": run.info.start_time,
                    "end_time": run.info.end_time,
                    "metrics": {k: float(v) for k, v in run.data.metrics.items()},
                    "params": {k: str(v) for k, v in run.data.params.items()}
                }
                
                # Extract common parameters
                if "request_id" in run_data["params"]:
                    run_data["request_id"] = run_data["params"]["request_id"]
                if "prompt_version" in run_data["params"]:
                    run_data["prompt_version"] = run_data["params"]["prompt_version"]
                if "model_name" in run_data["params"]:
                    run_data["model_name"] = run_data["params"]["model_name"]
                
                run_responses.append(MLflowRunResponse(**run_data))
            
            return MLflowExperimentResponse(
                experiment_id=experiment.experiment_id,
                experiment_name=experiment.name,
                artifact_location=experiment.artifact_location,
                lifecycle_stage=experiment.lifecycle_stage,
                run_count=len(runs),
                runs=run_responses,
                request_id=request_id
            )
            
        except ImportError:
            raise HTTPException(
                status_code=503,
                detail="MLflow is not installed. Install with: pip install mlflow>=2.15.0"
            )
        except Exception as e:
            logger.error(f"Error fetching MLflow experiment: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch MLflow experiment: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get MLflow experiment: {str(e)}"
        )
