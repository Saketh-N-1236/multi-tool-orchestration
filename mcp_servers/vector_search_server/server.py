"""Vector Search MCP server implementation."""

import uvicorn
from typing import Dict, Any
from mcp_servers.base_server import BaseMCPServer
from mcp_servers.vector_search_server.tools import get_tools
from mcp_servers.vector_search_server.vector_store import SimpleVectorStore
from config.settings import get_settings


class VectorSearchMCPServer(BaseMCPServer):
    """Vector Search MCP server for semantic document search."""
    
    def __init__(self):
        """Initialize Vector Search MCP server."""
        self.vector_store = SimpleVectorStore()
        super().__init__(
            server_name="Vector Search MCP Server",
            tools=get_tools()
        )
    
    async def _execute_tool_internal(
        self,
        method: str,
        params: Dict[str, Any],
        request_id: str
    ) -> Any:
        """Execute vector search tool.
        
        Args:
            method: Tool method name
            params: Tool parameters
            request_id: Request ID for correlation
            
        Returns:
            Tool execution result
        """
        if method == "search_documents":
            query = params.get("query")
            if not query:
                raise ValueError("query parameter is required")
            
            collection = params.get("collection", "default")
            top_k = params.get("top_k", 5)
            
            results = await self.vector_store.search(
                query=query,
                collection_name=collection,
                top_k=top_k
            )
            
            return {
                "query": query,
                "collection": collection,
                "results": results,
                "count": len(results)
            }
        
        elif method == "add_documents":
            documents = params.get("documents")
            if not documents:
                raise ValueError("documents parameter is required")
            
            collection = params.get("collection", "default")
            
            result = await self.vector_store.add_documents(
                collection_name=collection,
                documents=documents
            )
            
            return result
        
        elif method == "list_collections":
            collections = self.vector_store.list_collections()
            return {
                "collections": collections,
                "count": len(collections)
            }
        
        else:
            raise ValueError(f"Unknown tool method: {method}")


def create_app():
    """Create FastAPI app instance."""
    server = VectorSearchMCPServer()
    return server.app


def run_server():
    """Run the Vector Search MCP server."""
    settings = get_settings()
    uvicorn.run(
        "mcp_servers.vector_search_server.server:create_app",
        host="0.0.0.0",
        port=settings.vector_mcp_port,
        reload=False
    )


if __name__ == "__main__":
    run_server()
