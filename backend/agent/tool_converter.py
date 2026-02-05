"""Tool converter: MCP tools to LangChain StructuredTool.

This module converts MCP tool schemas (from MCP SDK) to LangChain StructuredTool
for use with LangGraph's ToolNode.
"""

from typing import Dict, Any, List, Optional, Callable
import json
import logging

try:
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, create_model, Field
    from mcp.types import Tool as MCPTool
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    StructuredTool = None
    MCPTool = None

logger = logging.getLogger(__name__)


def json_schema_to_pydantic(json_schema: Dict[str, Any]) -> type[BaseModel]:
    """Convert JSON Schema to a Pydantic model.
    
    Args:
        json_schema: JSON Schema dictionary
        
    Returns:
        Pydantic model class
    """
    if not LANGCHAIN_AVAILABLE:
        raise ImportError("LangChain is required for tool conversion")
    
    # Extract properties from JSON Schema
    properties = json_schema.get("properties", {})
    required = json_schema.get("required", [])
    
    # Build field definitions
    field_definitions: Dict[str, tuple] = {}
    
    for prop_name, prop_schema in properties.items():
        prop_type = prop_schema.get("type", "string")
        prop_description = prop_schema.get("description", "")
        is_required = prop_name in required
        
        # Map JSON Schema types to Python types
        if prop_type == "string":
            python_type = str
        elif prop_type == "integer":
            python_type = int
        elif prop_type == "number":
            python_type = float
        elif prop_type == "boolean":
            python_type = bool
        elif prop_type == "array":
            # Handle array items - check if items schema is defined
            items_schema = prop_schema.get("items", {})
            if items_schema:
                # If items have a type, use List[type]
                item_type = items_schema.get("type", "string")
                if item_type == "string":
                    python_type = List[str]
                elif item_type == "integer":
                    python_type = List[int]
                elif item_type == "number":
                    python_type = List[float]
                elif item_type == "object":
                    # For complex objects, use List[dict]
                    python_type = List[Dict[str, Any]]
                else:
                    python_type = List[Any]
            else:
                # No items schema, use generic list
                python_type = List[Any]
        elif prop_type == "object":
            python_type = Dict[str, Any]
        else:
            python_type = str  # Default to string
        
        # Get default value from schema if available
        default_value = prop_schema.get("default")
        has_default = "default" in prop_schema
        
        # Create field with description and default
        if is_required:
            field_definitions[prop_name] = (
                python_type,
                Field(description=prop_description)
            )
        else:
            # Use default from schema if provided, otherwise None
            if has_default and default_value is not None:
                # Convert default to appropriate type
                if prop_type == "integer" and isinstance(default_value, (int, float)):
                    default_value = int(default_value)
                elif prop_type == "number" and isinstance(default_value, (int, float)):
                    default_value = float(default_value)
                elif prop_type == "boolean" and isinstance(default_value, bool):
                    default_value = bool(default_value)
                elif prop_type == "string" and isinstance(default_value, str):
                    default_value = str(default_value)
                
                field_definitions[prop_name] = (
                    Optional[python_type],
                    Field(default=default_value, description=prop_description)
                )
            else:
                field_definitions[prop_name] = (
                    Optional[python_type],
                    Field(default=None, description=prop_description)
                )
    
    # Create Pydantic model dynamically
    if field_definitions:
        model = create_model(
            "ToolInput",
            **field_definitions
        )
    else:
        # Empty model if no properties
        model = create_model("ToolInput")
    
    return model


def mcp_tool_to_langchain(
    mcp_tool: MCPTool,
    server_name: str,
    tool_executor: Callable
) -> StructuredTool:
    """Convert an MCP tool to a LangChain StructuredTool.
    
    Args:
        mcp_tool: MCP Tool object from SDK
        server_name: Name of the MCP server
        tool_executor: Async function that executes the tool
        
    Returns:
        LangChain StructuredTool
    """
    if not LANGCHAIN_AVAILABLE:
        raise ImportError("LangChain is required for tool conversion")
    
    # Extract tool schema
    input_schema = mcp_tool.inputSchema if hasattr(mcp_tool, "inputSchema") else {}
    
    # Convert JSON Schema to Pydantic model
    try:
        args_schema = json_schema_to_pydantic(input_schema)
    except Exception as e:
        logger.warning(
            f"Failed to convert schema for tool '{mcp_tool.name}': {e}. "
            f"Using dict schema as fallback."
        )
        args_schema = dict
    
    # Create tool name with server prefix (use underscore instead of :: for Gemini compatibility)
    full_tool_name = f"{server_name}_{mcp_tool.name}"
    
    # Create the tool function
    async def tool_func(**kwargs: Any) -> str:
        """Execute the tool via MCP SDK."""
        try:
            # Validate and apply defaults using the Pydantic model if available
            # This ensures default values from JSON Schema are applied
            if args_schema != dict:
                try:
                    # Filter out None values - if a parameter is None, it means it wasn't provided
                    # and we should let Pydantic apply the default value
                    filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
                    
                    # Create instance of args_schema to validate and apply defaults
                    # Pydantic will automatically apply default values for optional fields
                    validated_args = args_schema(**filtered_kwargs)
                    # Convert Pydantic model to dict for tool execution (Pydantic v2)
                    kwargs = validated_args.model_dump(exclude_unset=False)
                    logger.debug(f"Tool '{full_tool_name}' validated args: {kwargs}")
                except Exception as validation_error:
                    logger.warning(
                        f"Tool argument validation failed for '{full_tool_name}': {validation_error}. "
                        f"Provided kwargs: {kwargs}. This may cause tool execution to fail."
                    )
                    # Re-raise validation error so it's caught and returned as tool error
                    raise
            
            result = await tool_executor(server_name, mcp_tool.name, kwargs)
            
            # Extract result text
            if isinstance(result, dict):
                if result.get("isError"):
                    error_msg = result.get("error", "Unknown error")
                    return f"Error: {error_msg}"
                return str(result.get("result", ""))
            return str(result)
        except Exception as e:
            logger.error(f"Tool execution failed: {e}", exc_info=True)
            return f"Error: {str(e)}"
    
    # Create StructuredTool
    tool = StructuredTool(
        name=full_tool_name,
        description=mcp_tool.description or f"Tool: {mcp_tool.name}",
        args_schema=args_schema,
        func=tool_func,
        coroutine=tool_func  # Async version
    )
    
    return tool


def convert_mcp_tools_to_langchain(
    mcp_tools: Dict[str, List[MCPTool]],
    tool_executor: Callable
) -> List[StructuredTool]:
    """Convert multiple MCP tools to LangChain StructuredTools.
    
    Args:
        mcp_tools: Dictionary mapping server names to their tools
        tool_executor: Async function that executes tools
        
    Returns:
        List of LangChain StructuredTool objects
    """
    langchain_tools: List[StructuredTool] = []
    
    for server_name, tools in mcp_tools.items():
        for mcp_tool in tools:
            try:
                langchain_tool = mcp_tool_to_langchain(
                    mcp_tool,
                    server_name,
                    tool_executor
                )
                langchain_tools.append(langchain_tool)
            except Exception as e:
                logger.error(
                    f"Failed to convert tool '{mcp_tool.name}' from server '{server_name}': {e}",
                    exc_info=True
                )
    
    logger.info(
        f"Converted {len(langchain_tools)} MCP tools to LangChain StructuredTools"
    )
    
    return langchain_tools
