"""MCP client with HTTP + Auth + Concurrency."""

import httpx
import uuid
from typing import Dict, Any, Optional, List
from asyncio import Semaphore
from datetime import datetime
from config.settings import get_settings


class MCPClient:
    """HTTP client for MCP servers with authentication and concurrency control."""
    
    def __init__(
        self,
        max_parallel: Optional[int] = None,
        timeout: Optional[int] = None
    ):
        """Initialize MCP client.
        
        Args:
            max_parallel: Maximum parallel requests (default from settings)
            timeout: Request timeout in seconds (default from settings)
        """
        self.settings = get_settings()
        self.max_parallel = max_parallel or self.settings.max_parallel_mcp_calls
        self.timeout = timeout or self.settings.mcp_call_timeout
        self.semaphore = Semaphore(self.max_parallel)
        self._client = httpx.AsyncClient(timeout=self.timeout)
    
    async def call_tool(
        self,
        server_url: str,
        tool_name: str,
        params: Dict[str, Any],
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Call a tool on an MCP server.
        
        Args:
            server_url: Base URL of the MCP server
            tool_name: Name of the tool to call
            params: Tool parameters
            request_id: Request ID for correlation (auto-generated if not provided)
            
        Returns:
            Tool execution result
            
        Raises:
            httpx.HTTPError: If HTTP request fails
            ValueError: If response is invalid
        """
        request_id = request_id or str(uuid.uuid4())
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "X-Request-ID": request_id
        }
        
        # Add authentication if configured
        if self.settings.mcp_api_key:
            headers["X-MCP-KEY"] = self.settings.mcp_api_key
        
        # Prepare JSON-RPC 2.0 request
        jsonrpc_request = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": tool_name,
            "params": params
        }
        
        # Make request with concurrency control
        async with self.semaphore:
            try:
                response = await self._client.post(
                    f"{server_url}/execute",
                    json=jsonrpc_request,
                    headers=headers
                )
                
                # Parse response even if status is not 200
                try:
                    result = response.json()
                except Exception:
                    # If response is not JSON, raise HTTP error
                    response.raise_for_status()
                    raise
                
                # Validate JSON-RPC 2.0 response
                if result.get("jsonrpc") != "2.0":
                    raise ValueError(f"Invalid JSON-RPC response: {result}")
                
                # Check for JSON-RPC errors (even if HTTP status is 200)
                if "error" in result:
                    error = result["error"]
                    error_message = error.get("message", "Unknown error")
                    error_data = error.get("data", "")
                    
                    # Combine message and data for better error info
                    full_error = f"{error_message}"
                    if error_data:
                        full_error += f": {error_data}"
                    
                    raise ValueError(full_error)
                
                # If HTTP status is not 200 but no JSON-RPC error, raise HTTP error
                if response.status_code != 200:
                    response.raise_for_status()
                
                return result.get("result", {})
                
            except ValueError as e:
                # Re-raise ValueError (includes JSON-RPC errors)
                raise
            except httpx.HTTPError as e:
                raise Exception(f"MCP server HTTP error: {str(e)}")
            except Exception as e:
                raise Exception(f"MCP client error: {str(e)}")
    
    async def list_tools(
        self,
        server_url: str,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """List available tools from an MCP server.
        
        Args:
            server_url: Base URL of the MCP server
            request_id: Request ID for correlation
            
        Returns:
            Dictionary with server info and tools list
        """
        request_id = request_id or str(uuid.uuid4())
        
        headers = {
            "X-Request-ID": request_id
        }
        
        if self.settings.mcp_api_key:
            headers["X-MCP-KEY"] = self.settings.mcp_api_key
        
        async with self.semaphore:
            try:
                response = await self._client.get(
                    f"{server_url}/tools",
                    headers=headers
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                raise Exception(f"MCP server HTTP error: {str(e)}")
    
    async def health_check(self, server_url: str) -> Dict[str, Any]:
        """Check health of an MCP server.
        
        Args:
            server_url: Base URL of the MCP server
            
        Returns:
            Health status information
        """
        async with self.semaphore:
            try:
                response = await self._client.get(f"{server_url}/health")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                raise Exception(f"MCP server health check failed: {str(e)}")
    
    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
