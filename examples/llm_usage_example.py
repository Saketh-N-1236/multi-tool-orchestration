"""Example usage of LLM abstraction layer."""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from config.settings import get_settings
from llm.factory import LLMFactory
from llm.models import LLMRequest, EmbeddingRequest

# Load environment variables
load_dotenv()


async def main():
    """Example of using LLM abstraction."""
    
    # Get settings
    settings = get_settings()
    print(f"Using LLM Provider: {settings.llm_provider}")
    print(f"Model: {settings.gemini_model if settings.llm_provider == 'gemini' else 'N/A'}")
    print("-" * 50)
    
    # Create provider using factory
    try:
        llm_provider = LLMFactory.create_provider(settings)
        print(f"Created provider: {llm_provider}")
        print("-" * 50)
        
        # Example 1: Chat completion
        print("\n1. Chat Completion Example:")
        chat_request = LLMRequest(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is machine learning?"}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        chat_response = await llm_provider.chat_completion(chat_request)
        print(f"Response: {chat_response.content[:200]}...")
        print(f"Provider: {chat_response.provider}")
        print(f"Model: {chat_response.model}")
        if chat_response.usage:
            print(f"Usage: {chat_response.usage}")
        
        # Example 2: Embeddings
        print("\n2. Embeddings Example:")
        embedding_request = EmbeddingRequest(
            texts=[
                "Machine learning is a subset of AI",
                "Deep learning uses neural networks",
                "Natural language processing helps computers understand text"
            ]
        )
        
        embedding_response = await llm_provider.get_embeddings(embedding_request)
        print(f"Number of embeddings: {len(embedding_response.embeddings)}")
        print(f"Embedding dimension: {len(embedding_response.embeddings[0])}")
        print(f"Provider: {embedding_response.provider}")
        print(f"Model: {embedding_response.model}")
        
    except ValueError as e:
        print(f"Error: {e}")
        print("\nPlease set the appropriate API key in your .env file:")
        if settings.llm_provider == "gemini":
            print("  GEMINI_API_KEY=your_key_here")
        elif settings.llm_provider == "openai":
            print("  OPENAI_API_KEY=your_key_here")
        elif settings.llm_provider == "anthropic":
            print("  ANTHROPIC_API_KEY=your_key_here")
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
