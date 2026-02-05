"""Test script for fully LangGraph implementation."""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from agent.langgraph_agent import LangGraphAgent
from agent.mcp_sdk_client import MCPSDKClient
import uuid

async def test_langgraph_full():
    """Test LangGraph agent with MCP SDK."""
    print("="*60)
    print("Testing Full LangGraph + MCP SDK Implementation")
    print("="*60)
    
    # Test MCP SDK client initialization
    print("\n1. Testing MCP SDK Client...")
    try:
        mcp_client = MCPSDKClient()
        await mcp_client.initialize()
        print("   [OK] MCP SDK Client initialized")
        
        # Test tool discovery
        print("\n2. Testing tool discovery...")
        all_tools = await mcp_client.discover_all_tools()
        total_tools = sum(len(tools) for tools in all_tools.values())
        print(f"   [OK] Discovered {total_tools} tools from {len(all_tools)} servers")
        for server_name, tools in all_tools.items():
            print(f"      - {server_name}: {len(tools)} tools")
        
        await mcp_client.close()
    except Exception as e:
        print(f"   [ERROR] MCP SDK Client failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test LangGraph agent
    print("\n3. Testing LangGraph Agent...")
    request_id = str(uuid.uuid4())
    
    try:
        async with LangGraphAgent() as agent:
            await agent.initialize()
            print("   [OK] LangGraph Agent initialized")
            
            print(f"\n4. Testing agent query...")
            print(f"   Request ID: {request_id}")
            print(f"   Query: 'What tables are in the database?'")
            print("   Processing...")
            
            state = await agent.invoke(
                user_message="What tables are in the database?",
                request_id=request_id
            )
            
            print("\n" + "="*60)
            print("Agent Response:")
            print("="*60)
            
            # Get assistant's final message
            assistant_messages = [m for m in state["messages"] if m["role"] == "assistant"]
            if assistant_messages:
                print(assistant_messages[-1]["content"])
            else:
                print("[WARNING] No assistant message found")
            
            print("\n" + "="*60)
            print("Tool Calls Made:")
            print("="*60)
            tool_calls = state.get("tool_calls", [])
            if tool_calls:
                for i, tool_call in enumerate(tool_calls, 1):
                    print(f"{i}. {tool_call['tool_name']}")
                    print(f"   Params: {tool_call.get('params', {})}")
            else:
                print("No tool calls made")
            
            print("\n" + "="*60)
            print("[SUCCESS] LangGraph implementation is working!")
            print("="*60)
    
    except Exception as e:
        print(f"\n[ERROR] Agent test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_langgraph_full())
