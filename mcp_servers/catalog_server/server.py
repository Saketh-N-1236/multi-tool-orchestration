"""Catalog MCP server implementation."""

import uvicorn
from typing import Dict, Any
from mcp_servers.base_server import BaseMCPServer
from mcp_servers.catalog_server.tools import get_tools
from mcp_servers.catalog_server.database import CatalogDatabase
from config.settings import get_settings


class CatalogMCPServer(BaseMCPServer):
    """Catalog MCP server for database catalog operations."""
    
    def __init__(self):
        """Initialize catalog MCP server."""
        self.db = CatalogDatabase()
        super().__init__(
            server_name="Catalog MCP Server",
            tools=get_tools()
        )
    
    async def _execute_tool_internal(
        self,
        method: str,
        params: Dict[str, Any],
        request_id: str
    ) -> Any:
        """Execute catalog tool.
        
        Args:
            method: Tool method name
            params: Tool parameters
            request_id: Request ID for correlation
            
        Returns:
            Tool execution result
        """
        if method == "list_tables":
            tables = await self.db.list_tables()
            return {
                "tables": tables,
                "count": len(tables)
            }
        
        elif method == "describe_table":
            table_name = params.get("table_name")
            if not table_name:
                raise ValueError("table_name parameter is required")
            return await self.db.describe_table(table_name)
        
        elif method == "get_table_row_count":
            table_name = params.get("table_name")
            if not table_name:
                raise ValueError("table_name parameter is required")
            count = await self.db.get_table_row_count(table_name)
            return {
                "table_name": table_name,
                "row_count": count
            }
        
        else:
            raise ValueError(f"Unknown tool method: {method}")


def create_app():
    """Create FastAPI app instance."""
    server = CatalogMCPServer()
    return server.app


def run_server():
    """Run the catalog MCP server."""
    settings = get_settings()
    uvicorn.run(
        "mcp_servers.catalog_server.server:create_app",
        host="0.0.0.0",
        port=settings.catalog_mcp_port,
        reload=False
    )


if __name__ == "__main__":
    run_server()
