"""Text chunking utility for splitting documents into smaller chunks."""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    min_chunk_size: int = 100
) -> List[str]:
    """Split text into chunks with overlap.
    
    Args:
        text: Text to chunk
        chunk_size: Maximum size of each chunk in characters
        chunk_overlap: Number of characters to overlap between chunks
        min_chunk_size: Minimum size of a chunk (smaller chunks are merged)
        
    Returns:
        List of text chunks
    """
    if not text or len(text.strip()) == 0:
        return []
    
    # If text is smaller than chunk_size, return as single chunk
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        # Calculate end position
        end = start + chunk_size
        
        # If this is the last chunk, take all remaining text
        if end >= len(text):
            chunk = text[start:]
            if chunk.strip():  # Only add non-empty chunks
                chunks.append(chunk)
            break
        
        # Try to break at sentence boundary (period, exclamation, question mark)
        # Look for sentence endings within the last 20% of the chunk
        search_start = max(start, end - int(chunk_size * 0.2))
        sentence_endings = ['.', '!', '?', '\n\n', '\n']
        
        best_break = end
        for ending in sentence_endings:
            # Find last occurrence of sentence ending in the search range
            pos = text.rfind(ending, search_start, end)
            if pos != -1 and pos > start:
                # Found a sentence boundary, break there
                best_break = pos + len(ending)
                break
        
        # Extract chunk
        chunk = text[start:best_break].strip()
        
        # Only add if chunk meets minimum size (unless it's the last chunk)
        if len(chunk) >= min_chunk_size or best_break >= len(text):
            if chunk:  # Only add non-empty chunks
                chunks.append(chunk)
        
        # Move start position with overlap
        start = best_break - chunk_overlap
        if start < 0:
            start = 0
        
        # Prevent infinite loop
        if start >= len(text):
            break
    
    # If no chunks were created, return the whole text as a single chunk
    if not chunks:
        return [text]
    
    return chunks


async def chunk_document(
    doc: Dict[str, Any],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    min_chunk_size: int = 100
) -> List[Dict[str, Any]]:
    """Chunk a document into multiple document chunks with metadata.
    
    Args:
        doc: Document dictionary with 'id', 'text', and optional 'metadata'
        chunk_size: Maximum size of each chunk in characters
        chunk_overlap: Number of characters to overlap between chunks
        min_chunk_size: Minimum size of a chunk
        
    Returns:
        List of chunked documents with enhanced metadata
    """
    doc_id = doc.get("id", "unknown")
    text = doc.get("text", "")
    original_metadata = doc.get("metadata", {})
    
    # Chunk the text (run in thread pool to avoid blocking event loop)
    import asyncio
    loop = asyncio.get_event_loop()
    text_chunks = await loop.run_in_executor(
        None,
        lambda: chunk_text(text, chunk_size, chunk_overlap, min_chunk_size)
    )
    
    # If no chunking needed, return original document
    if len(text_chunks) <= 1:
        return [doc]
    
    # Create chunked documents
    chunked_docs = []
    total_chunks = len(text_chunks)
    
    for idx, text_chunk in enumerate(text_chunks, start=1):
        # Create chunk ID
        chunk_id = f"{doc_id}_chunk_{idx}"
        
        # Create metadata for this chunk
        chunk_metadata = original_metadata.copy()
        chunk_metadata.update({
            "chunk_index": str(idx),
            "total_chunks": str(total_chunks),
            "original_doc_id": doc_id,
            "is_chunk": "true"
        })
        
        # Preserve file name if present
        if "source" in original_metadata:
            chunk_metadata["file_name"] = original_metadata["source"]
        
        chunked_docs.append({
            "id": chunk_id,
            "text": text_chunk,
            "metadata": chunk_metadata
        })
    
    logger.info(
        f"Chunked document '{doc_id}' into {total_chunks} chunks "
        f"(chunk_size={chunk_size}, overlap={chunk_overlap})"
    )
    
    return chunked_docs
