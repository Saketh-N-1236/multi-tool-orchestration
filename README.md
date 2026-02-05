# Multi-Tool Orchestration

A LangGraph agent that connects to MCP (Model Context Protocol) servers for multi-tool orchestration.

## 📚 Documentation

All documentation is organized in the [`docs/`](docs/) folder:

- **[Project Overview](docs/guides/understanding.md)** - Complete architecture and project structure
- **[High-Level Design](docs/guides/hld.md)** - System architecture and design
- **[Inference Logging & MLflow](docs/guides/hld_inference_mlflow.puml)** - Architecture diagram

## 🚀 Quick Start

### Backend Setup

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Configure**: Copy `.env.example` to `.env` and add your API keys (Gemini API key required)
3. **Navigate to backend**: `cd backend`
4. **Setup data**: Run `python scripts/setup_data.py`
5. **Start servers** (from backend directory): 
   - `python -m mcp_servers.catalog_server.server` (Terminal 1)
   - `python -m mcp_servers.sql_query_server.server` (Terminal 2)
   - `python -m mcp_servers.vector_search_server.server` (Terminal 3)
6. **Start API server**: `python -m api.main` (Terminal 4)
7. **Test servers**: Run `python tests/test_mcp_servers.py`
8. **Test agent**: Run `python tests/test_agent.py`

### Frontend Setup

1. **Navigate to frontend**: `cd frontend`
2. **Install dependencies**: `npm install`
3. **Start development server**: `npm run dev`
4. **Open browser**: Navigate to `http://localhost:3000`

See [Project Overview](docs/guides/understanding.md) for detailed documentation.

## ✨ Features

- ✅ **Model Abstraction**: Support for multiple LLM providers (Gemini, Ollama, OpenAI, Anthropic)
- ✅ **Hybrid Embeddings**: Use Ollama (local) or Gemini (cloud) for embeddings
- ✅ **Client-Server Architecture**: HTTP-based MCP servers
- ✅ **Versioning**: Tool and server versioning support
- ✅ **Authentication**: API key-based authentication
- ✅ **MCP Servers**: All 3 servers complete (Catalog, SQL Query, Vector Search)
- ✅ **MCP Client**: HTTP client with concurrency control
- ✅ **Tool Discovery**: Automatic tool discovery from MCP servers
- ✅ **Agent System**: LLM-powered agent with tool orchestration (Phase 2 complete)
- ✅ **Prompt Versioning**: Versioned prompts for tracking and experimentation
- ✅ **Frontend UI**: React + Vite frontend with chat, analytics, documents, and tools pages
- ✅ **Inference Logging**: Comprehensive logging of all API requests and responses
- ✅ **MLflow Integration**: Experiment tracking and AI-driven evaluation
- ✅ **Analytics Dashboard**: Real-time monitoring and visualization

## 📁 Project Structure

```
multi_tool_orchestration/
├── frontend/                # React + Vite frontend application
├── backend/                 # Backend Python application
│   ├── api/                 # FastAPI backend
│   ├── agent/               # LangGraph agent
│   ├── mcp_servers/         # MCP servers
│   ├── llm/                 # LLM provider abstraction
│   ├── config/              # Configuration
│   ├── analytics/           # Analytics aggregation
│   ├── inference_logging/   # Inference logging
│   ├── mlflow/              # MLflow integration
│   ├── scripts/             # Utility scripts
│   ├── tests/               # Test suite
│   └── data/                # Data files and databases
├── docs/                    # All documentation
└── requirements.txt         # Python dependencies
```

See [docs/guides/understanding.md](docs/guides/understanding.md) for complete project structure.
