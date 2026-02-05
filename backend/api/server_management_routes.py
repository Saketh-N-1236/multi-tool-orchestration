"""Server management API routes for dynamic MCP server configuration."""

import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, List, Optional
import logging
from pathlib import Path

from config.settings import get_settings, clear_settings_cache
from agent.mcp_sdk_client import MCPSDKClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Server Management"])
settings = get_settings()

# Server configuration file path
SERVER_CONFIG_FILE = Path("backend/data/server_configs.json")


class AddServerRequest(BaseModel):
    """Request model for adding a server."""
    name: str = Field(..., description="Server name")
    url: str = Field(..., description="Server SSE URL (e.g., http://localhost:7004/sse)")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate server name."""
        if not v or not v.strip():
            raise ValueError("Server name cannot be empty")
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError("Server name must contain only alphanumeric characters, underscores, or hyphens")
        return v.strip()
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate server URL."""
        if not v or not v.strip():
            raise ValueError("Server URL cannot be empty")
        if not v.startswith(('http://', 'https://')):
            raise ValueError("Server URL must start with http:// or https://")
        if not v.endswith('/sse'):
            raise ValueError("Server URL must end with /sse")
        return v.strip()


def load_server_configs() -> Dict[str, str]:
    """Load server configurations from file.
    
    Returns:
        Dictionary mapping server names to URLs
    """
    if SERVER_CONFIG_FILE.exists():
        try:
            with open(SERVER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load server configs: {e}")
            return {}
    return {}


def save_server_configs(configs: Dict[str, str]):
    """Save server configurations to file.
    
    Args:
        configs: Dictionary mapping server names to URLs
    """
    try:
        SERVER_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SERVER_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(configs, f, indent=2)
        logger.info(f"Saved {len(configs)} server configuration(s) to {SERVER_CONFIG_FILE}")
    except Exception as e:
        logger.error(f"Failed to save server configs: {e}")
        raise


def get_all_servers() -> Dict[str, str]:
    """Get all server configurations (hardcoded + additional).
    
    Returns:
        Dictionary mapping server names to URLs
    """
    # Hardcoded servers
    hardcoded = {
        "catalog": f"http://localhost:{settings.catalog_mcp_port}/sse",
        "sql_query": f"http://localhost:{settings.sql_mcp_port}/sse",
        "vector_search": f"http://localhost:{settings.vector_mcp_port}/sse",
    }
    
    # Additional servers from file
    additional = load_server_configs()
    
    # Merge (additional takes precedence for conflicts, but hardcoded are protected)
    all_servers = {**hardcoded, **additional}
    
    return all_servers


@router.get("/servers", response_model=Dict[str, Any])
async def list_servers():
    """List all configured MCP servers."""
    servers = get_all_servers()
    
    server_list = []
    for name, url in servers.items():
        server_list.append({
            "name": name,
            "url": url,
            "type": "hardcoded" if name in ["catalog", "sql_query", "vector_search"] else "additional"
        })
    
    return {
        "servers": server_list,
        "count": len(server_list),
        "hardcoded": 3,
        "additional": len(server_list) - 3
    }


@router.post("/servers", response_model=Dict[str, Any])
async def add_server(request: AddServerRequest):
    """Add a new MCP server configuration."""
    # Check if server name conflicts with hardcoded servers
    hardcoded_names = ["catalog", "sql_query", "vector_search"]
    if request.name in hardcoded_names:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot add server '{request.name}' - it conflicts with a hardcoded server name"
        )
    
    # Load existing configs
    configs = load_server_configs()
    
    # Check if server already exists
    if request.name in configs:
        raise HTTPException(
            status_code=409,
            detail=f"Server '{request.name}' already exists"
        )
    
    # Add new server
    configs[request.name] = request.url
    save_server_configs(configs)
    
    # Update settings (for current session)
    # Note: This won't persist to .env, but will work for current session
    # For persistence, user should update .env file or use the config file
    
    logger.info(f"Added MCP server '{request.name}' at {request.url}")
    
    return {
        "name": request.name,
        "url": request.url,
        "added": True,
        "message": "Server added. Restart the API server for changes to take effect."
    }


@router.delete("/servers/{server_name}", response_model=Dict[str, Any])
async def remove_server(server_name: str):
    """Remove an MCP server configuration."""
    # Check if trying to remove hardcoded server
    hardcoded_names = ["catalog", "sql_query", "vector_search"]
    if server_name in hardcoded_names:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot remove hardcoded server '{server_name}'"
        )
    
    # Load existing configs
    configs = load_server_configs()
    
    # Check if server exists
    if server_name not in configs:
        raise HTTPException(
            status_code=404,
            detail=f"Server '{server_name}' not found"
        )
    
    # Remove server
    del configs[server_name]
    save_server_configs(configs)
    
    logger.info(f"Removed MCP server '{server_name}'")
    
    return {
        "name": server_name,
        "removed": True,
        "message": "Server removed. Restart the API server for changes to take effect."
    }


@router.get("/servers/{server_name}/status", response_model=Dict[str, Any])
async def get_server_status(server_name: str):
    """Check status of an MCP server."""
    servers = get_all_servers()
    
    if server_name not in servers:
        raise HTTPException(
            status_code=404,
            detail=f"Server '{server_name}' not found"
        )
    
    server_url = servers[server_name]
    
    # Try to connect to server
    import httpx
    status = "unknown"
    error = None
    
    try:
        # Try health check endpoint
        health_url = server_url.replace('/sse', '/health')
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(health_url)
            if response.status_code == 200:
                status = "online"
            else:
                status = "offline"
                error = f"Health check returned status {response.status_code}"
    except httpx.TimeoutException:
        status = "offline"
        error = "Connection timeout"
    except Exception as e:
        status = "offline"
        error = str(e)
    
    return {
        "name": server_name,
        "url": server_url,
        "status": status,
        "error": error
    }
