"""Vector Search MCP server implementation using FastMCP."""

import uvicorn
import logging
from typing import Dict, Any, List, Optional
from mcp_servers.base_server import BaseMCPServer
from mcp_servers.vector_search_server.vector_store import VectorStore
from config.settings import get_settings

logger = logging.getLogger(__name__)


class VectorSearchMCPServer(BaseMCPServer):
    """Vector Search MCP server for semantic document search."""
    
    def __init__(self):
        """Initialize Vector Search MCP server."""
        from mcp_servers.vector_search_server.vector_store import SimpleVectorStore
        
        # Try to initialize ChromaDB first
        try:
            self.vector_store = VectorStore()
            # Check which type of store was actually created
            store_type = type(self.vector_store).__name__
            logger.info(f"Vector store initialized successfully: {store_type}")
            
            # Warn if SimpleVectorStore is being used when ChromaDB should be available
            if store_type == "SimpleVectorStore":
                logger.warning(
                    "⚠️  WARNING: Using SimpleVectorStore (JSON files) instead of ChromaDB! "
                    "Data will be saved to JSON files in data/vector_store/. "
                    "To use ChromaDB, ensure chromadb>=0.4.0 is installed."
                )
            else:
                logger.info(f"✅ Using {store_type} - data stored in ChromaDB, not JSON files")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize ChromaDB vector store: {e}", exc_info=True)
            logger.warning("⚠️  Falling back to SimpleVectorStore (JSON files)...")
            logger.warning(
                "⚠️  NOTE: Documents will be saved to JSON files in data/vector_store/ "
                "instead of ChromaDB. To use ChromaDB, install with: pip install chromadb>=0.4.0"
            )
            try:
                # Fall back to SimpleVectorStore
                self.vector_store = SimpleVectorStore()
                logger.info("SimpleVectorStore initialized successfully as fallback")
            except Exception as fallback_error:
                logger.error(f"Failed to initialize fallback vector store: {fallback_error}", exc_info=True)
                raise
        
        settings = get_settings()
        super().__init__(
            server_name="vector_search",
            port=settings.vector_mcp_port
        )
        
        # Register tools using FastMCP's add_tool method
        self._register_tools()
    
    def _register_tools(self):
        """Register tools with FastMCP."""
        
        @self.mcp.add_tool
        async def search_documents(
            query: str,
            collection: str = "default",
            top_k: int = 5,
            search_all_collections: bool = False
        ) -> Dict[str, Any]:
            """Search for documents using semantic similarity.
            
            Args:
                query: Search query text
                collection: Collection name to search in (default: "default")
                top_k: Number of results to return (default: 5, min: 1, max: 100)
                search_all_collections: Whether to search across all collections (default: False)
                
            Returns:
                Dictionary with search results
            """
            if not query:
                raise ValueError("query parameter is required")
            
            # First, try searching in the specified collection
            results = await self.vector_store.search(
                query=query,
                collection_name=collection,
                top_k=top_k,
                search_all_collections=search_all_collections
            )
            
            logger.debug(f"Search in collection '{collection}': found {len(results)} results")
            
            # If no results in specified collection and it's "default", automatically try all collections
            if len(results) == 0 and collection == "default" and not search_all_collections:
                logger.info(f"No results in 'default' collection, automatically searching all collections...")
                all_results = await self.vector_store.search(
                    query=query,
                    collection_name=collection,
                    top_k=top_k,
                    search_all_collections=True
                )
                logger.info(f"Search across all collections: found {len(all_results)} results")
                if all_results:
                    results = all_results
                    collection = "all"  # Update collection name to reflect search scope
            
            return {
                "query": query,
                "collection": collection if not search_all_collections else "all",
                "results": results,
                "count": len(results)
            }
        
        @self.mcp.add_tool
        async def add_documents(
            documents: List[Dict[str, Any]],
            collection: str = "default"
        ) -> Dict[str, Any]:
            """Add documents to a collection.
            
            Args:
                documents: List of documents to add. Each document must have:
                    - id: string (required)
                    - text: string (required)
                    - metadata: object (optional)
                collection: Collection name (default: "default")
                
            Returns:
                Dictionary with add operation result
            """
            if not documents:
                raise ValueError("documents parameter is required")
            
            result = await self.vector_store.add_documents(
                collection_name=collection,
                documents=documents
            )
            
            return result
        
        @self.mcp.add_tool
        async def list_collections() -> Dict[str, Any]:
            """List all available collections.
            
            Returns:
                Dictionary with collections list and count
            """
            collections = self.vector_store.list_collections()
            
            # Get document counts for each collection if supported
            collection_details = []
            if hasattr(self.vector_store, 'get_collection_stats'):
                stats = self.vector_store.get_collection_stats()
                # Create a map of collection name to stats
                stats_map = {stat["name"]: stat["document_count"] for stat in stats}
                # Build detailed collection info
                for collection_name in collections:
                    collection_details.append({
                        "name": collection_name,
                        "document_count": stats_map.get(collection_name, 0)
                    })
            else:
                # Fallback: just collection names without counts
                collection_details = [{"name": name, "document_count": None} for name in collections]
            
            return {
                "collections": collection_details,
                "count": len(collections)
            }
        
        @self.mcp.add_tool
        async def delete_collection(collection: str) -> Dict[str, Any]:
            """Delete a collection and all its documents.
            
            Args:
                collection: Collection name to delete
                
            Returns:
                Dictionary with deletion result
            """
            if not collection:
                raise ValueError("collection parameter is required")
            
            try:
                success = self.vector_store.delete_collection(collection)
                
                if success:
                    return {
                        "collection": collection,
                        "deleted": True,
                        "message": f"Collection '{collection}' deleted successfully"
                    }
                else:
                    return {
                        "collection": collection,
                        "deleted": False,
                        "message": f"Collection '{collection}' not found or could not be deleted"
                    }
            except Exception as e:
                logger.error(f"Error deleting collection {collection}: {e}", exc_info=True)
                raise ValueError(f"Failed to delete collection '{collection}': {str(e)}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - close vector store."""
        if hasattr(self.vector_store, 'close'):
            self.vector_store.close()


def create_app():
    """Create FastAPI app instance."""
    server = VectorSearchMCPServer()
    return server.get_app()


def run_server():
    """Run the Vector Search MCP server."""
    server = VectorSearchMCPServer()
    server.run()


if __name__ == "__main__":
    run_server()
