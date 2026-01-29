# Multi-Tool Orchestration

A LangGraph agent that connects to MCP (Model Context Protocol) servers for multi-tool orchestration.

## 📚 Documentation

All documentation is organized in the [`docs/`](docs/) folder:

- **[Project Overview](docs/guides/understanding.md)** - Architecture and design
- **[Installation Guide](docs/guides/installation_notes.md)** - Setup instructions
- **[Hybrid Embeddings Guide](docs/guides/hybrid_embeddings.md)** - Using Ollama and Gemini embeddings
- **[Implementation Status](docs/implementation/implementation_status.md)** - Current progress
- **[Documentation Index](docs/README.md)** - Complete documentation index

## 🚀 Quick Start

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Configure**: Copy `.env.example` to `.env` and add your API keys
3. **Setup data**: Run `python scripts/setup_data.py`
4. **Start servers**: 
   - `python -m mcp_servers.catalog_server.server` (Terminal 1)
   - `python -m mcp_servers.sql_query_server.server` (Terminal 2)
5. **Test**: Run `python examples/test_mcp_servers.py`

See [Phase 1 Quick Start Guide](docs/guides/phase1_quickstart.md) for detailed instructions.

## ✨ Features

- ✅ **Model Abstraction**: Support for multiple LLM providers (Gemini, Ollama, OpenAI, Anthropic)
- ✅ **Hybrid Embeddings**: Use Ollama (local) or Gemini (cloud) for embeddings
- ✅ **Client-Server Architecture**: HTTP-based MCP servers
- ✅ **Versioning**: Tool and server versioning support
- ✅ **Authentication**: API key-based authentication
- ✅ **MCP Servers**: Catalog and SQL Query servers (Phase 1 complete)
- ✅ **MCP Client**: HTTP client with concurrency control
- ✅ **Tool Discovery**: Automatic tool discovery from MCP servers

## 📁 Project Structure

```
multi_tool_orchestration/
├── docs/                    # All documentation
├── llm/                     # LLM provider abstraction
├── config/                  # Configuration
├── agent/                   # LangGraph agent (to be implemented)
├── mcp_servers/             # MCP servers (to be implemented)
├── examples/                # Usage examples
└── tests/                   # Test suite
```

See [docs/guides/understanding.md](docs/guides/understanding.md) for complete project structure.
