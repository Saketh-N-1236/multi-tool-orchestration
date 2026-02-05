"""Vector Search server tools with versioning."""

from typing import List, Dict, Any

# Tool version
TOOL_VERSION = "1.0.0"


def get_tools() -> List[Dict[str, Any]]:
    """Get list of vector search tools with versioning.
    
    Returns:
        List of tool definitions with version metadata
    """
    return [
        {
            "name": "search_documents",
            "tool_version": TOOL_VERSION,
            "description": "Search for documents using semantic similarity",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query text"
                    },
                    "collection": {
                        "type": "string",
                        "description": "Collection name to search in (default: 'default')",
                        "default": "default"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5, min: 1, max: 100)",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 100
                    },
                    "search_all_collections": {
                        "type": "boolean",
                        "description": "Whether to search across all collections (default: false)",
                        "default": False
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "add_documents",
            "tool_version": TOOL_VERSION,
            "description": "Add documents to a collection",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "collection": {
                        "type": "string",
                        "description": "Collection name",
                        "default": "default"
                    },
                    "documents": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "text": {"type": "string"},
                                "metadata": {"type": "object"}
                            },
                            "required": ["id", "text"]
                        },
                        "description": "List of documents to add"
                    }
                },
                "required": ["documents"]
            }
        },
        {
            "name": "list_collections",
            "tool_version": TOOL_VERSION,
            "description": "List all available collections",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "delete_collection",
            "tool_version": TOOL_VERSION,
            "description": "Delete a collection and all its documents",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "collection": {
                        "type": "string",
                        "description": "Collection name to delete"
                    }
                },
                "required": ["collection"]
            }
        }
    ]
