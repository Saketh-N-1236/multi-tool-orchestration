"""Stdio entry point for Cursor integration.

This script runs the catalog MCP server in stdio mode for Cursor IDE integration.
"""

import sys
from pathlib import Path

# Add backend directory to path to ensure imports work
backend_path = Path(__file__).parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from mcp_servers.catalog_server.server import CatalogMCPServer
from mcp.server.stdio import stdio_server

if __name__ == "__main__":
    # Create server instance
    server = CatalogMCPServer()
    
    # Run in stdio mode (for Cursor)
    stdio_server(server.mcp)
