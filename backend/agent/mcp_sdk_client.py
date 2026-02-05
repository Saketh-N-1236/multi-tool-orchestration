"""MCP SDK Client wrapper using official MCP Python SDK with SSE transport.

This module provides a wrapper around the official MCP Python SDK
for connecting to MCP servers via SSE (Server-Sent Events) transport.
"""

import asyncio
from typing import Dict, Any, Optional, List
from asyncio import Semaphore
from datetime import datetime, timedelta
import logging
import httpx

try:
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    from mcp.types import Tool, TextContent
    MCP_SDK_AVAILABLE = True
except ImportError:
    MCP_SDK_AVAILABLE = False
    ClientSession = None
    sse_client = None
    Tool = None
    TextContent = None

from config.settings import get_settings

logger = logging.getLogger(__name__)

# Global tool cache with TTL (shared across all MCPSDKClient instances)
_tool_cache_global: Dict[str, tuple[List[Tool], datetime]] = {}
_cache_ttl_seconds = 60  # Cache for 60 seconds
_cache_lock = asyncio.Lock()


async def get_cached_tools(server_name: str, force_refresh: bool = False) -> Optional[List[Tool]]:
    """Get cached tools if available and not expired.
    
    Args:
        server_name: Name of the server
        force_refresh: If True, ignore cache
        
    Returns:
        Cached tools or None if not available/expired
    """
    if force_refresh:
        return None
    
    async with _cache_lock:
        if server_name not in _tool_cache_global:
            return None
        
        tools, cached_time = _tool_cache_global[server_name]
        if datetime.utcnow() - cached_time > timedelta(seconds=_cache_ttl_seconds):
            # Cache expired
            del _tool_cache_global[server_name]
            return None
        
        return tools


def set_cached_tools(server_name: str, tools: List[Tool]):
    """Cache tools for a server (synchronous wrapper for async operation).
    
    Args:
        server_name: Name of the server
        tools: List of tools to cache
    """
    # Use thread-safe dict update (Python dict operations are atomic)
    _tool_cache_global[server_name] = (tools, datetime.utcnow())


def clear_tool_cache():
    """Clear the global tool cache."""
    _tool_cache_global.clear()


class MCPSDKClient:
    """MCP SDK Client wrapper using official MCP Python SDK with SSE transport.
    
    This client uses the official MCP Python SDK to connect to MCP servers
    via SSE (Server-Sent Events) transport following the official MCP protocol.
    """
    
    def __init__(
        self,
        max_parallel: Optional[int] = None,
        timeout: Optional[int] = None
    ):
        """Initialize MCP SDK client.
        
        Args:
            max_parallel: Maximum parallel requests (default from settings)
            timeout: Request timeout in seconds (default from settings)
        """
        if not MCP_SDK_AVAILABLE:
            raise ImportError(
                "MCP SDK is not installed. Install with: pip install mcp>=1.0.0"
            )
        
        self.settings = get_settings()
        self.max_parallel = max_parallel or self.settings.max_parallel_mcp_calls
        self.timeout = timeout or self.settings.mcp_call_timeout
        self.connect_timeout = getattr(self.settings, 'mcp_connect_timeout', 10)
        self.semaphore = Semaphore(self.max_parallel)
        
        # Server configuration: server_name -> server_url (SSE endpoint)
        self.server_configs: Dict[str, str] = {}
        
        # Session storage: server_name -> ClientSession
        # Sessions are created on-demand and managed per operation
        self._sessions: Dict[str, ClientSession] = {}
        
        # Tool cache: server_name -> List[Tool]
        self._tool_cache: Dict[str, List[Tool]] = {}
        
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize connections to all configured MCP servers.
        
        This method sets up server configurations for SSE endpoints.
        SSE endpoints follow the pattern: http://host:port/sse
        """
        if self._initialized:
            return
        
        # Get server SSE URLs from settings
        # MCP SSE endpoints typically use /sse path
        server_configs = {
            "catalog": f"http://localhost:{self.settings.catalog_mcp_port}/sse",
            "sql_query": f"http://localhost:{self.settings.sql_mcp_port}/sse",
            "vector_search": f"http://localhost:{self.settings.vector_mcp_port}/sse",
        }
        
        # Load additional servers from settings (dynamic configuration)
        if hasattr(self.settings, 'additional_mcp_servers') and self.settings.additional_mcp_servers:
            try:
                import json
                additional_servers = json.loads(self.settings.additional_mcp_servers)
                if isinstance(additional_servers, dict):
                    server_configs.update(additional_servers)
                    logger.info(f"Loaded {len(additional_servers)} additional MCP server(s) from settings")
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse additional_mcp_servers from settings: {e}")
        
        # Also load from server config file (for persistence)
        try:
            from pathlib import Path
            server_config_file = Path("backend/data/server_configs.json")
            if server_config_file.exists():
                import json
                with open(server_config_file, 'r', encoding='utf-8') as f:
                    file_servers = json.load(f)
                    if isinstance(file_servers, dict):
                        server_configs.update(file_servers)
                        logger.info(f"Loaded {len(file_servers)} additional MCP server(s) from config file")
        except Exception as e:
            logger.warning(f"Failed to load server configs from file: {e}")
        
        # Store server configurations
        for server_name, server_url in server_configs.items():
            self.server_configs[server_name] = server_url
            logger.info(f"Configured MCP server (SSE): {server_name} at {server_url}")
        
        self._initialized = True
        logger.info(f"Initialized MCP SDK client with {len(self.server_configs)} SSE server configurations")
    
    async def _get_session(self, server_name: str) -> ClientSession:
        """Get or create a ClientSession for a server.
        
        Creates a new SSE session for each operation (sessions are not persistent).
        
        Args:
            server_name: Name of the server
            
        Returns:
            ClientSession instance
        """
        if server_name not in self.server_configs:
            raise ValueError(f"Server '{server_name}' not configured")
        
        server_url = self.server_configs[server_name]
        
        # Create SSE client session
        # The sse_client context manager handles the connection
        async with sse_client(server_url) as (read, write):
            session = ClientSession(read, write)
            await session.initialize()
            return session
    
    async def list_tools(self, server_name: str) -> List[Tool]:
        """List available tools from an MCP server using official MCP SDK.
        
        Args:
            server_name: Name of the server
            
        Returns:
            List of Tool objects (MCP SDK format)
            
        Raises:
            ConnectionError: If the server is not reachable
            Exception: For other connection/communication errors
        """
        # Check global cache first
        cached_tools = await get_cached_tools(server_name)
        if cached_tools is not None:
            logger.debug(f"Using cached tools for {server_name} ({len(cached_tools)} tools)")
            # Also cache in instance cache
            self._tool_cache[server_name] = cached_tools
            return cached_tools
        
        # Check instance cache
        if server_name in self._tool_cache:
            return self._tool_cache[server_name]
        
        async with self.semaphore:
            try:
                server_url = self.server_configs.get(server_name)
                if not server_url:
                    raise ValueError(f"Server '{server_name}' not configured")
                
                logger.info(f"Connecting to MCP server '{server_name}' at {server_url}...")
                
                # Use official MCP SDK SSE transport with retry logic
                # Note: sse_client may not support timeout parameter directly
                # Connection timeout is handled by httpx internally
                # Add retry logic for connection issues
                max_retries = 2
                last_error = None
                
                for attempt in range(max_retries + 1):
                    try:
                        async with sse_client(server_url) as (read, write):
                            async with ClientSession(read, write) as session:
                                await session.initialize()
                                
                                # Use official MCP SDK method to list tools
                                tools_response = await session.list_tools()
                                tools = tools_response.tools
                                
                                # Cache in both instance and global cache
                                self._tool_cache[server_name] = tools
                                set_cached_tools(server_name, tools)
                                
                                logger.info(
                                    f"Successfully discovered {len(tools)} tools from server '{server_name}' via SSE"
                                )
                                
                                return tools
                    except ExceptionGroup as eg:
                        # Unwrap ExceptionGroup to check if it's a connection error
                        actual_exc = None
                        if hasattr(eg, 'exceptions') and len(eg.exceptions) > 0:
                            actual_exc = eg.exceptions[0]
                        
                        # Check if it's a connection-related error
                        if isinstance(actual_exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.TimeoutException)):
                            last_error = actual_exc
                            if attempt < max_retries:
                                wait_time = (attempt + 1) * 2  # Exponential backoff: 2s, 4s
                                logger.warning(
                                    f"Connection attempt {attempt + 1}/{max_retries + 1} failed for '{server_name}'. "
                                    f"Retrying in {wait_time}s... Error: {type(actual_exc).__name__}"
                                )
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                # All retries exhausted, re-raise as ConnectionError
                                error_msg = (
                                    f"Cannot connect to MCP server '{server_name}' at {server_url}. "
                                    f"Make sure the server is running. Error: {type(actual_exc).__name__}"
                                )
                                raise ConnectionError(error_msg) from actual_exc
                        else:
                            # Not a connection error, re-raise the ExceptionGroup
                            raise
                    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.TimeoutException) as e:
                        last_error = e
                        if attempt < max_retries:
                            wait_time = (attempt + 1) * 2  # Exponential backoff: 2s, 4s
                            logger.warning(
                                f"Connection attempt {attempt + 1}/{max_retries + 1} failed for '{server_name}'. "
                                f"Retrying in {wait_time}s... Error: {type(e).__name__}"
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            # All retries exhausted, re-raise the last error
                            error_msg = (
                                f"Cannot connect to MCP server '{server_name}' at {server_url}. "
                                f"Make sure the server is running. Error: {type(e).__name__}"
                            )
                            raise ConnectionError(error_msg) from e
            except ExceptionGroup as eg:
                # Unwrap ExceptionGroup to get the actual exception
                # ExceptionGroup is raised by anyio.create_task_group() when sse_client fails
                actual_exc = None
                if hasattr(eg, 'exceptions') and len(eg.exceptions) > 0:
                    # Get the first exception from the group
                    actual_exc = eg.exceptions[0]
                    # Check if it's a connection-related error
                    if isinstance(actual_exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.TimeoutException)):
                        error_msg = (
                            f"Cannot connect to MCP server '{server_name}' at {self.server_configs.get(server_name, 'unknown')}. "
                            f"Make sure the server is running. Error: {type(actual_exc).__name__}"
                        )
                        logger.error(error_msg)
                        raise ConnectionError(error_msg) from actual_exc
                # If we can't unwrap it, raise as RuntimeError with original message
                error_msg = f"Failed to connect to MCP server '{server_name}': {eg}"
                logger.error(error_msg, exc_info=True)
                raise ConnectionError(error_msg) from eg
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.TimeoutException) as e:
                error_msg = (
                    f"Cannot connect to MCP server '{server_name}' at {self.server_configs.get(server_name, 'unknown')}. "
                    f"Make sure the server is running. Error: {type(e).__name__}"
                )
                logger.error(error_msg)
                raise ConnectionError(error_msg) from e
            except Exception as e:
                error_msg = f"Failed to list tools from server '{server_name}': {e}"
                logger.error(error_msg, exc_info=True)
                raise RuntimeError(error_msg) from e
    
    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Call a tool on an MCP server using official MCP SDK.
        
        Args:
            server_name: Name of the server
            tool_name: Name of the tool to call
            arguments: Tool arguments
            request_id: Optional request ID for correlation
            
        Returns:
            Tool execution result in format compatible with tool converter
        """
        async with self.semaphore:
            try:
                # Use official MCP SDK SSE transport
                async with sse_client(self.server_configs[server_name]) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        
                        # Use official MCP SDK method to call tool
                        result = await session.call_tool(tool_name, arguments)
                        
                        # Extract content from MCP SDK CallToolResult
                        content_parts = []
                        for content_item in result.content:
                            if isinstance(content_item, TextContent):
                                content_parts.append(content_item.text)
                            else:
                                # Handle other content types
                                content_parts.append(str(content_item))
                        
                        # Combine content parts
                        result_text = "\n".join(content_parts) if content_parts else ""
                        
                        # Check for errors
                        is_error = result.isError if hasattr(result, "isError") else False
                        
                        # Return in format compatible with tool converter
                        return {
                            "tool_name": tool_name,
                            "result": result_text,
                            "error": None if not is_error else result_text,
                            "isError": is_error
                        }
            except ExceptionGroup as eg:
                # Unwrap ExceptionGroup to get the actual exception
                actual_exc = None
                if hasattr(eg, 'exceptions') and len(eg.exceptions) > 0:
                    actual_exc = eg.exceptions[0]
                    if isinstance(actual_exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.TimeoutException)):
                        error_msg = (
                            f"Cannot connect to MCP server '{server_name}' to call tool '{tool_name}'. "
                            f"Make sure the server is running."
                        )
                        logger.error(error_msg)
                        return {
                            "tool_name": tool_name,
                            "result": None,
                            "error": error_msg,
                            "isError": True
                        }
                # Fallback for other ExceptionGroup cases
                error_msg = f"Failed to call tool '{tool_name}' on server '{server_name}': {eg}"
                logger.error(error_msg, exc_info=True)
                return {
                    "tool_name": tool_name,
                    "result": None,
                    "error": str(eg),
                    "isError": True
                }
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.TimeoutException) as e:
                error_msg = (
                    f"Cannot connect to MCP server '{server_name}' to call tool '{tool_name}'. "
                    f"Make sure the server is running. Error: {type(e).__name__}"
                )
                logger.error(error_msg)
                return {
                    "tool_name": tool_name,
                    "result": None,
                    "error": error_msg,
                    "isError": True
                }
            except Exception as e:
                logger.error(
                    f"Failed to call tool '{tool_name}' on server '{server_name}': {e}",
                    exc_info=True
                )
                return {
                    "tool_name": tool_name,
                    "result": None,
                    "error": str(e),
                    "isError": True
                }
    
    async def discover_all_tools(self) -> Dict[str, List[Tool]]:
        """Discover tools from all configured servers in parallel.
        
        Returns:
            Dictionary mapping server names to their tools
            
        Raises:
            RuntimeError: If no tools can be discovered from any server
        """
        import asyncio
        
        all_tools: Dict[str, List[Tool]] = {}
        errors: Dict[str, str] = {}
        
        # Create tasks for parallel execution
        async def discover_server(server_name: str) -> tuple[str, List[Tool] | None, str | None]:
            """Discover tools from a single server."""
            try:
                tools = await self.list_tools(server_name)
                return (server_name, tools if tools else None, None)
            except Exception as e:
                logger.warning(f"Could not discover tools from '{server_name}': {e}")
                return (server_name, None, str(e))
        
        # Discover all servers in parallel
        server_names = list(self.server_configs.keys())
        if not server_names:
            raise RuntimeError("No MCP servers configured")
        
        results = await asyncio.gather(
            *[discover_server(server_name) for server_name in server_names],
            return_exceptions=True
        )
        
        # Process results
        for result in results:
            if isinstance(result, Exception):
                # Handle gather exceptions
                logger.error(f"Unexpected error in parallel discovery: {result}", exc_info=True)
                continue
            
            server_name, tools, error = result
            if tools:
                all_tools[server_name] = tools
            elif error:
                errors[server_name] = error
            else:
                errors[server_name] = "No tools returned"
        
        # If no tools were discovered from any server, raise an error with diagnostic info
        if not all_tools:
            error_summary = "; ".join([f"{name}: {err}" for name, err in errors.items()])
            
            # Add diagnostic information
            diagnostic_info = []
            for server_name, server_url in self.server_configs.items():
                diagnostic_info.append(f"  - {server_name}: {server_url}")
            
            raise RuntimeError(
                f"Failed to discover tools from any MCP server. "
                f"Please ensure at least one MCP server is running.\n"
                f"Errors: {error_summary}\n"
                f"Configured servers:\n" + "\n".join(diagnostic_info) + "\n"
                f"To start servers, run: python -m backend.scripts.start_servers"
            )
        
        # Log summary
        total_tools = sum(len(tools) for tools in all_tools.values())
        logger.info(
            f"Tool discovery complete: {total_tools} tools from {len(all_tools)} server(s). "
            f"Servers: {', '.join(all_tools.keys())}"
        )
        
        if errors:
            logger.warning(
                f"Some servers failed: {', '.join(errors.keys())}. "
                f"Agent will work with available tools from: {', '.join(all_tools.keys())}"
            )
        
        return all_tools
    
    async def close(self) -> None:
        """Close all sessions and clean up resources."""
        # Clear caches
        self._tool_cache.clear()
        self._sessions.clear()
        self.server_configs.clear()
        self._initialized = False
        logger.info("MCP SDK client closed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
