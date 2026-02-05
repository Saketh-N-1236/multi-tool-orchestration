"""Catalog server tools with versioning."""

from typing import List, Dict, Any

# Tool version
TOOL_VERSION = "1.0.0"


def get_tools() -> List[Dict[str, Any]]:
    """Get list of catalog tools with versioning.
    
    Returns:
        List of tool definitions with version metadata
    """
    return [
        {
            "name": "list_tables",
            "tool_version": TOOL_VERSION,
            "description": "List all tables in the database",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "describe_table",
            "tool_version": TOOL_VERSION,
            "description": "Get schema information for a specific table",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Name of the table to describe"
                    }
                },
                "required": ["table_name"]
            }
        },
        {
            "name": "get_table_row_count",
            "tool_version": TOOL_VERSION,
            "description": "Get the number of rows in a table",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Name of the table"
                    }
                },
                "required": ["table_name"]
            }
        }
    ]
