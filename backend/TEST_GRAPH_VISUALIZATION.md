# How to Test Graph Visualization

This guide provides step-by-step instructions to test the LangGraph visualization feature.

## Prerequisites

1. **MCP Servers Running**: The graph needs tools to be discovered
2. **Dependencies Installed**: 
   ```bash
   pip install langgraph ipython  # IPython is optional but recommended
   ```

## Testing Methods

### Method 1: Test Script (Easiest)

This is the simplest way to test visualization.

#### Step 1: Start MCP Servers

```bash
cd backend
python scripts/start_servers.py
```

Keep this terminal running. In a new terminal:

#### Step 2: Run Test Script

**Option A: In Regular Python**
```bash
cd backend
python test_graph_visualization.py
```

**Expected Output:**
```
============================================================
LangGraph Visualization Test
============================================================

1. Initializing agent and compiling graph...
✅ Graph compiled successfully

2. Attempting to visualize graph...
⚠️  IPython not available - skipping display
   To enable visualization, run this script in a Jupyter notebook or IPython environment
   Or install IPython: pip install ipython
✅ Graph visualization saved to: backend/langgraph_visualization.png

3. Testing graph execution (should not be affected)...
✅ Graph is ready for execution

============================================================
✅ Visualization test completed successfully!
============================================================
```

**Option B: In IPython/Jupyter**
```python
# In Jupyter notebook or IPython
%run test_graph_visualization.py
```

The graph image will be displayed inline in the notebook.

---

### Method 2: API Endpoint Test

Test the HTTP API endpoint that returns the graph as PNG.

#### Step 1: Start MCP Servers
```bash
cd backend
python scripts/start_servers.py
```

#### Step 2: Start API Server
In a new terminal:
```bash
cd backend
python scripts/start_api.py
```

#### Step 3: Initialize Agent (Required)
The agent must be initialized before accessing the visualization endpoint. Make a chat request:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "test",
    "session_id": "test_session"
  }'
```

#### Step 4: Get Graph Visualization
```bash
# Download as PNG file
curl http://localhost:8000/api/v1/graph/visualization --output graph.png

# Or open in browser
# Navigate to: http://localhost:8000/api/v1/graph/visualization
```

**Expected Result:**
- Browser: PNG image displays directly
- curl: File `graph.png` is saved

**Error Handling:**
- `503 Service Unavailable`: Agent not initialized (make a chat request first)
- `501 Not Implemented`: Graph doesn't support visualization (check LangGraph version)
- `500 Internal Server Error`: Check server logs

---

### Method 3: Manual Test in IPython/Jupyter

Test visualization programmatically in a notebook.

#### Step 1: Start MCP Servers
```bash
cd backend
python scripts/start_servers.py
```

#### Step 2: Open Jupyter/IPython
```bash
cd backend
jupyter notebook
# or
ipython
```

#### Step 3: Run Test Code
```python
from IPython.display import Image, display
from agent.agent_pool import get_agent
import asyncio

# Initialize agent (compiles graph)
agent = await get_agent()

# Get underlying graph
underlying_graph = agent.graph.get_graph()

# Check if visualization is supported
print(f"Has draw_mermaid_png: {hasattr(underlying_graph, 'draw_mermaid_png')}")

# Generate and display PNG
if hasattr(underlying_graph, 'draw_mermaid_png'):
    png_bytes = underlying_graph.draw_mermaid_png()
    if png_bytes:
        display(Image(png_bytes))
        print("✅ Graph visualization displayed!")
    else:
        print("⚠️  draw_mermaid_png() returned None")
else:
    print("⚠️  Graph does not support draw_mermaid_png()")
    print(f"Available methods: {[m for m in dir(underlying_graph) if 'draw' in m.lower() or 'visual' in m.lower()]}")
```

**Expected Result:**
- Graph image displays inline in the notebook
- Console shows success message

---

### Method 4: Test Automatic Visualization

Test the automatic visualization that happens after graph compilation.

#### Step 1: Enable Automatic Visualization

Edit `backend/.env` or set environment variable:
```bash
# In .env file
ENABLE_GRAPH_VISUALIZATION=true
```

Or in Python:
```python
import os
os.environ['ENABLE_GRAPH_VISUALIZATION'] = 'true'
```

#### Step 2: Start MCP Servers
```bash
cd backend
python scripts/start_servers.py
```

#### Step 3: Run in IPython/Jupyter
```python
# In Jupyter notebook
from agent.agent_pool import get_agent

# This will automatically display the graph after compilation
agent = await get_agent()
```

**Expected Result:**
- Graph image appears automatically after `get_agent()` completes
- No manual visualization code needed

**Note:** Automatic visualization only works in IPython/Jupyter environments.

---

## Verification Checklist

After running any test method, verify:

- [ ] Graph compiled successfully (no errors)
- [ ] Visualization generated (PNG bytes or image displayed)
- [ ] Graph execution still works (can make chat requests)
- [ ] No errors in logs related to visualization

## Troubleshooting

### Issue: "Graph not initialized"
**Solution:** Make a chat request first to initialize the agent:
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test"}'
```

### Issue: "draw_mermaid_png() method not found"
**Possible Causes:**
1. LangGraph version doesn't support visualization
2. Graph structure doesn't support visualization

**Solution:**
```bash
# Check LangGraph version
pip show langgraph

# Update if needed
pip install --upgrade langgraph
```

### Issue: "IPython not available"
**Solution:**
```bash
# Install IPython
pip install ipython

# Or use API endpoint instead (works without IPython)
curl http://localhost:8000/api/v1/graph/visualization --output graph.png
```

### Issue: "MCP servers not available"
**Solution:**
```bash
# Start MCP servers first
cd backend
python scripts/start_servers.py
```

### Issue: Visualization works but graph execution fails
**This shouldn't happen** - visualization is non-blocking. If it does:
1. Check logs for actual error
2. Verify MCP servers are running
3. Check agent initialization logs

## Quick Test Commands

```bash
# 1. Start everything
cd backend
python scripts/start_servers.py &  # In background
python scripts/start_api.py &      # In background

# 2. Initialize agent
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test"}'

# 3. Get visualization
curl http://localhost:8000/api/v1/graph/visualization --output graph.png

# 4. View the image
# On Windows: start graph.png
# On Mac: open graph.png
# On Linux: xdg-open graph.png
```

## Expected Graph Structure

The visualization should show:
- **Entry point**: `agent` node
- **Agent node**: Calls LLM with tools
- **Conditional edge**: Routes to `tools` or `end`
- **Tools node**: Executes tool calls
- **Edge**: `tools` → `agent` (loop back)

## Next Steps

After successful testing:
1. Use visualization for debugging graph structure
2. Share graph images in documentation
3. Use API endpoint in frontend to display graph
4. Enable automatic visualization in development notebooks
