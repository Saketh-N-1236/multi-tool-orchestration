"""SQL Query server tools with versioning."""

from typing import List, Dict, Any

# Tool version
TOOL_VERSION = "1.0.0"


def get_tools() -> List[Dict[str, Any]]:
    """Get list of SQL query tools with versioning.
    
    Returns:
        List of tool definitions with version metadata
    """
    return [
        {
            "name": "execute_query",
            "tool_version": TOOL_VERSION,
            "description": "Execute a read-only SQL SELECT query",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL SELECT query to execute (read-only)"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "explain_query",
            "tool_version": TOOL_VERSION,
            "description": "Get execution plan for a SQL SELECT query",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL SELECT query to explain (read-only)"
                    }
                },
                "required": ["query"]
            }
        }
    ]
