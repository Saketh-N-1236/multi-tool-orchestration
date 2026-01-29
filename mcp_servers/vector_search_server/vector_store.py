"""Vector store implementation using simple in-memory storage with Gemini embeddings."""

import json
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
import numpy as np
from config.settings import get_settings
from llm.factory import LLMFactory
from llm.models import EmbeddingRequest


class SimpleVectorStore:
    """Simple in-memory vector store with Gemini embeddings.
    
    This is a lightweight implementation that doesn't require ChromaDB.
    For production use, consider migrating to ChromaDB when available.
    """
    
    def __init__(self, store_path: Optional[str] = None):
        """Initialize vector store.
        
        Args:
            store_path: Path to store vector data
        """
        self.settings = get_settings()
        self.store_path = Path(store_path or self.settings.vector_store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize LLM provider for embeddings
        self.llm_provider = LLMFactory.create_embedding_provider(self.settings)
        
        # In-memory storage: {collection_name: {doc_id: {text, embedding, metadata}}}
        self._collections: Dict[str, Dict[str, Dict[str, Any]]] = {}
        
        # Load existing data if available
        self._load_data()
    
    def _get_collection_file(self, collection_name: str) -> Path:
        """Get file path for collection data."""
        return self.store_path / f"{collection_name}.json"
    
    def _load_data(self):
        """Load collections from disk."""
        if not self.store_path.exists():
            return
        
        for file_path in self.store_path.glob("*.json"):
            collection_name = file_path.stem
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._collections[collection_name] = data
            except Exception as e:
                print(f"Warning: Failed to load collection {collection_name}: {e}")
    
    def _save_collection(self, collection_name: str):
        """Save collection to disk."""
        if collection_name in self._collections:
            file_path = self._get_collection_file(collection_name)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self._collections[collection_name], f, indent=2)
    
    async def add_documents(
        self,
        collection_name: str,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Add documents to a collection.
        
        Args:
            collection_name: Name of the collection
            documents: List of documents with id, text, and optional metadata
            
        Returns:
            Dictionary with add results
        """
        if collection_name not in self._collections:
            self._collections[collection_name] = {}
        
        # Get embeddings for all documents
        texts = [doc["text"] for doc in documents]
        embedding_request = EmbeddingRequest(texts=texts)
        embedding_response = await self.llm_provider.get_embeddings(embedding_request)
        
        # Store documents with embeddings
        added_count = 0
        for i, doc in enumerate(documents):
            doc_id = doc.get("id", f"doc_{len(self._collections[collection_name])}")
            self._collections[collection_name][doc_id] = {
                "text": doc["text"],
                "embedding": embedding_response.embeddings[i],
                "metadata": doc.get("metadata", {})
            }
            added_count += 1
        
        # Save to disk
        self._save_collection(collection_name)
        
        return {
            "collection": collection_name,
            "added_count": added_count,
            "total_documents": len(self._collections[collection_name])
        }
    
    async def search(
        self,
        query: str,
        collection_name: str = "default",
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for similar documents.
        
        Args:
            query: Search query text
            collection_name: Collection to search in
            top_k: Number of results to return
            
        Returns:
            List of similar documents with scores
        """
        if collection_name not in self._collections:
            return []
        
        # Get query embedding
        embedding_request = EmbeddingRequest(texts=[query])
        embedding_response = await self.llm_provider.get_embeddings(embedding_request)
        query_embedding = np.array(embedding_response.embeddings[0])
        
        # Calculate similarities
        results = []
        collection = self._collections[collection_name]
        
        for doc_id, doc_data in collection.items():
            doc_embedding = np.array(doc_data["embedding"])
            
            # Cosine similarity
            similarity = np.dot(query_embedding, doc_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(doc_embedding)
            )
            
            results.append({
                "id": doc_id,
                "text": doc_data["text"],
                "score": float(similarity),
                "metadata": doc_data.get("metadata", {})
            })
        
        # Sort by score (descending) and return top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    def list_collections(self) -> List[str]:
        """List all collection names.
        
        Returns:
            List of collection names
        """
        return list(self._collections.keys())
