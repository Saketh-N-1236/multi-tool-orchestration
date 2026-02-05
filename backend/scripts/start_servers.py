"""Start all MCP servers."""
import sys
import time
import signal
from pathlib import Path
from typing import List
import subprocess

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import get_settings

# Track spawned processes for cleanup
processes: List[subprocess.Popen] = []


def signal_handler(sig, frame):
    """Handle Ctrl+C to stop all servers."""
    print("\n\n[INFO] Stopping all servers...")
    for process in processes:
        try:
            process.terminate()
            process.wait(timeout=5)
        except (subprocess.TimeoutExpired, Exception):
            try:
                process.kill()
            except Exception:
                pass
    print("[OK] All servers stopped")
    sys.exit(0)


def start_server(module_path: str, port: int, name: str):
    """Start a single MCP server.
    
    Args:
        module_path: Python module path to the server
        port: Port number
        name: Server name for logging
        
    Returns:
        Process object
    """
    print(f"Starting {name} on port {port}...")
    process = subprocess.Popen(
        [sys.executable, "-m", module_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Combine stderr with stdout
        universal_newlines=True
    )
    processes.append(process)
    
    # Give server a moment to start
    time.sleep(1)
    
    # Check if process is still running
    if process.poll() is not None:
        print(f"[WARNING] {name} may have failed to start (process exited)")
    else:
        print(f"[OK] {name} process started")
    
    return process


def main():
    """Start all MCP servers."""
    settings = get_settings()
    
    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("Starting MCP Servers...")
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
    print("[OK] Server processes started!")
    print(f"   Catalog Server: http://localhost:{settings.catalog_mcp_port}")
    print(f"   SQL Query Server: http://localhost:{settings.sql_mcp_port}")
    print(f"   Vector Search Server: http://localhost:{settings.vector_mcp_port}")
    print("\n[INFO] Note: Server output is hidden. Check server logs for details.")
    print("[INFO] Press Ctrl+C to stop all servers")
    
    # Keep script running to maintain processes
    try:
        while True:
            # Check if any process died
            for i, process in enumerate(processes):
                if process.poll() is not None:
                    server_names = ["Catalog", "SQL Query", "Vector Search"]
                    print(f"\n[WARNING] {server_names[i]} server stopped unexpectedly!")
            time.sleep(5)
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    main()
