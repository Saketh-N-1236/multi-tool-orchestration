# Phase 1: MCP Servers Quick Start Guide

## Prerequisites

1. ✅ Python 3.11+ (or 3.14 with some limitations)
2. ✅ Dependencies installed: `pip install -r requirements.txt`
3. ✅ `.env` file configured with API keys

## Step 1: Setup Sample Data

```bash
python scripts/setup_data.py
```

This creates a sample SQLite database with:
- `users` table (4 sample users)
- `products` table (5 sample products)
- `orders` table (5 sample orders)

## Step 2: Start MCP Servers

### Option A: Start Individual Servers

**Terminal 1 - Catalog Server:**
```bash
python -m mcp_servers.catalog_server.server
```

**Terminal 2 - SQL Query Server:**
```bash
python -m mcp_servers.sql_query_server.server
```

**Terminal 3 - Vector Search Server:**
```bash
python -m mcp_servers.vector_search_server.server
```

### Option B: Start All Servers (Basic)

```bash
python scripts/start_servers.py
```

## Step 3: Verify Servers are Running

### Test Health Endpoints

```bash
# Catalog server
curl http://localhost:7001/health

# SQL Query server
curl http://localhost:7003/health

# Vector Search server
curl http://localhost:7002/health
```

Expected response:
```json
{
  "status": "healthy",
  "server_name": "Catalog MCP Server",
  "server_version": "1.0.0",
  "protocol_version": "2024-11-05"
}
```

### Test Tool Listing

```bash
curl http://localhost:7001/tools
```

## Step 4: Run Test Suite

```bash
python examples/test_mcp_servers.py
```

This will test:
- ✅ Server health checks (all 3 servers)
- ✅ Tool discovery (all 8 tools)
- ✅ Tool execution
- ✅ Read-only enforcement
- ✅ Vector search functionality

You can also test vector search specifically:
```bash
python examples/test_vector_search.py
```

## Step 5: Use MCP Client in Your Code

```python
import asyncio
from agent.mcp_client import MCPClient
from agent.tool_result_normalizer import normalize_result

async def main():
    async with MCPClient() as client:
        # List tables
        result = await client.call_tool(
            server_url="http://localhost:7001",
            tool_name="list_tables",
            params={}
        )
        
        normalized = normalize_result(result, "list_tables")
        print(normalized)

asyncio.run(main())
```

## Common Issues

### Server Won't Start

**Issue:** Port already in use
**Solution:** 
- Change port in `.env` file
- Or stop the process using the port

### Authentication Errors

**Issue:** `401 Unauthorized`
**Solution:**
- Set `MCP_API_KEY` in `.env` file
- Or remove `MCP_API_KEY` to disable authentication

### Database Not Found

**Issue:** `Database file not found`
**Solution:**
- Run `python scripts/setup_data.py` first
- Check `DATABASE_PATH` in `.env`

## Next Steps

- ✅ Phase 1 Complete: MCP Servers ready
- ⏳ Phase 2: Implement LangGraph Agent
- ⏳ Phase 3: FastAPI Deployment
- ⏳ Phase 4: Testing & Documentation

## Architecture

```
┌─────────────────┐
│   MCP Client    │
│  (agent/)       │
└────────┬────────┘
         │ HTTP + JSON-RPC 2.0
         │
    ┌────┴────┬────┐
    │         │    │
┌───▼───┐ ┌──▼────┐ ┌──▼────────┐
│Catalog│ │  SQL  │ │  Vector   │
│Server │ │Server │ │  Search   │
└───────┘ └───────┘ └───────────┘
```

See [Phase 1 Implementation Details](../implementation/phase1_mcp_servers.md) for more information.
