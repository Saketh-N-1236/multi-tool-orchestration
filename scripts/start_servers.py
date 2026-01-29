"""Start all MCP servers."""

import asyncio
import subprocess
import sys
from pathlib import Path
from config.settings import get_settings


def start_server(module_path: str, port: int, name: str):
    """Start a single MCP server.
    
    Args:
        module_path: Python module path to the server
        port: Port number
        name: Server name for logging
    """
    print(f"Starting {name} on port {port}...")
    subprocess.Popen(
        [sys.executable, "-m", module_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )


def main():
    """Start all MCP servers."""
    settings = get_settings()
    
    print("🚀 Starting MCP Servers...")
    print("-" * 50)
    
    # Start Catalog server
    start_server(
        "mcp_servers.catalog_server.server",
        settings.catalog_mcp_port,
        "Catalog MCP Server"
    )
    
    # Start SQL Query server
    start_server(
        "mcp_servers.sql_query_server.server",
        settings.sql_mcp_port,
        "SQL Query MCP Server"
    )
    
    # Start Vector Search server
    start_server(
        "mcp_servers.vector_search_server.server",
        settings.vector_mcp_port,
        "Vector Search MCP Server"
    )
    
    print("-" * 50)
    print("[OK] All servers started!")
    print(f"   Catalog Server: http://localhost:{settings.catalog_mcp_port}")
    print(f"   SQL Query Server: http://localhost:{settings.sql_mcp_port}")
    print(f"   Vector Search Server: http://localhost:{settings.vector_mcp_port}")
    print("\nPress Ctrl+C to stop all servers")


if __name__ == "__main__":
    main()
