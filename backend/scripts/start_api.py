"""Script to start the FastAPI API server."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import uvicorn
from config.settings import get_settings, clear_settings_cache


def main():
    """Start the API server."""
    # Clear cache to ensure fresh settings from .env
    clear_settings_cache()
    settings = get_settings()
    
    print(f"[INFO] Starting API server on {settings.api_host}:{settings.api_port}")
    print(f"[INFO] API will be available at: http://localhost:{settings.api_port}")
    print(f"[INFO] Documentation: http://localhost:{settings.api_port}/docs")
    print(f"[INFO] Make sure MCP servers are running!")
    print()
    
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower()
    )


if __name__ == "__main__":
    main()
