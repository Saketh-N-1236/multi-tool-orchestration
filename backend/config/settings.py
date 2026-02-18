"""Application settings with multi-provider LLM support."""

from typing import Optional, Any
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from functools import lru_cache

# Get absolute path to .env file (relative to this file's directory)
# backend/config/settings.py -> backend/config/ -> backend/ -> .env
_env_file_path = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Configure Pydantic Settings to load from .env file
    # Use absolute path to ensure it works regardless of working directory
    model_config = SettingsConfigDict(
        env_file=str(_env_file_path),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra fields in .env
    )
    
    # LLM Provider Selection
    # Set LLM_PROVIDER in .env file: gemini, openai, anthropic, or ollama
    # Default: "ollama" (for local testing) - change in .env as needed
    llm_provider: str = "gemini"  # Options: gemini, openai, anthropic, ollama
    
    @field_validator('llm_provider')
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        """Validate LLM provider is one of the supported options."""
        valid_providers = ["gemini", "openai", "anthropic", "ollama"]
        if v.lower() not in valid_providers:
            raise ValueError(
                f"Invalid LLM provider: {v}. "
                f"Must be one of: {', '.join(valid_providers)}. "
                f"Set LLM_PROVIDER in .env file."
            )
        return v.lower()
    
    # Embedding Provider Selection (can be different from LLM provider)
    # Set EMBEDDING_PROVIDER in .env file: gemini or ollama
    # Default: "ollama" (for local testing) - change in .env as needed
    embedding_provider: str = "ollama"  # Options: gemini, ollama
    
    @field_validator('embedding_provider')
    @classmethod
    def validate_embedding_provider(cls, v: str) -> str:
        """Validate embedding provider is one of the supported options."""
        valid_providers = ["gemini", "ollama"]
        if v.lower() not in valid_providers:
            raise ValueError(
                f"Invalid embedding provider: {v}. "
                f"Must be one of: {', '.join(valid_providers)}. "
                f"Set EMBEDDING_PROVIDER in .env file."
            )
        return v.lower()
    
    # Gemini Configuration
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-pro"
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4"
    
    # Anthropic Configuration
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    
    # Ollama Configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_timeout: int = 300  # Timeout in seconds (5 minutes for model loading)
    
    # LLM Parameters (provider-agnostic)
    llm_temperature: float = 0.7
    llm_max_tokens: int = 500
    llm_top_p: Optional[float] = None
    
    @field_validator('llm_top_p', mode='before')
    @classmethod
    def parse_optional_float(cls, v: Any) -> Optional[float]:
        """Parse empty string as None for optional float fields."""
        if v == "" or v is None:
            return None
        try:
            return float(v) if v else None
        except (ValueError, TypeError):
            return None
    
    # Databases
    database_path: str = "data/sample_data.db"
    
    # Catalog Configuration (for multi-catalog support)
    # Format: JSON string mapping catalog names to configurations
    # Example: '{"analytics": {"type": "sqlite", "path": "data/analytics.db"}}'
    catalog_configs: str = "{}"  # JSON string, parsed in CatalogManager
    
    # Vector Store Configuration
    # NOTE: vector_store_path is ONLY used by SimpleVectorStore (JSON file fallback)
    # When using ChromaDB (recommended), this path is NOT used
    vector_store_path: str = "data/vector_store"  # Only for SimpleVectorStore fallback
    
    # ChromaDB Configuration (Primary vector database)
    # ChromaDB is a lightweight, embedded vector database that works on all platforms
    chromadb_data_path: str = "data/chromadb_data"  # Path for ChromaDB persistent storage
    
    # MLflow
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment_name: str = "mcp_agent_experiments"
    enable_mlflow_tracking: bool = True  # Set to False to disable MLflow tracking (experiments won't be logged)
    
    # Graph Visualization
    enable_graph_visualization: bool = False  # Set to True to display graph visualization after compilation (requires IPython)
    
    # MCP Server ports
    catalog_mcp_port: int = 7001
    vector_mcp_port: int = 7002
    sql_mcp_port: int = 7003
    
    # MCP Authentication
    mcp_api_key: Optional[str] = None  # Shared MCP API key
    
    # Dynamic MCP Server Configuration
    # Format: JSON string mapping server names to SSE URLs
    # Example: '{"custom_server": "http://localhost:7004/sse"}'
    additional_mcp_servers: str = "{}"  # JSON string, parsed in MCPSDKClient
    
    # API settings
    api_port: int = 8000
    api_key: Optional[str] = None
    api_host: str = "0.0.0.0"
    
    # Concurrency
    max_parallel_mcp_calls: int = 5
    mcp_call_timeout: int = 60  # Increased from 30 to 60 seconds for slower connections
    mcp_connect_timeout: int = 10  # Connection timeout in seconds
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    # Inference Logging
    inference_log_db_path: str = "data/inference_logs.db"
    
    # LangGraph Checkpointing (for conversation history persistence)
    checkpoint_db_path: str = "data/checkpoints.db"  # SQLite database for checkpoint storage
    
    # Agent Implementation Selection
    # Always using LangGraph + MCP SDK (custom implementation removed)
    # This setting is kept for backward compatibility but always True
    use_langgraph: bool = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance.
    
    Returns:
        Settings instance
    """
    settings = Settings()
    # Debug: Log what was loaded (only in development)
    import os
    if os.getenv("DEBUG_SETTINGS", "false").lower() == "true":
        print(f"[DEBUG] Settings loaded - LLM Provider: {settings.llm_provider}")
        print(f"[DEBUG] .env file path: {_env_file_path}")
        print(f"[DEBUG] .env file exists: {_env_file_path.exists()}")
    return settings


def clear_settings_cache():
    """Clear the settings cache.
    
    Call this when .env file changes to reload settings.
    """
    get_settings.cache_clear()
