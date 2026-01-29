"""Tool result normalization layer."""

from typing import Any, Dict, Optional
from datetime import datetime


def normalize_result(
    result: Any,
    tool_name: str,
    tool_version: str = "1.0.0",
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """Normalize tool result to consistent format.
    
    Args:
        result: Tool execution result (can be data or Exception)
        tool_name: Name of the tool
        tool_version: Version of the tool
        request_id: Request ID for correlation
        
    Returns:
        Normalized result dictionary
    """
    if isinstance(result, Exception):
        return {
            "status": "error",
            "data": None,
            "metadata": {
                "tool_name": tool_name,
                "tool_version": tool_version,
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat()
            },
            "error": {
                "type": type(result).__name__,
                "message": str(result)
            }
        }
    
    return {
        "status": "success",
        "data": result,
        "metadata": {
            "tool_name": tool_name,
            "tool_version": tool_version,
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat()
        },
        "error": None
    }
