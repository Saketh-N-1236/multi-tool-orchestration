"""SQL Query MCP server implementation using FastMCP."""

import uvicorn
from typing import Dict, Any, Optional
from mcp_servers.base_server import BaseMCPServer
from mcp_servers.sql_query_server.query_engine import SQLQueryEngine
from config.settings import get_settings


class SQLQueryMCPServer(BaseMCPServer):
    """SQL Query MCP server for read-only SQL queries."""
    
    def __init__(self):
        """Initialize SQL Query MCP server."""
        self.query_engine = SQLQueryEngine()
        settings = get_settings()
        
        super().__init__(
            server_name="sql_query",
            port=settings.sql_mcp_port
        )
        
        # Register tools using FastMCP's add_tool method
        self._register_tools()
    
    def _register_tools(self):
        """Register tools with FastMCP."""
        
        @self.mcp.add_tool
        async def execute_query(query: str, database: Optional[str] = None) -> Dict[str, Any]:
            """Execute a read-only SQL SELECT query.
            
            Args:
                query: SQL SELECT query to execute (read-only)
                database: Optional database/catalog name to query. If not specified, 
                         uses the default database. Use catalog_list_catalogs to see 
                         available databases.
                
            Returns:
                Dictionary with query results including database information
                
            Examples:
                - Query default database: execute_query("SELECT * FROM users")
                - Query specific database: execute_query("SELECT * FROM inference_logs", database="inference_logs")
            """
            if not query:
                raise ValueError("query parameter is required")
            return await self.query_engine.execute_query(query, database)
        
        @self.mcp.add_tool
        async def explain_query(query: str, database: Optional[str] = None) -> Dict[str, Any]:
            """Get execution plan for a SQL SELECT query.
            
            Args:
                query: SQL SELECT query to explain (read-only)
                database: Optional database/catalog name to query. If not specified, 
                         uses the default database. Use catalog_list_catalogs to see 
                         available databases.
                
            Returns:
                Dictionary with execution plan including database information
            """
            if not query:
                raise ValueError("query parameter is required")
            return await self.query_engine.explain_query(query, database)


def create_app():
    """Create FastAPI app instance."""
    server = SQLQueryMCPServer()
    return server.get_app()


def run_server():
    """Run the SQL Query MCP server."""
    server = SQLQueryMCPServer()
    server.run()


if __name__ == "__main__":
    run_server()
