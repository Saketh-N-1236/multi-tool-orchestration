"""Catalog MCP server implementation using FastMCP."""

import uvicorn
from typing import Dict, Any, Optional
import json
from mcp_servers.base_server import BaseMCPServer
from mcp_servers.catalog_server.database import CatalogDatabase
from mcp_servers.catalog_server.catalog_manager import CatalogManager
from config.settings import get_settings


class CatalogMCPServer(BaseMCPServer):
    """Catalog MCP server for database catalog operations."""
    
    def __init__(self):
        """Initialize catalog MCP server."""
        settings = get_settings()
        
        # Initialize catalog manager (Unity Catalog-like)
        self.catalog_manager = CatalogManager()
        
        # Keep backward compatibility with existing CatalogDatabase
        self.db = CatalogDatabase()
        
        super().__init__(
            server_name="catalog",
            port=settings.catalog_mcp_port
        )
        
        # Register tools using FastMCP's add_tool method
        self._register_tools()
    
    def _register_tools(self):
        """Register tools with FastMCP."""
        
        # Unified tools (backward compatible + multi-catalog support)
        @self.mcp.add_tool
        async def list_tables(
            catalog_name: Optional[str] = None,
            schema_name: Optional[str] = None
        ) -> Dict[str, Any]:
            """List tables in database/catalog.
            
            Supports both single database (backward compatible) and multi-catalog modes.
            
            Args:
                catalog_name: Optional catalog name (defaults to main database if not provided)
                schema_name: Optional schema name (defaults to "main" for SQLite if not provided)
            
            Returns:
                Dictionary with tables list and count. If catalog_name is provided,
                includes catalog and schema information.
            """
            if catalog_name:
                # Multi-catalog mode: use catalog_manager
                if not schema_name:
                    schemas = await self.catalog_manager.list_schemas(catalog_name)
                    schema_name = schemas[0] if schemas else "main"
                
                tables = await self.catalog_manager.list_tables(catalog_name, schema_name)
                return {
                    "catalog": catalog_name,
                    "schema": schema_name,
                    "tables": tables,
                    "count": len(tables)
                }
            else:
                # Backward compatible mode: use default database
                tables = await self.db.list_tables()
                return {
                    "tables": tables,
                    "count": len(tables)
                }
        
        @self.mcp.add_tool
        async def describe_table(
            table_name: str,
            catalog_name: Optional[str] = None,
            schema_name: Optional[str] = None
        ) -> Dict[str, Any]:
            """Get schema information for a table.
            
            Supports both single database (backward compatible) and multi-catalog modes.
            
            Args:
                table_name: Name of the table to describe (required)
                catalog_name: Optional catalog name (defaults to main database if not provided)
                schema_name: Optional schema name (defaults to "main" for SQLite if not provided)
            
            Returns:
                Dictionary with table schema information. If catalog_name is provided,
                includes catalog and schema information.
            """
            if not table_name:
                raise ValueError("table_name parameter is required")
            
            if catalog_name:
                # Multi-catalog mode: use catalog_manager
                if not schema_name:
                    schemas = await self.catalog_manager.list_schemas(catalog_name)
                    schema_name = schemas[0] if schemas else "main"
                
                return await self.catalog_manager.describe_table(
                    catalog_name, schema_name, table_name
                )
            else:
                # Backward compatible mode: use default database
                return await self.db.describe_table(table_name)
        
        @self.mcp.add_tool
        async def get_table_row_count(table_name: str) -> Dict[str, Any]:
            """Get the number of rows in a table.
            
            Args:
                table_name: Name of the table
                
            Returns:
                Dictionary with table name and row count
            """
            if not table_name:
                raise ValueError("table_name parameter is required")
            count = await self.db.get_table_row_count(table_name)
            return {
                "table_name": table_name,
                "row_count": count
            }
        
        # Unity Catalog-like tools (new)
        @self.mcp.add_tool
        async def list_catalogs() -> Dict[str, Any]:
            """List all available catalogs (Unity Catalog-like).
            
            Returns:
                Dictionary with catalogs list and count
            """
            catalogs = await self.catalog_manager.list_catalogs()
            return {
                "catalogs": catalogs,
                "count": len(catalogs)
            }
        
        @self.mcp.add_tool
        async def list_schemas(catalog_name: str) -> Dict[str, Any]:
            """List schemas in a catalog (Unity Catalog-like).
            
            Args:
                catalog_name: Name of the catalog
                
            Returns:
                Dictionary with schemas list and count
            """
            if not catalog_name:
                raise ValueError("catalog_name parameter is required")
            schemas = await self.catalog_manager.list_schemas(catalog_name)
            return {
                "catalog": catalog_name,
                "schemas": schemas,
                "count": len(schemas)
            }
        
        @self.mcp.add_tool
        async def search_tables(
            query: str,
            catalog_name: Optional[str] = None
        ) -> Dict[str, Any]:
            """Search tables across catalogs (Unity Catalog-like).
            
            Args:
                query: Search query (table name pattern)
                catalog_name: Optional catalog to search in (searches all if None)
                
            Returns:
                Dictionary with matching tables
            """
            if not query:
                raise ValueError("query parameter is required")
            
            results = await self.catalog_manager.search_tables(query, catalog_name)
            return {
                "query": query,
                "catalog": catalog_name or "all",
                "results": results,
                "count": len(results)
            }
        
        @self.mcp.add_tool
        async def get_table_lineage(
            catalog_name: str,
            schema_name: str,
            table_name: str
        ) -> Dict[str, Any]:
            """Get data lineage for a table (Unity Catalog-like).
            
            Args:
                catalog_name: Name of the catalog
                schema_name: Name of the schema
                table_name: Name of the table
                
            Returns:
                Dictionary with lineage information
            """
            if not catalog_name:
                raise ValueError("catalog_name parameter is required")
            if not schema_name:
                raise ValueError("schema_name parameter is required")
            if not table_name:
                raise ValueError("table_name parameter is required")
            
            return await self.catalog_manager.get_lineage(
                catalog_name, schema_name, table_name
            )


def create_app():
    """Create FastAPI app instance."""
    server = CatalogMCPServer()
    return server.get_app()


def run_server():
    """Run the catalog MCP server."""
    server = CatalogMCPServer()
    server.run()


if __name__ == "__main__":
    run_server()
