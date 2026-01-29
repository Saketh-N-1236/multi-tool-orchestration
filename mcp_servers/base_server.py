"""Base MCP server with HTTP + Auth + Versioning."""

import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uuid
from datetime import datetime
from config.settings import get_settings

# Setup logging
logger = logging.getLogger(__name__)

# Version metadata
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"  # MCP protocol version


class BaseMCPServer:
    """Base class for MCP servers with HTTP + Auth + Versioning."""
    
    def __init__(self, server_name: str, tools: List[Dict[str, Any]]):
        """Initialize base MCP server.
        
        Args:
            server_name: Name of the server
            tools: List of tool definitions with versioning
        """
        self.server_name = server_name
        self.tools = tools
        self.settings = get_settings()
        self.app = FastAPI(title=f"{server_name} MCP Server")
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure as needed
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Add authentication middleware
        self._setup_middleware()
        
        # Setup routes
        self._setup_routes()
    
    def _setup_middleware(self):
        """Setup authentication middleware."""
        
        @self.app.middleware("http")
        async def verify_mcp_key(request: Request, call_next):
            """Verify MCP API key if configured."""
            if self.settings.mcp_api_key:
                api_key = request.headers.get("X-MCP-KEY")
                if api_key != self.settings.mcp_api_key:
                    return JSONResponse(
                        {"error": "Unauthorized", "message": "Invalid MCP API key"},
                        status_code=401
                    )
            return await call_next(request)
    
    def _setup_routes(self):
        """Setup HTTP routes."""
        
        @self.app.get("/health")
        async def health():
            """Health check endpoint with version info."""
            return {
                "status": "healthy",
                "server_name": self.server_name,
                "server_version": SERVER_VERSION,
                "protocol_version": PROTOCOL_VERSION,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        @self.app.get("/tools")
        async def list_tools(
            x_mcp_key: Optional[str] = Header(None, alias="X-MCP-KEY")
        ):
            """List all available tools with versioning."""
            return {
                "server_name": self.server_name,
                "server_version": SERVER_VERSION,
                "protocol_version": PROTOCOL_VERSION,
                "tools": self.tools
            }
        
        @self.app.post("/execute")
        async def execute_tool(
            request: Request,
            x_mcp_key: Optional[str] = Header(None, alias="X-MCP-KEY"),
            x_request_id: Optional[str] = Header(None, alias="X-Request-ID")
        ):
            """Execute a tool using JSON-RPC 2.0 format.
            
            Expected JSON-RPC 2.0 request:
            {
                "jsonrpc": "2.0",
                "id": "unique-id",
                "method": "tool_name",
                "params": {...}
            }
            """
            try:
                # Get request ID from header or generate new one
                request_id = x_request_id or str(uuid.uuid4())
                
                # Parse JSON-RPC 2.0 request
                body = await request.json()
                
                # Validate JSON-RPC 2.0 format
                if body.get("jsonrpc") != "2.0":
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": body.get("id"),
                        "error": {
                            "code": -32600,
                            "message": "Invalid Request",
                            "data": "jsonrpc must be '2.0'"
                        }
                    }, status_code=400)
                
                method = body.get("method")
                params = body.get("params", {})
                request_id_jsonrpc = body.get("id")
                
                if not method:
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": request_id_jsonrpc,
                        "error": {
                            "code": -32600,
                            "message": "Invalid Request",
                            "data": "method is required"
                        }
                    }, status_code=400)
                
                # Execute tool
                result = await self._execute_tool_internal(
                    method=method,
                    params=params,
                    request_id=request_id
                )
                
                # Return JSON-RPC 2.0 response
                return {
                    "jsonrpc": "2.0",
                    "id": request_id_jsonrpc,
                    "result": result,
                    "metadata": {
                        "request_id": request_id,
                        "server_version": SERVER_VERSION,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
                
            except ValueError as e:
                # Return JSON-RPC 2.0 error response for validation errors
                # This is expected behavior for invalid requests (e.g., read-only enforcement)
                logger.info(
                    f"Validation error for method '{method}': {str(e)[:100]}",
                    extra={"request_id": request_id, "method": method}
                )
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": body.get("id") if 'body' in locals() else None,
                    "error": {
                        "code": -32602,
                        "message": "Invalid params",
                        "data": str(e)
                    }
                }, status_code=400)
            except Exception as e:
                # Return JSON-RPC 2.0 error response for unexpected errors
                logger.error(
                    f"Internal error executing method '{method}': {str(e)}",
                    extra={"request_id": request_id, "method": method},
                    exc_info=True
                )
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": body.get("id") if 'body' in locals() else None,
                    "error": {
                        "code": -32603,
                        "message": "Internal Error",
                        "data": str(e)
                    }
                }, status_code=500)
    
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
