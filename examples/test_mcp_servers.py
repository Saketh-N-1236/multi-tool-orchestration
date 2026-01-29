"""Test MCP servers functionality."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agent.mcp_client import MCPClient
from agent.tool_binding import ToolDiscovery
from agent.tool_result_normalizer import normalize_result
from config.settings import get_settings


async def test_catalog_server():
    """Test catalog server."""
    print("\n" + "="*60)
    print("Testing Catalog MCP Server")
    print("="*60)
    
    settings = get_settings()
    server_url = f"http://localhost:{settings.catalog_mcp_port}"
    
    async with MCPClient() as client:
        # Health check
        print("\n1. Health Check:")
        try:
            health = await client.health_check(server_url)
            print(f"   ✅ Server: {health.get('server_name')}")
            print(f"   ✅ Version: {health.get('server_version')}")
            print(f"   ✅ Status: {health.get('status')}")
        except Exception as e:
            print(f"   ❌ Health check failed: {e}")
            return
        
        # List tools
        print("\n2. List Tools:")
        try:
            tools_info = await client.list_tools(server_url)
            print(f"   ✅ Server: {tools_info.get('server_name')}")
            print(f"   ✅ Tools found: {len(tools_info.get('tools', []))}")
            for tool in tools_info.get('tools', []):
                print(f"      - {tool['name']} (v{tool.get('tool_version', 'N/A')})")
        except Exception as e:
            print(f"   ❌ List tools failed: {e}")
            return
        
        # Call list_tables
        print("\n3. Call list_tables:")
        try:
            result = await client.call_tool(
                server_url=server_url,
                tool_name="list_tables",
                params={}
            )
            normalized = normalize_result(result, "list_tables")
            print(f"   ✅ Status: {normalized['status']}")
            if normalized['status'] == 'success':
                tables = normalized['data'].get('tables', [])
                print(f"   ✅ Tables found: {len(tables)}")
                for table in tables:
                    print(f"      - {table}")
        except Exception as e:
            print(f"   ❌ Call tool failed: {e}")
        
        # Call describe_table
        print("\n4. Call describe_table:")
        try:
            result = await client.call_tool(
                server_url=server_url,
                tool_name="describe_table",
                params={"table_name": "users"}
            )
            normalized = normalize_result(result, "describe_table")
            print(f"   ✅ Status: {normalized['status']}")
            if normalized['status'] == 'success':
                table_info = normalized['data']
                print(f"   ✅ Table: {table_info.get('table_name')}")
                print(f"   ✅ Columns: {len(table_info.get('columns', []))}")
        except Exception as e:
            print(f"   ❌ Call tool failed: {e}")


async def test_sql_query_server():
    """Test SQL query server."""
    print("\n" + "="*60)
    print("Testing SQL Query MCP Server")
    print("="*60)
    
    settings = get_settings()
    server_url = f"http://localhost:{settings.sql_mcp_port}"
    
    async with MCPClient() as client:
        # Health check
        print("\n1. Health Check:")
        try:
            health = await client.health_check(server_url)
            print(f"   ✅ Server: {health.get('server_name')}")
            print(f"   ✅ Status: {health.get('status')}")
        except Exception as e:
            print(f"   ❌ Health check failed: {e}")
            return
        
        # Execute query
        print("\n2. Execute SELECT Query:")
        try:
            result = await client.call_tool(
                server_url=server_url,
                tool_name="execute_query",
                params={"query": "SELECT * FROM users LIMIT 3"}
            )
            normalized = normalize_result(result, "execute_query")
            print(f"   ✅ Status: {normalized['status']}")
            if normalized['status'] == 'success':
                data = normalized['data']
                print(f"   ✅ Rows returned: {data.get('row_count', 0)}")
        except Exception as e:
            print(f"   ❌ Query execution failed: {e}")
        
        # Test read-only enforcement
        print("\n3. Test Read-Only Enforcement:")
        try:
            result = await client.call_tool(
                server_url=server_url,
                tool_name="execute_query",
                params={"query": "INSERT INTO users (name, email) VALUES ('Test', 'test@test.com')"}
            )
            print(f"   [ERROR] Read-only check failed - INSERT was allowed!")
        except Exception as e:
            error_str = str(e).lower()
            # Check for read-only enforcement indicators
            if any(keyword in error_str for keyword in [
                "read-only", "not allowed", "invalid params", 
                "insert", "update", "delete", "only select"
            ]):
                print(f"   [OK] Read-only enforcement working")
                print(f"   [OK] Error message: {str(e)[:80]}...")
            else:
                print(f"   [WARNING] Unexpected error format: {e}")
                print(f"   [INFO] This might still be correct - check if INSERT was blocked")


async def test_tool_discovery():
    """Test tool discovery."""
    print("\n" + "="*60)
    print("Testing Tool Discovery")
    print("="*60)
    
    discovery = ToolDiscovery()
    try:
        print("\n1. Discover All Servers:")
        results = await discovery.discover_all_servers()
        
        for server_name, server_info in results.items():
            if "error" in server_info:
                print(f"   ❌ {server_name}: {server_info['error']}")
            else:
                print(f"   ✅ {server_name}:")
                print(f"      - Server Version: {server_info.get('server_version')}")
                print(f"      - Tools: {server_info.get('tool_count', 0)}")
        
        print("\n2. Get All Discovered Tools:")
        tools = discovery.get_discovered_tools()
        print(f"   ✅ Total tools discovered: {len(tools)}")
        for tool_key, tool_info in tools.items():
            print(f"      - {tool_key}")
    finally:
        await discovery.close()


async def main():
    """Main test function."""
    print("="*60)
    print("MCP Servers Test Suite")
    print("="*60)
    print("\n[WARNING] Make sure servers are running:")
    print("   python -m mcp_servers.catalog_server.server")
    print("   python -m mcp_servers.sql_query_server.server")
    print("   python -m mcp_servers.vector_search_server.server")
    print("\nStarting tests in 2 seconds...")
    
    try:
        import sys
        if sys.stdin.isatty():
            # Only wait for input if running in interactive terminal
            try:
                input("Press Enter to continue or Ctrl+C to exit...")
            except KeyboardInterrupt:
                print("\nExiting...")
                return
        else:
            # Non-interactive mode, wait a bit then continue
            import time
            time.sleep(2)
    except Exception:
        # If anything fails, just continue
        pass
    
    # Run tests
    await test_catalog_server()
    await test_sql_query_server()
    await test_tool_discovery()
    
    print("\n" + "="*60)
    print("✅ All tests completed!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
