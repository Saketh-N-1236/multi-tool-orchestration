"""Base MCP server using official FastMCP framework.

This module provides a base class for MCP servers using the official
FastMCP framework, which properly implements the MCP protocol over SSE.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import Request
from fastapi.responses import JSONResponse
from config.settings import get_settings

# Try to import FastMCP
try:
    from mcp.server.fastmcp import FastMCP
    FASTMCP_AVAILABLE = True
except ImportError:
    FASTMCP_AVAILABLE = False
    FastMCP = None

# Setup logging
logger = logging.getLogger(__name__)

# Version metadata
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"  # MCP protocol version


class BaseMCPServer:
    """Base class for MCP servers using FastMCP framework."""
    
    def __init__(
        self,
        server_name: str,
        port: int,
        tools_config: Any = None
    ):
        """Initialize base MCP server with FastMCP.
        
        Args:
            server_name: Name of the server
            port: Port to run the server on
            tools_config: Configuration for tools (to be implemented by subclasses)
        """
        if not FASTMCP_AVAILABLE:
            raise RuntimeError(
                "FastMCP is not available. Please install the MCP SDK: "
                "pip install mcp"
            )
        
        self.server_name = server_name
        self.port = port
        self.settings = get_settings()
        
        # Create FastMCP server instance
        # FastMCP automatically handles SSE at /sse endpoint
        self.mcp = FastMCP(
            name=server_name,
            sse_path="/sse",  # SSE endpoint path
            host="0.0.0.0",
            port=port,
            log_level="INFO"
        )
        
        # Register health check endpoint
        self._setup_health_endpoint()
        
        # Setup tools (to be implemented by subclasses)
        self._setup_tools()
        
        logger.info(f"Initialized {server_name} MCP server on port {port}")
    
    def _setup_health_endpoint(self):
        """Setup health check endpoint."""
        
        @self.mcp.custom_route("/health", methods=["GET"])
        async def health_check(request: Request) -> JSONResponse:
            """Health check endpoint with version info."""
            return JSONResponse({
                "status": "healthy",
                "server_name": self.server_name,
                "server_version": SERVER_VERSION,
                "protocol_version": PROTOCOL_VERSION,
                "sse_enabled": True,
                "sse_path": "/sse"
            })
    
    def _setup_tools(self):
        """Setup tools. Override in subclasses."""
        pass
    
    async def _execute_tool_internal(
        self,
        method: str,
        params: Dict[str, Any],
        request_id: str
    ) -> Any:
        """Execute tool internally. Override in subclasses.
        
        Args:
            method: Tool method name
            params: Tool parameters
            request_id: Request ID for correlation
            
        Returns:
            Tool execution result
            
        Raises:
            NotImplementedError: If not overridden
        """
        raise NotImplementedError(
            "Subclasses must implement _execute_tool_internal"
        )
    
    def get_app(self):
        """Get the FastAPI app instance."""
        # FastMCP exposes the SSE app via sse_app method
        return self.mcp.sse_app()
    
    def run(self):
        """Run the server using FastMCP's built-in run method."""
        # FastMCP's run() method handles SSE transport automatically
        # Note: FastMCP uses the host and port from __init__, so we need to recreate
        # with the correct port, or use uvicorn directly
        import uvicorn
        app = self.mcp.sse_app()
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=self.port,
            log_level="info"
        )
