"""Tool discovery and binding system."""

from typing import Dict, Any, List, Optional
from agent.mcp_client import MCPClient
from config.settings import get_settings


class ToolDiscovery:
    """Tool discovery system for MCP servers."""
    
    def __init__(self, mcp_client: Optional[MCPClient] = None):
        """Initialize tool discovery.
        
        Args:
            mcp_client: MCP client instance (creates new if not provided)
        """
        self.settings = get_settings()
        self.mcp_client = mcp_client or MCPClient()
        self._discovered_tools: Dict[str, Dict[str, Any]] = {}
    
    async def discover_tools(
        self,
        server_url: str,
        server_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Discover tools from an MCP server.
        
        Args:
            server_url: Base URL of the MCP server
            server_name: Optional server name for identification
            
        Returns:
            Dictionary with server info and discovered tools
        """
        try:
            tools_info = await self.mcp_client.list_tools(server_url)
            
            server_id = server_name or tools_info.get("server_name", server_url)
            
            # Store discovered tools
            for tool in tools_info.get("tools", []):
                tool_key = f"{server_id}::{tool['name']}"
                self._discovered_tools[tool_key] = {
                    "server": server_id,
                    "server_url": server_url,
                    "server_version": tools_info.get("server_version"),
                    "protocol_version": tools_info.get("protocol_version"),
                    "tool": tool
                }
            
            return {
                "server": server_id,
                "server_url": server_url,
                "server_version": tools_info.get("server_version"),
                "protocol_version": tools_info.get("protocol_version"),
                "tools": tools_info.get("tools", []),
                "tool_count": len(tools_info.get("tools", []))
            }
            
        except Exception as e:
            return {
                "server": server_name or server_url,
                "server_url": server_url,
                "error": str(e),
                "tools": [],
                "tool_count": 0
            }
    
    async def discover_all_servers(self) -> Dict[str, Any]:
        """Discover tools from all configured MCP servers.
        
        Returns:
            Dictionary with discovery results for all servers
        """
        results = {}
        
        # Catalog server
        catalog_url = f"http://localhost:{self.settings.catalog_mcp_port}"
        results["catalog"] = await self.discover_tools(
            catalog_url,
            "catalog"
        )
        
        # SQL Query server
        sql_url = f"http://localhost:{self.settings.sql_mcp_port}"
        results["sql_query"] = await self.discover_tools(
            sql_url,
            "sql_query"
        )
        
        # Vector Search server
        vector_url = f"http://localhost:{self.settings.vector_mcp_port}"
        results["vector_search"] = await self.discover_tools(
            vector_url,
            "vector_search"
        )
        
        return results
    
    def get_discovered_tools(self) -> Dict[str, Dict[str, Any]]:
        """Get all discovered tools.
        
        Returns:
            Dictionary mapping tool keys to tool information
        """
        return self._discovered_tools.copy()
    
    def get_tool_info(self, tool_key: str) -> Optional[Dict[str, Any]]:
        """Get information for a specific tool.
        
        Args:
            tool_key: Tool key in format "server::tool_name"
            
        Returns:
            Tool information dictionary or None if not found
        """
        return self._discovered_tools.get(tool_key)
    
    async def close(self):
        """Close the MCP client."""
        await self.mcp_client.close()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()