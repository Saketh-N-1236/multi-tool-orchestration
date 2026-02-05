# Backend - Multi-Tool Orchestration

Backend Python application for the Multi-Tool Orchestration system.

## Structure

```
backend/
├── api/                 # FastAPI REST API server
├── agent/               # LangGraph agent implementation
├── mcp_servers/         # MCP (Model Context Protocol) servers
├── llm/                 # LLM provider abstraction layer
├── config/              # Configuration and settings
├── analytics/           # Analytics aggregation logic
├── inference_logging/   # Inference request logging
├── mlflow/              # MLflow experiment tracking
├── scripts/             # Utility and setup scripts
├── tests/               # Test suite
└── data/                # Data files, databases, and vector stores
```

## Quick Start

1. **Install dependencies** (from project root):
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure** (from project root):
   - Copy `.env.example` to `.env`
   - Add your API keys (Gemini API key required)

3. **Setup data** (from backend directory):
   ```bash
   cd backend
   python scripts/setup_data.py
   ```

4. **Start MCP servers** (from backend directory):
   ```bash
   # Terminal 1
   python -m mcp_servers.catalog_server.server
   
   # Terminal 2
   python -m mcp_servers.sql_query_server.server
   
   # Terminal 3
   python -m mcp_servers.vector_search_server.server
   ```

5. **Start API server** (from backend directory):
   ```bash
   python -m api.main
   ```

The API will be available at `http://localhost:8000`

## Running Scripts

All scripts should be run from the `backend/` directory:

```bash
cd backend
python scripts/setup_data.py
python scripts/evaluate_agent.py
python scripts/upload_documents.py
# etc.
```

## Running Tests

Tests should be run from the `backend/` directory:

```bash
cd backend
python tests/test_mcp_servers.py
python tests/test_agent.py
python tests/test_chat_endpoint.py
```

## Module Imports

All Python modules use relative imports within the backend package. When running scripts or tests, make sure you're in the `backend/` directory or add it to your Python path.


You migrated the client to MCP SDK + SSE,
but you did not migrate the servers to MCP.
mlflow ui --port 5000
now explain me how the tool is selection explain with visual flow . what techniques that we are using and what features implemented for this and what are non functional features
Assessing whether connecting your custom MCP servers to Cursor is useful. Reviewing the server setup:


[4 tools called]


Checking available tools:


[3 tools called]


## Opinion: connecting your MCP servers to Cursor

### Benefits

1. Database schema awareness
   - Cursor can see tables, schemas, and row counts
   - Helps generate accurate SQL and understand data models
   - Tools: `list_tables`, `describe_table`, `get_table_row_count`

2. Codebase documentation search
   - Search uploaded docs/knowledge base from within Cursor
   - Tool: `search_documents`

3. SQL query assistance
   - Test queries directly in Cursor
   - Get execution plans
   - Tools: `execute_query`, `explain_query`

4. Better context for code generation
   - Cursor can use your actual database schema and docs when generating code

### Challenges

1. Transport mismatch
   - Your servers: SSE (HTTP-based) via FastMCP
   - Cursor expects: stdio transport (standard input/output)
   - Solution: Create a stdio wrapper or use an MCP bridge

2. Server management
   - Cursor expects servers to start on demand
   - Your servers run as long-lived HTTP services
   - Solution: Create a stdio wrapper that connects to your HTTP servers

3. Configuration complexity
   - Cursor needs MCP server config in settings
   - Need to handle authentication/ports

### Technical approach

Option 1: Create stdio wrapper scripts (recommended)

Create lightweight Python scripts that:
- Use stdio transport (what Cursor expects)
- Forward requests to your HTTP MCP servers
- Act as a bridge between Cursor and your servers

```python
# Example: cursor_mcp_bridge.py
# This would connect to your HTTP servers and expose via stdio
```

Option 2: Dual-mode servers

Modify your servers to support both:
- SSE transport (for your current system)
- stdio transport (for Cursor)

This requires more changes but keeps everything in one place.

### Recommendation

Yes, connect them, but use Option 1 (stdio wrapper).

Reasons:
1. Low risk: doesn't change existing servers
2. Quick to implement: simple bridge scripts
3. Best of both worlds: keep SSE for your system, add stdio for Cursor
4. High value: Cursor gains access to your database and docs

### Implementation priority

High value, medium effort:
1. Catalog server — most useful for code generation
2. SQL query server — useful for testing queries
3. Vector search server — useful if you have documentation

### What you'd need

1. Create 3 stdio wrapper scripts (one per server)
2. Configure Cursor's MCP settings to point to these scripts
3. Ensure your HTTP servers are running when Cursor needs them

### Example Cursor MCP config

```json
{
  "mcpServers": {
    "catalog": {
      "command": "python",
      "args": ["path/to/cursor_catalog_bridge.py"]
    },
    "sql_query": {
      "command": "python", 
      "args": ["path/to/cursor_sql_bridge.py"]
    },
    "vector_search": {
      "command": "python",
      "args": ["path/to/cursor_vector_bridge.py"]
    }
  }
}
```

### Final verdict

Yes, connect them. The benefits outweigh the effort, especially for the catalog and SQL servers. The stdio wrapper approach is clean and maintainable.

Should I create the stdio wrapper scripts for you?