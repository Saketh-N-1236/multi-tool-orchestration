"""FastAPI main application with request ID middleware."""

import uuid
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from contextlib import asynccontextmanager
from pathlib import Path

from api.routes import router
from api.crud_routes import router as crud_router
from api.server_management_routes import router as server_management_router
from api.middleware import setup_middleware
from config.settings import get_settings, clear_settings_cache


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup - clear cache to ensure fresh settings are loaded from .env
    clear_settings_cache()
    # Force reload by getting fresh settings instance
    settings = get_settings()
    
    # Verify settings are loaded correctly
    from pathlib import Path
    import os
    env_path = Path(".env")
    
    # Read .env file directly to verify what's in it
    env_content = ""
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip().startswith('LLM_PROVIDER='):
                    env_content = line.strip()
                    break
    
    print(f"[INFO] Starting API server on {settings.api_host}:{settings.api_port}")
    print(f"[INFO] ===== LLM PROVIDER DEBUG =====")
    print(f"[INFO] LLM Provider from Settings: {settings.llm_provider}")
    print(f"[INFO] LLM Provider from .env file: {env_content}")
    print(f"[INFO] LLM Provider from OS env: {os.getenv('LLM_PROVIDER', 'NOT SET')}")
    print(f"[INFO] .env file path: {env_path.absolute()}")
    print(f"[INFO] .env file exists: {env_path.exists()}")
    print(f"[INFO] ===============================")
    print(f"[INFO] Embedding Provider: {settings.embedding_provider}")
    print(f"[INFO] MCP Servers:")
    print(f"  - Catalog: http://localhost:{settings.catalog_mcp_port}")
    print(f"  - Vector Search: http://localhost:{settings.vector_mcp_port}")
    print(f"  - SQL Query: http://localhost:{settings.sql_mcp_port}")
    
    yield
    
    # Shutdown
    print("[INFO] Shutting down API server")


def create_app() -> FastAPI:
    """Create and configure FastAPI application.
    
    Returns:
        Configured FastAPI app
    """
    # Clear cache before creating app to ensure fresh settings
    clear_settings_cache()
    settings = get_settings()
    
    app = FastAPI(
        title="Multi-Tool Orchestration API",
        description="API for multi-tool orchestration using MCP servers and LLM agents",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure as needed
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Request ID middleware - must be added first so it runs first
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        """Add request ID to request and response."""
        # Get request ID from header or generate new one
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        
        # Store in request state
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response header
        response.headers["X-Request-ID"] = request_id
        
        return response
    
    # Setup additional middleware (logging, rate limiting)
    setup_middleware(app)
    
    # Include routes
    app.include_router(router, prefix="/api/v1")
    app.include_router(crud_router)  # CRUD routes already have /api/v1 prefix
    app.include_router(server_management_router)  # Server management routes already have /api/v1 prefix
    
    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "name": "Multi-Tool Orchestration API",
            "version": "1.0.0",
            "status": "running",
            "docs": "/docs"
        }
    
    # Health check endpoint
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "version": "1.0.0"
        }
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
