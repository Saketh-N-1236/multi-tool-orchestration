# Cursor Integration Guide

This guide explains how to connect your MCP servers to Cursor IDE.

## Overview

Your MCP servers are configured to work with Cursor IDE via stdio (standard input/output) transport. Each server has a stdio wrapper script that allows Cursor to communicate with it.

## Prerequisites

1. **Cursor IDE** installed
2. **Python environment** with all dependencies installed
3. **MCP SDK** installed: `pip install mcp>=1.0.0`

## Setup Steps

### Step 1: Verify Stdio Servers

Test that the stdio servers work correctly:

```bash
# From backend directory
cd backend

# Test catalog server
python -m mcp_servers.catalog_server.stdio_server

# Test SQL query server
python -m mcp_servers.sql_query_server.stdio_server

# Test vector search server
python -m mcp_servers.vector_search_server.stdio_server
```

Each server should start and wait for input (they won't produce output until they receive MCP protocol messages).

### Step 2: Configure Cursor

1. **Locate Cursor Configuration**

   Cursor configuration location depends on your OS:
   - **Windows**: `%APPDATA%\Cursor\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`
   - **macOS**: `~/Library/Application Support/Cursor/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`
   - **Linux**: `~/.config/Cursor/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

2. **Add MCP Server Configuration**

   Add the following to your Cursor MCP settings file:

   ```json
   {
     "mcpServers": {
       "catalog": {
         "command": "python",
         "args": [
           "-m",
           "mcp_servers.catalog_server.stdio_server"
         ],
         "cwd": "/absolute/path/to/backend"
       },
       "sql_query": {
         "command": "python",
         "args": [
           "-m",
           "mcp_servers.sql_query_server.stdio_server"
         ],
         "cwd": "/absolute/path/to/backend"
       },
       "vector_search": {
         "command": "python",
         "args": [
           "-m",
           "mcp_servers.vector_search_server.stdio_server"
         ],
         "cwd": "/absolute/path/to/backend"
       }
     }
   }
   ```

   **Important**: Replace `/absolute/path/to/backend` with the actual absolute path to your `backend` directory.

   Example (Windows):
   ```json
   "cwd": "C:\\Users\\YourName\\Downloads\\training_tasks\\multi_tool_orchestration\\backend"
   ```

   Example (macOS/Linux):
   ```json
   "cwd": "/home/username/projects/multi_tool_orchestration/backend"
   ```

### Step 3: Restart Cursor

After configuring, restart Cursor IDE completely to load the new MCP server configurations.

### Step 4: Verify Integration

1. Open Cursor IDE
2. Open the MCP panel (usually accessible via Command Palette: `Cmd/Ctrl + Shift + P` → "MCP")
3. You should see your three servers listed:
   - `catalog`
   - `sql_query`
   - `vector_search`
4. Check that tools are discoverable for each server

## Available Tools

### Catalog Server Tools

- `list_tables` - List all tables in the database
- `describe_table` - Get schema information for a table
- `get_table_row_count` - Get row count for a table
- `list_catalogs` - List all available catalogs (Unity Catalog-like)
- `list_schemas` - List schemas in a catalog
- `list_tables_multi` - List tables in catalog/schema
- `describe_table_multi` - Get table metadata with catalog/schema
- `search_tables` - Search tables across catalogs
- `get_table_lineage` - Get data lineage for a table

### SQL Query Server Tools

- `execute_query` - Execute a read-only SQL SELECT query
- `explain_query` - Get execution plan for a SQL query

### Vector Search Server Tools

- `search_documents` - Search for documents using semantic similarity
- `add_documents` - Add documents to the vector store

## Troubleshooting

### Server Not Appearing in Cursor

1. **Check Python Path**: Ensure Python is in your system PATH
2. **Check Working Directory**: Verify the `cwd` path is correct and absolute
3. **Check Dependencies**: Ensure all Python dependencies are installed
4. **Check Logs**: Look for errors in Cursor's developer console

### Server Fails to Start

1. **Test Manually**: Run the stdio server manually to see errors:
   ```bash
   cd backend
   python -m mcp_servers.catalog_server.stdio_server
   ```

2. **Check Imports**: Ensure all imports work correctly
3. **Check Settings**: Verify settings file is accessible

### Tools Not Discoverable

1. **Check Server Status**: Verify server is running in Cursor
2. **Check Tool Registration**: Ensure tools are properly registered in server code
3. **Restart Cursor**: Sometimes a restart helps refresh tool discovery

### Path Issues

If you encounter path-related errors:

1. Use absolute paths in Cursor configuration
2. Ensure the `backend` directory contains all necessary files
3. Check that Python can find the modules

## Alternative: Using Relative Paths

If absolute paths don't work, you can try using a wrapper script:

1. Create a wrapper script (e.g., `backend/scripts/run_catalog_stdio.sh` or `.bat`):

   **Windows** (`run_catalog_stdio.bat`):
   ```batch
   @echo off
   cd /d %~dp0..
   cd backend
   python -m mcp_servers.catalog_server.stdio_server
   ```

   **Unix** (`run_catalog_stdio.sh`):
   ```bash
   #!/bin/bash
   cd "$(dirname "$0")/../backend"
   python -m mcp_servers.catalog_server.stdio_server
   ```

2. Update Cursor config to use the wrapper script instead

## Testing

To test the stdio servers work correctly:

```bash
# From project root
cd backend

# Test each server (they should start and wait for input)
python -m mcp_servers.catalog_server.stdio_server
python -m mcp_servers.sql_query_server.stdio_server
python -m mcp_servers.vector_search_server.stdio_server
```

## Notes

- The stdio servers are separate from the HTTP/SSE servers
- You can run both simultaneously (stdio for Cursor, HTTP for your agent)
- The stdio servers use the same tool definitions as HTTP servers
- All servers share the same configuration from `config/settings.py`

## Support

If you encounter issues:

1. Check Cursor's developer console for errors
2. Test servers manually to isolate issues
3. Verify all dependencies are installed
4. Check that paths are correct and absolute
