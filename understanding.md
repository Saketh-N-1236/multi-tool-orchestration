Local MCP Tool-Calling Agents

Project Structure

```
multi_tool_orchestration/
├── mcp_servers/                         # Custom MCP servers (HTTP transport)
│   ├── __init__.py
│   ├── base_server.py                   # Base MCP server (HTTP + Auth + Versioning)
│   ├── catalog_server/
│   │   ├── __init__.py
│   │   ├── server.py                    # Catalog MCP server
│   │   ├── tools.py                     # Catalog tools (with versioning)
│   │   └── database.py                  # SQLite operations
│   ├── vector_search_server/
│   │   ├── __init__.py
│   │   ├── server.py                    # Vector Search MCP server
│   │   ├── tools.py                     # Vector search tools (with versioning)
│   │   └── vector_store.py              # Chroma integration
│   └── sql_query_server/
│       ├── __init__.py
│       ├── server.py                    # SQL Query MCP server
│       ├── tools.py                     # SQL query tools (with versioning)
│       └── query_engine.py              # SQL execution (read-only enforcement)
├── agent/                                # LangGraph agent
│   ├── __init__.py
│   ├── state.py                         # Agent state schema
│   ├── graph.py                         # LangGraph agent graph
│   ├── mcp_client.py                    # MCP client (HTTP + Auth + Concurrency)
│   ├── tool_binding.py                 # Bind MCP tools to agent
│   ├── orchestrator.py                  # Tool orchestration logic
│   ├── tool_result_normalizer.py        # Tool result normalization
│   └── prompts/                         # Versioned prompts
│       ├── system_v1.txt                # System prompt v1
│       ├── tool_policy.txt              # Tool usage policy
│       └── README.md                    # Prompt versioning docs
├── llm/                                  # LLM integration
│   ├── __init__.py
│   └── gemini_client.py                 # Gemini API client
├── api/                                  # FastAPI deployment
│   ├── __init__.py
│   ├── main.py                          # FastAPI app
│   ├── routes.py                        # API endpoints
│   ├── models.py                        # Request/response models
│   └── middleware.py                    # Inference logging + Request ID
├── mlflow/                               # MLflow integration
│   ├── __init__.py
│   ├── tracking.py                      # MLflow tracking setup
│   ├── evaluation.py                    # Evaluation pipeline
│   ├── judges.py                         # AI judge configuration
│   └── data/                            # Evaluation datasets
│       └── eval_dataset.jsonl           # Versioned evaluation dataset
├── logging/                              # Inference logging
│   ├── __init__.py
│   ├── inference_logger.py              # Inference logging
│   └── models.py                        # Log models
├── error_handling/                       # Error handling
│   ├── __init__.py
│   ├── error_handler.py                 # Error handling strategies
│   ├── retry.py                          # Retry logic
│   └── circuit_breaker.py               # Circuit breaker pattern
├── config/                               # Configuration
│   ├── __init__.py
│   ├── settings.py                      # Pydantic settings (with all ENV vars)
│   ├── config.yaml                      # Main configuration
│   └── .env.example                      # Environment variables template
├── data/                                 # Data files
│   ├── sample_data.db                   # SQLite database
│   ├── inference_logs.db                # Inference logging database
│   ├── vector_store/                    # Chroma vector store directory
│   └── sample_documents/                # Sample documents
├── tests/                                # Test suite
│   ├── __init__.py
│   ├── test_mcp_servers.py              # MCP server tests
│   ├── test_agent.py                    # Agent tests
│   ├── test_api.py                      # API tests
│   ├── test_mlflow.py                   # MLflow tests
│   ├── test_chaos.py                    # Chaos tests (server down, timeout)
│   └── fixtures/                        # Test fixtures
├── scripts/                              # Utility scripts
│   ├── setup_data.py                    # Initialize sample data
│   ├── start_servers.py                  # Start all MCP servers
│   ├── populate_vector_store.py         # Populate Chroma
│   └── setup_mlflow.py                  # Setup MLflow
├── requirements.txt                      # Python dependencies
├── README.md                             # Documentation
├── .env.example                          # Environment template
└── docker-compose.yml                    # Docker setup (OPTIONAL - for later)
```

Implementation Phases

Phase 1: Foundation & MCP Servers (Days 1-3)

#### Day 1: Project Setup & MCP Framework (HTTP + Auth + Versioning)

**Tasks:**

1. **Project initialization**
   - Create directory structure (including `agent/prompts/`)
   - Initialize Python virtual environment
   - `requirements.txt` (same as before)

2. **Configuration setup with all ENV vars**
   - File: `config/settings.py` (enhanced):
     ```python
     from pydantic_settings import BaseSettings
     
     class Settings(BaseSettings):
         # LLM
         gemini_api_key: str
         gemini_model: str = "gemini-2.5-pro"  # Configurable model
         
         # Databases
         database_path: str = "./data/sample_data.db"
         vector_store_path: str = "./data/vector_store"
         
         # MLflow
         mlflow_tracking_uri: str = "http://localhost:5000"
         
         # MCP Server ports
         catalog_mcp_port: int = 7001
         vector_mcp_port: int = 7002
         sql_mcp_port: int = 7003
         
         # MCP Authentication
         mcp_api_key: Optional[str] = None  # Shared MCP API key
         
         # API settings
         api_port: int = 8000
         api_key: Optional[str] = None
         
         # Concurrency
         max_parallel_mcp_calls: int = 5
         mcp_call_timeout: int = 30
         
         # Logging
         log_level: str = "INFO"
         
         class Config:
             env_file = ".env"
     ```

3. **Base MCP server (HTTP + Auth + Versioning)**
   - File: `mcp_servers/base_server.py`
   - HTTP-based MCP server using FastAPI
   - JSON-RPC 2.0 protocol (explicit)
   - Version metadata:
     ```python
     SERVER_VERSION = "1.0.0"
     PROTOCOL_VERSION = "2024-11-05"  # MCP protocol version
     ```
   - Authentication middleware:
     ```python
     @app.middleware("http")
     async def verify_mcp_key(request: Request, call_next):
         if settings.mcp_api_key:
             if request.headers.get("X-MCP-KEY") != settings.mcp_api_key:
                 return JSONResponse({"error": "Unauthorized"}, 401)
         return await call_next(request)
     ```
   - Health check: `GET /health` (returns version info)
   - Tools list: `GET /tools` (returns tools with versioning):
     ```python
     {
         "server_version": "1.0.0",
         "protocol_version": "2024-11-05",
         "tools": [
             {
                 "name": "list_tables",
                 "tool_version": "1.0.0",
                 "description": "...",
                 "inputSchema": {...}
             }
         ]
     }
     ```
   - Tool execution: `POST /execute` (JSON-RPC 2.0 format)

4. **Catalog MCP server (with versioning)**
   - File: `mcp_servers/catalog_server/server.py`
   - Extends base server
   - Tools with version metadata
   - File: `mcp_servers/catalog_server/tools.py`
   - Each tool includes `tool_version: "1.0.0"`

#### Day 2: Vector Search & SQL Query Servers (with improvements)

**Tasks:**

1. **Vector Search MCP server (with collection naming)**
   - File: `mcp_servers/vector_search_server/server.py`
   - Collection naming convention: `{collection_name}_{version}`
   - Tools with versioning
   - File: `mcp_servers/vector_search_server/vector_store.py`
   - Chroma with Gemini embeddings
   - Collection management with versioning

2. **SQL Query MCP server (read-only enforcement)**
   - File: `mcp_servers/sql_query_server/server.py`
   - Tools with versioning
   - File: `mcp_servers/sql_query_server/query_engine.py`
   - Read-only enforcement:
     ```python
     READ_ONLY_KEYWORDS = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER"]
     
     def validate_read_only(query: str):
         query_upper = query.upper().strip()
         for keyword in READ_ONLY_KEYWORDS:
             if query_upper.startswith(keyword):
                 raise ValueError(f"Read-only mode: {keyword} not allowed")
     ```

3. **Sample data setup**
   - Create SQLite database
   - Populate Chroma with versioned collections
   - Use Gemini embeddings

#### Day 3: MCP Client (HTTP + Auth + Concurrency)

**Tasks:**

1. **MCP client (HTTP + Auth + Concurrency)**
   - File: `agent/mcp_client.py`
   - HTTP client for MCP servers
   - JSON-RPC 2.0 communication
   - Authentication header: `X-MCP-KEY`
   - Concurrency control:
     ```python
     from asyncio import Semaphore
     
     class MCPClient:
         def __init__(self, max_parallel: int = 5, timeout: int = 30):
             self.semaphore = Semaphore(max_parallel)
             self.timeout = timeout
         
         async def call_tool(self, server_url, tool_name, args):
             async with self.semaphore:
                 # Make HTTP call with timeout
                 pass
     ```
   - Request ID propagation:
     ```python
     async def call_tool(self, ..., request_id: str = None):
         headers = {
             "X-MCP-KEY": settings.mcp_api_key,
             "X-Request-ID": request_id or str(uuid.uuid4())
         }
     ```

2. **Tool result normalizer**
   - File: `agent/tool_result_normalizer.py`
   - Normalize all tool results:
     ```python
     def normalize_result(result: Any, tool_name: str) -> dict:
         return {
             "status": "success" if not isinstance(result, Exception) else "error",
             "data": result if not isinstance(result, Exception) else None,
             "metadata": {
                 "tool_name": tool_name,
                 "timestamp": datetime.utcnow().isoformat()
             },
             "error": str(result) if isinstance(result, Exception) else None
         }
     ```

3. **Tool discovery system**
   - Discover tools with version metadata
   - Validate tool versions
   - Register tools with version info

4. **Testing MCP servers**
   - Test HTTP endpoints
   - Test authentication
   - Test versioning
   - Test tool discovery
Phase 2: LangGraph Agent Development (Days 4-5)

#### Day 4: Agent Core & Gemini Integration (with prompt versioning)

**Tasks:**

1. **Prompt versioning system**
   - File: `agent/prompts/system_v1.txt`
     ```
     You are a helpful AI assistant that can use multiple tools to answer questions.
     Available tools: {tool_list}
     Tool usage policy: {tool_policy}
     ...
     ```
   - File: `agent/prompts/tool_policy.txt`
     ```
     - Always validate tool inputs before calling
     - Handle errors gracefully
     - Use tools in logical order
     ...
     ```
   - File: `agent/prompts/README.md` - Document prompt versions

2. **Gemini API client**
   - File: `llm/gemini_client.py`
   - Use configurable model from settings
   - Load prompts from versioned files
   - Log prompt version to MLflow:
     ```python
     mlflow.log_param("prompt_version", "v1")
     mlflow.log_param("model", settings.gemini_model)
     ```

3. **Agent state schema**
   - File: `agent/state.py`
   - Include request_id in state:
     ```python
     class AgentState(TypedDict):
         messages: List[BaseMessage]
         tool_calls: List[dict]
         tool_results: List[dict]
         request_id: str  # For correlation
         current_step: Optional[int]
         error: Optional[str]
         session_id: Optional[str]
     ```

4. **LangGraph agent graph**
   - File: `agent/graph.py`
   - Load system prompt from versioned file
   - Propagate request_id through all nodes
   - Use tool result normalizer

5. **Tool binding**
   - File: `agent/tool_binding.py`
   - Convert MCP tools to LangGraph tools
   - Include tool version in metadata

#### Day 5: Tool Orchestration & Error Handling

**Tasks:**

1. **Tool orchestration**
   - File: `agent/orchestrator.py`
   - Use normalized tool results
   - Handle version mismatches

2. **Error handling**
   - Complete error handling system
   - Use normalized error format

3. **Agent testing**
   - Test with versioned prompts
   - Test request ID propagation
   - Test normalized results

Phase 3: FastAPI Deployment (Day 6)

#### Day 6: API Development & Deployment (with Request ID)

**Tasks:**

1. **FastAPI application**
   - File: `api/main.py`
   - Request ID middleware:
     ```python
     @app.middleware("http")
     async def add_request_id(request: Request, call_next):
         request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
         request.state.request_id = request_id
         response = await call_next(request)
         response.headers["X-Request-ID"] = request_id
         return response
     ```

2. **API routes**
   - File: `api/routes.py`
   - Propagate request_id to agent
   - Include request_id in responses

3. **Inference logging middleware**
   - File: `api/middleware.py`
   - Log with request_id
   - File: `logging/inference_logger.py`
   - Include request_id in logs

4. **Rate limiting**
   - Use `slowapi`
   - Configurable limits

5. **API testing**
   - Test request ID propagation
   - Test all endpoints

### Phase 3.5: MLflow Evaluation & Observability (Day 6.5)

#### Tasks:

1. **MLflow setup**
   - File: `mlflow/tracking.py`
   - Log prompt version
   - Log model name from settings

2. **Evaluation dataset storage**
   - File: `mlflow/data/eval_dataset.jsonl`
   - JSONL format for versioning
   - Example:
     ```jsonl
     {"input": "List all tables", "expected_output": "...", "category": "catalog"}
     {"input": "Search for documents about AI", "expected_output": "...", "category": "vector"}
     ```

3. **Evaluation pipeline**
   - File: `mlflow/evaluation.py`
   - Load dataset from JSONL
   - Run evaluation
   - Log with request IDs

4. **Tracing integration**
   - Enable MLflow tracing
   - Correlate with request IDs
   - Log tool calls with versions

5. **Testing**
   - Test evaluation pipeline
   - Test tracing with request IDs

### Phase 4: Testing & Documentation (Day 7)

#### Day 7: Final Testing & Documentation

**Tasks:**

1. **Chaos testing**
   - File: `tests/test_chaos.py`
   - Test server down scenarios
   - Test timeout scenarios
   - Test authentication failures
   - Test version mismatches

2. **Integration testing**
   - End-to-end with request IDs
   - Performance testing
   - Load testing

3. **Documentation**
   - Update `README.md`:
     - Versioning strategy
     - Authentication setup
     - Request ID correlation
     - Prompt versioning
     - Collection naming conventions
     - Read-only SQL enforcement
   - API documentation
   - MLflow evaluation guide

4. **Final validation**
   - Test all improvements
   - Verify request ID propagation
   - Verify versioning
   - Verify authentication

##Technical Specifications

### MCP Server with Versioning & Auth

```python
# Base MCP Server
from fastapi import FastAPI, Header, HTTPException
from typing import Optional

app = FastAPI(title="Catalog MCP Server")

SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "server_version": SERVER_VERSION,
        "protocol_version": PROTOCOL_VERSION
    }

@app.get("/tools")
async def list_tools(x_mcp_key: Optional[str] = Header(None)):
    # Verify auth
    if settings.mcp_api_key and x_mcp_key != settings.mcp_api_key:
        raise HTTPException(401, "Unauthorized")
    
    return {
        "server_version": SERVER_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "tools": [
            {
                "name": "list_tables",
                "tool_version": "1.0.0",
                "description": "List all tables",
                "inputSchema": {...}
            }
        ]
    }

@app.post("/execute")
async def execute_tool(
    request: JSONRPCRequest,
    x_mcp_key: Optional[str] = Header(None),
    x_request_id: Optional[str] = Header(None)
):
    # Verify auth
    # Execute with request ID
    # Return normalized result
    pass
```

### Request ID Propagation

```python
# API Middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Propagate to agent
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# Agent
def invoke_agent(state: AgentState, request_id: str):
    state["request_id"] = request_id
    # Propagate to MCP calls
    # Log to MLflow with request_id
    pass

# MCP Client
async def call_tool(..., request_id: str):
    headers = {
        "X-MCP-KEY": settings.mcp_api_key,
        "X-Request-ID": request_id
    }
    # Make call
    pass
```

### Tool Result Normalization

```python
# agent/tool_result_normalizer.py
def normalize_result(result: Any, tool_name: str, tool_version: str = "1.0.0") -> dict:
    """Normalize all tool results to consistent format"""
    if isinstance(result, Exception):
        return {
            "status": "error",
            "data": None,
            "metadata": {
                "tool_name": tool_name,
                "tool_version": tool_version,
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
            "timestamp": datetime.utcnow().isoformat()
        },
        "error": None
    }
```
Deliverables Checklist

- [ ] Three custom MCP servers (HTTP + Auth + Versioning)
- [ ] MCP authentication (X-MCP-KEY header)
- [ ] Tool versioning (tool_version, server_version, protocol_version)
- [ ] LangGraph agent with prompt versioning
- [ ] Request ID propagation (API → Agent → MCP → Logs → MLflow)
- [ ] Tool result normalization layer
- [ ] Concurrency limits for MCP calls
- [ ] SQL read-only enforcement
- [ ] Collection naming conventions
- [ ] FastAPI server with inference logging
- [ ] MLflow evaluation with JSONL dataset
- [ ] Chaos tests (server down, timeout)
- [ ] Complete documentation
- [ ] Docker setup (optional, for later)

##Success Criteria

1. All MCP servers return version metadata
2. MCP authentication works correctly
3. Request IDs propagate through entire system
4. Tool results are normalized consistently
5. Concurrency limits prevent overload
6. SQL queries are read-only enforced
7. MLflow evaluation uses versioned dataset
8. Chaos tests pass
9. All tests passing
10. Documentation complete
