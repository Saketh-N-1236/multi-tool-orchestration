"""Vector store implementation using ChromaDB with custom embeddings."""

import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid
from config.settings import get_settings
from llm.factory import LLMFactory
from llm.models import EmbeddingRequest

logger = logging.getLogger(__name__)

# Try to import ChromaDB
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
    
    # Suppress ChromaDB telemetry warnings
    # These warnings occur due to ChromaDB version compatibility issues with telemetry
    chromadb_logger = logging.getLogger("chromadb")
    chromadb_logger.setLevel(logging.ERROR)  # Only show errors, suppress warnings
    
    # Also suppress specific telemetry-related loggers
    telemetry_logger = logging.getLogger("chromadb.telemetry")
    telemetry_logger.setLevel(logging.CRITICAL)  # Suppress all telemetry messages
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None
    logger.warning(
        "ChromaDB is not installed. Install with: pip install chromadb>=0.4.0. "
        "Falling back to simple vector store."
    )


class ChromaDBVectorStore:
    """ChromaDB vector store with custom embeddings (Gemini/Ollama).
    
    ChromaDB is a lightweight, embedded vector database that works on all platforms
    including Windows, Linux, and macOS.
    """
    
    def __init__(self, store_path: Optional[str] = None):
        """Initialize ChromaDB vector store.
        
        Args:
            store_path: Path for ChromaDB data storage
        """
        self.settings = get_settings()
        self.store_path = Path(store_path or self.settings.chromadb_data_path)
        self.store_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize LLM provider for embeddings
        self.llm_provider = LLMFactory.create_embedding_provider(self.settings)
        
        # Initialize ChromaDB client
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "ChromaDB is not installed. Install with: pip install chromadb>=0.4.0"
            )
        
        self._client = None
        logger.info(
            f"Initializing ChromaDBVectorStore at {self.store_path}"
        )
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize ChromaDB client."""
        try:
            # ChromaDB uses persistent client for local storage
            # Disable telemetry completely to avoid warnings
            self._client = chromadb.PersistentClient(
                path=str(self.store_path),
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            logger.info(f"✅ Initialized ChromaDB at {self.store_path}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client: {e}", exc_info=True)
            raise
    
    def _get_collection_name(self, collection_name: str) -> str:
        """Get valid collection name that meets ChromaDB requirements.
        
        ChromaDB collection name requirements:
        1. Contains 3-63 characters
        2. Starts and ends with an alphanumeric character
        3. Otherwise contains only alphanumeric characters, underscores or hyphens (-)
        4. Contains no two consecutive periods (..)
        5. Is not a valid IPv4 address
        
        Args:
            collection_name: Original collection name
            
        Returns:
            Normalized collection name that meets ChromaDB requirements
        """
        if not collection_name:
            collection_name = "default"
        
        # Remove invalid characters, keep only alphanumeric, underscore, hyphen
        clean_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in collection_name)
        
        # Remove consecutive underscores/hyphens
        clean_name = re.sub(r'[_-]{2,}', '_', clean_name)
        
        # Remove leading/trailing non-alphanumeric characters
        clean_name = clean_name.strip('_-')
        
        # Ensure it starts and ends with alphanumeric
        if clean_name and not clean_name[0].isalnum():
            clean_name = 'c' + clean_name
        if clean_name and not clean_name[-1].isalnum():
            clean_name = clean_name + '1'
        
        # Ensure minimum length of 3 characters (ChromaDB requirement)
        if len(clean_name) < 3:
            # Pad with numbers to reach minimum length
            clean_name = clean_name.ljust(3, '0')
        
        # Ensure maximum length of 63 characters
        if len(clean_name) > 63:
            clean_name = clean_name[:63]
            # Ensure it still ends with alphanumeric
            if not clean_name[-1].isalnum():
                clean_name = clean_name[:-1] + '1'
        
        # Convert to lowercase for consistency
        clean_name = clean_name.lower()
        
        # Final validation: ensure it's not an IPv4 address pattern
        if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', clean_name):
            clean_name = 'collection_' + clean_name.replace('.', '_')
        
        return clean_name
    
    def _get_or_create_collection(self, collection_name: str, embedding_dimension: int = 768):
        """Get or create a ChromaDB collection.
        
        Args:
            collection_name: Collection name
            embedding_dimension: Dimension of embeddings (for metadata, ChromaDB handles this automatically)
            
        Returns:
            ChromaDB collection object
        """
        normalized_name = self._get_collection_name(collection_name)
        
        try:
            # Try to get existing collection
            collection = self._client.get_collection(name=normalized_name)
            logger.debug(f"Using existing ChromaDB collection: {normalized_name}")
        except Exception:
            # Collection doesn't exist, create it
            # Configure to use cosine distance for better similarity scores
            # ChromaDB supports: "l2", "ip" (inner product), "cosine"
            try:
                collection = self._client.create_collection(
                    name=normalized_name,
                    metadata={"description": f"Collection for {collection_name}"},
                    # Use cosine distance for normalized similarity scores
                    # Note: This requires embeddings to be normalized
                    # If not available, we'll handle L2 distance in conversion
                )
                logger.info(f"Created ChromaDB collection: {normalized_name}")
            except TypeError:
                # Older ChromaDB versions might not support distance_metric parameter
                # Create without it and handle conversion in search
                collection = self._client.create_collection(
                    name=normalized_name,
                    metadata={"description": f"Collection for {collection_name}"}
                )
                logger.info(f"Created ChromaDB collection: {normalized_name} (using default distance metric)")
        
        return collection
    
    async def add_documents(
        self,
        collection_name: str,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Add documents to a ChromaDB collection.
        
        Args:
            collection_name: Name of the collection
            documents: List of documents with id, text, and optional metadata
            
        Returns:
            Dictionary with add results
        """
        if not documents:
            return {
                "collection": collection_name,
                "added_count": 0,
                "total_documents": 0
            }
        
        # Get embeddings for all documents
        texts = [doc["text"] for doc in documents]
        embedding_request = EmbeddingRequest(texts=texts)
        embedding_response = await self.llm_provider.get_embeddings(embedding_request)
        
        # Determine embedding dimension from first embedding
        embedding_dimension = len(embedding_response.embeddings[0]) if embedding_response.embeddings else 768
        
        # Get normalized collection name
        normalized_name = self._get_collection_name(collection_name)
        
        # Get or create collection
        collection = self._get_or_create_collection(collection_name, embedding_dimension)
        
        # Normalize embeddings for better similarity scores
        # L2 normalize: divide by L2 norm
        try:
            import numpy as np
            normalized_embeddings = []
            for embedding in embedding_response.embeddings:
                emb_array = np.array(embedding, dtype=np.float32)
                norm = np.linalg.norm(emb_array)
                if norm > 0:
                    normalized_emb = (emb_array / norm).tolist()
                else:
                    normalized_emb = embedding  # Keep original if norm is 0
                normalized_embeddings.append(normalized_emb)
        except ImportError:
            # NumPy not available, use embeddings as-is
            logger.warning("NumPy not available, embeddings will not be normalized")
            normalized_embeddings = embedding_response.embeddings
        
        # Prepare data for ChromaDB
        ids = []
        embeddings = []
        metadatas = []
        
        for i, doc in enumerate(documents):
            doc_id = doc.get("id", str(uuid.uuid4()))
            embedding = normalized_embeddings[i]
            metadata = doc.get("metadata", {})
            
            # ChromaDB expects metadata as dict with string values
            chroma_metadata = {}
            for key, value in metadata.items():
                # Convert metadata values to strings (ChromaDB requirement)
                if isinstance(value, (str, int, float, bool)):
                    chroma_metadata[str(key)] = str(value)
                elif value is None:
                    chroma_metadata[str(key)] = ""
                else:
                    chroma_metadata[str(key)] = str(value)
            
            # Add doc_id to metadata for retrieval
            chroma_metadata["doc_id"] = doc_id
            
            # Add collection name to metadata for traceability
            chroma_metadata["collection_name"] = normalized_name
            
            ids.append(doc_id)
            embeddings.append(embedding)
            metadatas.append(chroma_metadata)
        
        # Add documents to ChromaDB
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
        
        # Get total count
        try:
            count_result = collection.count()
            total_count = count_result if isinstance(count_result, int) else len(documents)
        except Exception as e:
            logger.warning(f"Failed to get count from ChromaDB: {e}, using document count")
            total_count = len(documents)
        
        logger.info(
            f"Added {len(documents)} documents to ChromaDB collection '{normalized_name}' "
            f"(original name: '{collection_name}'). Total documents: {total_count}"
        )
        
        return {
            "collection": normalized_name,  # Return normalized name so client knows actual collection
            "original_collection": collection_name,  # Also return original for reference
            "added_count": len(documents),
            "total_documents": total_count
        }
    
    async def search(
        self,
        query: str,
        collection_name: str = "default",
        top_k: int = 5,
        search_all_collections: bool = False
    ) -> List[Dict[str, Any]]:
        """Search for similar documents using vector similarity.
        
        Args:
            query: Search query text
            collection_name: Collection to search in (ignored if search_all_collections=True)
            top_k: Number of results to return per collection
            search_all_collections: If True, search across all collections
            
        Returns:
            List of similar documents with scores
        """
        # If searching all collections, get results from each and merge
        if search_all_collections:
            all_results = []
            try:
                collections = self._client.list_collections()
                for col in collections:
                    try:
                        results = await self._search_in_collection(query, col.name, top_k)
                        all_results.extend(results)
                    except Exception as e:
                        logger.warning(f"Error searching collection {col.name}: {e}")
                
                # Sort all results by score and return top_k
                all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
                return all_results[:top_k]
            except Exception as e:
                logger.error(f"Error listing collections for search: {e}")
                return []
        
        # Single collection search
        normalized_name = self._get_collection_name(collection_name)
        return await self._search_in_collection(query, normalized_name, top_k)
    
    async def _search_in_collection(
        self,
        query: str,
        collection_name: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Search in a specific collection.
        
        Args:
            query: Search query text
            collection_name: Collection name (already normalized)
            top_k: Number of results to return
            
        Returns:
            List of similar documents with scores
        """
        # Check if collection exists
        try:
            collection = self._client.get_collection(name=collection_name)
        except Exception:
            logger.warning(f"Collection {collection_name} does not exist")
            return []
        
        # Get query embedding
        embedding_request = EmbeddingRequest(texts=[query])
        embedding_response = await self.llm_provider.get_embeddings(embedding_request)
        query_vector = embedding_response.embeddings[0]
        
        # Normalize query embedding to match stored embeddings
        try:
            import numpy as np
            query_array = np.array(query_vector, dtype=np.float32)
            norm = np.linalg.norm(query_array)
            if norm > 0:
                query_vector = (query_array / norm).tolist()
        except ImportError:
            # NumPy not available, use embedding as-is
            pass
        
        # Perform vector search
        try:
            results = collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )
            
            # Parse results
            parsed_results = []
            if results.get("ids") and len(results["ids"]) > 0:
                for i in range(len(results["ids"][0])):
                    doc_id = results["ids"][0][i]
                    text = results["documents"][0][i] if results.get("documents") else ""
                    metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                    distance = results["distances"][0][i] if results.get("distances") else 0.0
                    
                    # Convert distance to similarity score
                    # ChromaDB can use different distance metrics:
                    # - Cosine distance: [0, 2] where 0 = identical, 2 = opposite
                    # - L2 (Euclidean) distance: [0, ∞] where 0 = identical, larger = more different
                    # - Inner product: can be negative or positive
                    if distance is not None:
                        distance_float = float(distance)
                        
                        # Detect distance metric based on value range
                        if distance_float <= 2.0:
                            # Likely cosine distance [0, 2]
                            # Convert to similarity: similarity = 1 - (distance / 2)
                            similarity = 1.0 - (distance_float / 2.0)
                        elif distance_float <= 1.0:
                            # Might be normalized cosine or L2
                            similarity = 1.0 - distance_float
                        else:
                            # Likely L2 (Euclidean) distance - can be very large
                            # For L2, we need to normalize. Use inverse distance with scaling
                            # Common approach: similarity = 1 / (1 + distance)
                            # Or normalize by a reasonable max distance (e.g., sqrt(embedding_dim * 2))
                            # For 768-dim embeddings, max L2 distance ≈ sqrt(768 * 4) ≈ 55
                            # But distances can be larger, so use a more robust formula
                            
                            # Method 1: Inverse distance (works for any L2 distance)
                            # similarity = 1.0 / (1.0 + distance_float)
                            
                            # Method 2: Normalize by estimated max distance
                            # For normalized embeddings, max L2 distance is typically 2-4
                            # For unnormalized, it can be much larger
                            # Use a sigmoid-like function: similarity = 1 / (1 + distance/scale)
                            # Scale factor: for typical embedding distances, use 10-50
                            scale_factor = 50.0  # Adjust based on typical L2 distances
                            similarity = 1.0 / (1.0 + (distance_float / scale_factor))
                            
                            # Clamp to [0, 1] range
                            similarity = max(0.0, min(1.0, similarity))
                    else:
                        similarity = 0.0
                    
                    # Get original doc_id from metadata if available
                    original_id = metadata.get("doc_id", doc_id)
                    
                    parsed_results.append({
                        "id": original_id,
                        "text": text,
                        "score": max(0.0, min(1.0, similarity)),  # Clamp between 0 and 1
                        "distance": float(distance) if distance is not None else 0.0,
                        "metadata": {k: v for k, v in metadata.items() if k != "doc_id"},
                        "collection": collection_name  # Include collection name in results
                    })
            
            return parsed_results
            
        except Exception as e:
            logger.error(f"Error searching ChromaDB collection {collection_name}: {e}", exc_info=True)
            return []
    
    def list_collections(self) -> List[str]:
        """List all collection names.
        
        Returns:
            List of collection names
        """
        try:
            collections = self._client.list_collections()
            # Extract collection names
            collection_names = [col.name for col in collections]
            return collection_names
        except Exception as e:
            logger.error(f"Error listing ChromaDB collections: {e}")
            return []
    
    def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection.
        
        Args:
            collection_name: Name of collection to delete
            
        Returns:
            True if collection was deleted, False otherwise
        """
        try:
            normalized_name = self._get_collection_name(collection_name)
            
            # Check if collection exists before trying to delete
            collections = self._client.list_collections()
            collection_names = [col.name for col in collections]
            
            if normalized_name not in collection_names:
                logger.warning(f"Collection '{normalized_name}' not found, cannot delete")
                return False
            
            self._client.delete_collection(name=normalized_name)
            logger.info(f"Deleted collection: {normalized_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting ChromaDB collection {collection_name}: {e}", exc_info=True)
            # Re-raise the exception so the caller can handle it
            raise
    
    def get_collection_stats(self) -> List[Dict[str, Any]]:
        """Get statistics for all collections including document counts.
        
        Returns:
            List of dictionaries with collection name and document count
        """
        try:
            collections = self._client.list_collections()
            collection_stats = []
            
            for col in collections:
                collection_name = col.name
                try:
                    count = col.count()
                    collection_stats.append({
                        "name": collection_name,
                        "document_count": count
                    })
                except Exception as e:
                    logger.warning(f"Failed to get count for collection {collection_name}: {e}")
                    collection_stats.append({
                        "name": collection_name,
                        "document_count": 0,
                        "error": str(e)
                    })
            
            return collection_stats
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return []
    
    def close(self):
        """Close ChromaDB client connection."""
        if self._client:
            try:
                # ChromaDB PersistentClient doesn't need explicit close
                # but we can clean up references
                del self._client
                self._client = None
            except Exception as e:
                logger.warning(f"Error closing ChromaDB client: {e}")


# SimpleVectorStore fallback (JSON-based)
import json
import numpy as np

class SimpleVectorStore:
    """Simple in-memory vector store using JSON files (fallback)."""
    
    def __init__(self, store_path: Optional[str] = None):
        """Initialize simple vector store.
        
        Args:
            store_path: Path for JSON file storage
        """
        self.settings = get_settings()
        self.store_path = Path(store_path or self.settings.vector_store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize LLM provider for embeddings
        self.llm_provider = LLMFactory.create_embedding_provider(self.settings)
        
        # Load existing collections
        self._collections: Dict[str, Dict[str, Any]] = {}
        self._load_collections()
        
        logger.info(
            f"⚠️  Using SimpleVectorStore - data will be saved to JSON files in {self.store_path}. "
            "This is a fallback. For production, use ChromaDB."
        )
    
    def _load_collections(self):
        """Load collections from JSON files."""
        for json_file in self.store_path.glob("*.json"):
            collection_name = json_file.stem
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    self._collections[collection_name] = json.load(f)
                logger.debug(f"Loaded collection {collection_name} from {json_file}")
            except Exception as e:
                logger.warning(f"Failed to load collection {collection_name}: {e}")
    
    def _save_collection(self, collection_name: str):
        """Save collection to JSON file."""
        json_file = self.store_path / f"{collection_name}.json"
        try:
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(self._collections[collection_name], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save collection {collection_name}: {e}")
    
    async def add_documents(self, collection_name: str, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        if collection_name not in self._collections:
            self._collections[collection_name] = {}
        
        texts = [doc["text"] for doc in documents]
        embedding_request = EmbeddingRequest(texts=texts)
        embedding_response = await self.llm_provider.get_embeddings(embedding_request)
        
        for i, doc in enumerate(documents):
            doc_id = doc.get("id", str(uuid.uuid4()))
            self._collections[collection_name][doc_id] = {
                "text": doc["text"],
                "embedding": embedding_response.embeddings[i],
                "metadata": doc.get("metadata", {})
            }
        
        self._save_collection(collection_name)
        
        return {
            "collection": collection_name,
            "added_count": len(documents),
            "total_documents": len(self._collections[collection_name])
        }
    
    async def search(self, query: str, collection_name: str = "default", top_k: int = 5) -> List[Dict[str, Any]]:
        if collection_name not in self._collections:
            return []
        embedding_request = EmbeddingRequest(texts=[query])
        embedding_response = await self.llm_provider.get_embeddings(embedding_request)
        query_embedding = np.array(embedding_response.embeddings[0])
        results = []
        collection = self._collections[collection_name]
        for doc_id, doc_data in collection.items():
            doc_embedding = np.array(doc_data["embedding"])
            similarity = np.dot(query_embedding, doc_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(doc_embedding)
            )
            results.append({
                "id": doc_id,
                "text": doc_data["text"],
                "score": float(similarity),
                "metadata": doc_data.get("metadata", {})
            })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    def list_collections(self) -> List[str]:
        return list(self._collections.keys())
    
    def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection.
        
        Args:
            collection_name: Name of collection to delete
            
        Returns:
            True if collection was deleted, False otherwise
        """
        if collection_name in self._collections:
            del self._collections[collection_name]
            # Delete JSON file if it exists
            json_file = self.store_path / f"{collection_name}.json"
            if json_file.exists():
                try:
                    json_file.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete collection file {json_file}: {e}")
            return True
        return False
    
    def get_collection_stats(self) -> List[Dict[str, Any]]:
        """Get statistics for all collections including document counts.
        
        Returns:
            List of dictionaries with collection name and document count
        """
        collection_stats = []
        for collection_name, collection_data in self._collections.items():
            document_count = len(collection_data) if isinstance(collection_data, dict) else 0
            collection_stats.append({
                "name": collection_name,
                "document_count": document_count
            })
        return collection_stats
    
    def close(self):
        pass


# Choose vector store implementation
if CHROMADB_AVAILABLE:
    try:
        # Try to create ChromaDB instance to verify it works
        VectorStore = ChromaDBVectorStore
        logger.info("✅ Using ChromaDBVectorStore as primary vector store")
    except Exception as e:
        logger.warning(f"ChromaDB available but initialization failed: {e}. Falling back to SimpleVectorStore.")
        VectorStore = SimpleVectorStore
else:
    VectorStore = SimpleVectorStore
    logger.warning("⚠️  ChromaDB not available. Using SimpleVectorStore (JSON files) as fallback.")
