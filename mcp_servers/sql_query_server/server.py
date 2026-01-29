"""SQL Query MCP server implementation."""

import uvicorn
from typing import Dict, Any
from mcp_servers.base_server import BaseMCPServer
from mcp_servers.sql_query_server.tools import get_tools
from mcp_servers.sql_query_server.query_engine import SQLQueryEngine
from config.settings import get_settings


class SQLQueryMCPServer(BaseMCPServer):
    """SQL Query MCP server for read-only SQL queries."""
    
    def __init__(self):
        """Initialize SQL Query MCP server."""
        self.query_engine = SQLQueryEngine()
        super().__init__(
            server_name="SQL Query MCP Server",
            tools=get_tools()
        )
    
    async def _execute_tool_internal(
        self,
        method: str,
        params: Dict[str, Any],
        request_id: str
    ) -> Any:
        """Execute SQL query tool.
        
        Args:
            method: Tool method name
            params: Tool parameters
            request_id: Request ID for correlation
            
        Returns:
            Tool execution result
        """
        if method == "execute_query":
            query = params.get("query")
            if not query:
                raise ValueError("query parameter is required")
            return await self.query_engine.execute_query(query)
        
        elif method == "explain_query":
            query = params.get("query")
            if not query:
                raise ValueError("query parameter is required")
            return await self.query_engine.explain_query(query)
        
        else:
            raise ValueError(f"Unknown tool method: {method}")


def create_app():
    """Create FastAPI app instance."""
    server = SQLQueryMCPServer()
    return server.app


def run_server():
    """Run the SQL Query MCP server."""
    settings = get_settings()
    uvicorn.run(
        "mcp_servers.sql_query_server.server:create_app",
        host="0.0.0.0",
        port=settings.sql_mcp_port,
        reload=False
    )


if __name__ == "__main__":
    run_server()
