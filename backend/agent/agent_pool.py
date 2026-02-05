"""Agent pool for reusing initialized LangGraph agents.

This module provides a singleton/pooling mechanism to avoid
re-initializing agents on every request, significantly improving
latency and reducing resource usage.
"""

import asyncio
import logging
from typing import Optional
from datetime import datetime, timedelta

from agent.langgraph_agent import LangGraphAgent

logger = logging.getLogger(__name__)

# Global agent instance (singleton)
_agent_instance: Optional[LangGraphAgent] = None
_agent_lock = asyncio.Lock()
_agent_initialized = False
_agent_last_used: Optional[datetime] = None
_agent_ttl_seconds = 3600  # Keep agent alive for 1 hour


async def get_agent() -> LangGraphAgent:
    """Get or create singleton LangGraph agent instance.
    
    This function ensures only one agent instance is created and reused
    across all requests, avoiding expensive re-initialization.
    
    Returns:
        Initialized LangGraphAgent instance
        
    Raises:
        RuntimeError: If agent initialization fails
    """
    global _agent_instance, _agent_initialized, _agent_last_used
    
    async with _agent_lock:
        # Check if agent exists and is still valid
        if _agent_instance is not None and _agent_initialized:
            # Check if agent has expired (not used for TTL period)
            if _agent_last_used:
                time_since_use = datetime.utcnow() - _agent_last_used
                if time_since_use > timedelta(seconds=_agent_ttl_seconds):
                    logger.info("Agent instance expired, recreating...")
                    try:
                        await _agent_instance.close()
                    except Exception as e:
                        logger.warning(f"Error closing expired agent: {e}")
                    _agent_instance = None
                    _agent_initialized = False
                else:
                    # Agent is still valid, update last used time
                    _agent_last_used = datetime.utcnow()
                    return _agent_instance
        
        # Create new agent instance
        if _agent_instance is None:
            logger.info("Creating new LangGraph agent instance...")
            _agent_instance = LangGraphAgent()
        
        # Initialize if not already initialized
        if not _agent_initialized:
            try:
                await _agent_instance.initialize()
                _agent_initialized = True
                _agent_last_used = datetime.utcnow()
                logger.info("LangGraph agent initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize agent: {e}", exc_info=True)
                _agent_instance = None
                _agent_initialized = False
                raise RuntimeError(f"Agent initialization failed: {e}") from e
        
        return _agent_instance


async def reset_agent():
    """Reset the singleton agent instance (useful for testing or forced refresh).
    
    This will close the current agent and force creation of a new one
    on the next get_agent() call.
    """
    global _agent_instance, _agent_initialized, _agent_last_used
    
    async with _agent_lock:
        if _agent_instance is not None:
            try:
                await _agent_instance.close()
            except Exception as e:
                logger.warning(f"Error closing agent during reset: {e}")
        
        _agent_instance = None
        _agent_initialized = False
        _agent_last_used = None
        logger.info("Agent instance reset")


async def close_agent():
    """Close the singleton agent instance (call on shutdown)."""
    await reset_agent()
