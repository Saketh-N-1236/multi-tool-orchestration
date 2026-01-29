"""Test Vector Search MCP server."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agent.mcp_client import MCPClient
from agent.tool_result_normalizer import normalize_result
from config.settings import get_settings


async def test_vector_search():
    """Test vector search server."""
    print("="*60)
    print("Testing Vector Search MCP Server")
    print("="*60)
    
    settings = get_settings()
    server_url = f"http://localhost:{settings.vector_mcp_port}"
    
    async with MCPClient() as client:
        # Health check
        print("\n1. Health Check:")
        try:
            health = await client.health_check(server_url)
            print(f"   [OK] Server: {health.get('server_name')}")
            print(f"   [OK] Status: {health.get('status')}")
        except Exception as e:
            print(f"   [ERROR] Health check failed: {e}")
            print("   Make sure the server is running:")
            print(f"   python -m mcp_servers.vector_search_server.server")
            return
        
        # Add documents
        print("\n2. Add Documents:")
        try:
            result = await client.call_tool(
                server_url=server_url,
                tool_name="add_documents",
                params={
                    "collection": "test",
                    "documents": [
                        {
                            "id": "doc1",
                            "text": "Machine learning is a subset of artificial intelligence",
                            "metadata": {"category": "AI"}
                        },
                        {
                            "id": "doc2",
                            "text": "Python is a popular programming language for data science",
                            "metadata": {"category": "Programming"}
                        },
                        {
                            "id": "doc3",
                            "text": "Vector databases store embeddings for semantic search",
                            "metadata": {"category": "Database"}
                        }
                    ]
                }
            )
            normalized = normalize_result(result, "add_documents")
            print(f"   [OK] Status: {normalized['status']}")
            if normalized['status'] == 'success':
                data = normalized['data']
                print(f"   [OK] Added {data.get('added_count')} documents")
                print(f"   [OK] Total in collection: {data.get('total_documents')}")
        except Exception as e:
            print(f"   [ERROR] Add documents failed: {e}")
        
        # Search documents
        print("\n3. Search Documents:")
        try:
            result = await client.call_tool(
                server_url=server_url,
                tool_name="search_documents",
                params={
                    "query": "artificial intelligence and machine learning",
                    "collection": "test",
                    "top_k": 2
                }
            )
            normalized = normalize_result(result, "search_documents")
            print(f"   [OK] Status: {normalized['status']}")
            if normalized['status'] == 'success':
                data = normalized['data']
                print(f"   [OK] Query: {data.get('query')}")
                print(f"   [OK] Results found: {data.get('count')}")
                for i, res in enumerate(data.get('results', []), 1):
                    print(f"      {i}. Score: {res.get('score', 0):.4f} - {res.get('text', '')[:60]}...")
        except Exception as e:
            print(f"   [ERROR] Search failed: {e}")
        
        # List collections
        print("\n4. List Collections:")
        try:
            result = await client.call_tool(
                server_url=server_url,
                tool_name="list_collections",
                params={}
            )
            normalized = normalize_result(result, "list_collections")
            print(f"   [OK] Status: {normalized['status']}")
            if normalized['status'] == 'success':
                data = normalized['data']
                print(f"   [OK] Collections: {data.get('collections', [])}")
        except Exception as e:
            print(f"   [ERROR] List collections failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_vector_search())
