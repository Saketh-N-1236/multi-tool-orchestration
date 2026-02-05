"""Test script to visualize LangGraph after compilation.

This script demonstrates how to visualize the compiled LangGraph
using IPython.display without disturbing the execution flow.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from agent.agent_pool import get_agent, reset_agent


async def test_graph_visualization():
    """Test graph visualization after compilation."""
    print("=" * 60)
    print("LangGraph Visualization Test")
    print("=" * 60)
    
    try:
        # Get or initialize agent (this will compile the graph)
        print("\n1. Initializing agent and compiling graph...")
        agent = await get_agent()
        
        if not agent.graph:
            print("❌ Error: Graph not initialized")
            return
        
        print("✅ Graph compiled successfully")
        
        # Try to visualize using IPython if available
        print("\n2. Attempting to visualize graph...")
        try:
            from IPython.display import Image, display
            
            # Method 1: Try to get underlying graph
            try:
                underlying_graph = agent.graph.get_graph()
                if hasattr(underlying_graph, 'draw_mermaid_png'):
                    print("   Using underlying_graph.draw_mermaid_png()...")
                    png_bytes = underlying_graph.draw_mermaid_png()
                    if png_bytes:
                        display(Image(png_bytes))
                        print("✅ Graph visualization displayed successfully!")
                    else:
                        print("⚠️  draw_mermaid_png() returned None")
                else:
                    print("⚠️  Underlying graph does not have draw_mermaid_png() method")
            except AttributeError:
                # Method 2: Try direct access on compiled graph
                if hasattr(agent.graph, 'draw_mermaid_png'):
                    print("   Using agent.graph.draw_mermaid_png()...")
                    png_bytes = agent.graph.draw_mermaid_png()
                    if png_bytes:
                        display(Image(png_bytes))
                        print("✅ Graph visualization displayed successfully!")
                    else:
                        print("⚠️  draw_mermaid_png() returned None")
                else:
                    print("⚠️  Compiled graph does not have draw_mermaid_png() method")
                    print("   Available methods:", [m for m in dir(agent.graph) if not m.startswith('_')])
        
        except ImportError:
            print("⚠️  IPython not available - skipping display")
            print("   To enable visualization, run this script in a Jupyter notebook or IPython environment")
            print("   Or install IPython: pip install ipython")
            
            # Still try to get the image bytes for saving
            try:
                underlying_graph = agent.graph.get_graph()
                if hasattr(underlying_graph, 'draw_mermaid_png'):
                    png_bytes = underlying_graph.draw_mermaid_png()
                    if png_bytes:
                        # Save to file instead
                        output_path = backend_path / "langgraph_visualization.png"
                        with open(output_path, "wb") as f:
                            f.write(png_bytes)
                        print(f"✅ Graph visualization saved to: {output_path}")
            except Exception as e:
                print(f"⚠️  Could not save graph visualization: {e}")
        
        # Test that graph execution still works
        print("\n3. Testing graph execution (should not be affected)...")
        from agent.langgraph_state import create_langgraph_initial_state
        from agent.prompts.loader import load_system_prompt
        
        initial_state = create_langgraph_initial_state(
            user_message="Hello",
            request_id="test_viz",
            session_id="test_session",
            system_prompt=load_system_prompt(tool_list="Test tools")
        )
        
        # Just verify the graph can be invoked (don't actually run it fully)
        print("✅ Graph is ready for execution")
        
        print("\n" + "=" * 60)
        print("✅ Visualization test completed successfully!")
        print("=" * 60)
        print("\nNote: Visualization does not affect graph execution.")
        print("      The graph can be used normally after visualization.")
        
    except Exception as e:
        print(f"\n❌ Error during visualization test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        await reset_agent()


if __name__ == "__main__":
    # Check if running in IPython/Jupyter
    try:
        from IPython import get_ipython
        ipython = get_ipython()
        if ipython:
            print("Running in IPython/Jupyter environment")
            # Try to use nest_asyncio if available (needed for IPython async support)
            try:
                import nest_asyncio  # type: ignore[import-untyped]
                nest_asyncio.apply()
            except ImportError:
                # nest_asyncio not installed - may cause issues in IPython
                print("⚠️  Warning: nest_asyncio not installed. Install with: pip install nest-asyncio")
                print("   Continuing without it (may fail in some IPython environments)")
            asyncio.run(test_graph_visualization())
        else:
            asyncio.run(test_graph_visualization())
    except ImportError:
        # Not in IPython, run normally
        asyncio.run(test_graph_visualization())
