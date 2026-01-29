"""Example demonstrating hybrid embedding approach with Ollama and Gemini."""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from config.settings import get_settings
from llm.factory import LLMFactory
from llm.models import EmbeddingRequest

# Load environment variables
load_dotenv()


async def test_embeddings(provider_name: str, texts: list):
    """Test embeddings with a specific provider."""
    print(f"\n{'='*60}")
    print(f"Testing {provider_name.upper()} Embeddings")
    print(f"{'='*60}")
    
    try:
        settings = get_settings()
        
        # Create embedding provider
        if provider_name == "ollama":
            settings.embedding_provider = "ollama"
        elif provider_name == "gemini":
            settings.embedding_provider = "gemini"
        
        embedding_provider = LLMFactory.create_embedding_provider(settings)
        print(f"Created provider: {embedding_provider}")
        
        # Create embedding request
        embedding_request = EmbeddingRequest(texts=texts)
        
        # Get embeddings
        print(f"\nGenerating embeddings for {len(texts)} texts...")
        embedding_response = await embedding_provider.get_embeddings(embedding_request)
        
        print(f"[SUCCESS]")
        print(f"   Provider: {embedding_response.provider}")
        print(f"   Model: {embedding_response.model}")
        print(f"   Number of embeddings: {len(embedding_response.embeddings)}")
        print(f"   Embedding dimension: {len(embedding_response.embeddings[0])}")
        print(f"   First embedding sample: {embedding_response.embeddings[0][:5]}...")
        
        return embedding_response
        
    except Exception as e:
        print(f"[ERROR] Error with {provider_name}: {str(e)}")
        return None


async def compare_embeddings():
    """Compare embeddings from different providers."""
    print("\n" + "="*60)
    print("HYBRID EMBEDDING APPROACH DEMONSTRATION")
    print("="*60)
    
    # Test texts
    test_texts = [
        "Machine learning is a subset of artificial intelligence",
        "Deep learning uses neural networks with multiple layers",
        "Natural language processing helps computers understand text"
    ]
    
    print(f"\nTest texts:")
    for i, text in enumerate(test_texts, 1):
        print(f"  {i}. {text}")
    
    # Test Ollama embeddings
    ollama_result = await test_embeddings("ollama", test_texts)
    
    # Test Gemini embeddings
    gemini_result = await test_embeddings("gemini", test_texts)
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    if ollama_result:
        print(f"[OK] Ollama: Working")
        print(f"   - Model: {ollama_result.model}")
        print(f"   - Dimension: {len(ollama_result.embeddings[0])}")
    else:
        print(f"[FAIL] Ollama: Not available (check if Ollama is running)")
        print(f"   Install: https://ollama.ai")
        print(f"   Run: ollama pull nomic-embed-text")
    
    if gemini_result:
        print(f"[OK] Gemini: Working")
        print(f"   - Model: {gemini_result.model}")
        print(f"   - Dimension: {len(gemini_result.embeddings[0])}")
    else:
        print(f"[FAIL] Gemini: Not available")
        print(f"   - Likely quota limit (free tier restrictions)")
        print(f"   - Or check API key in .env file")
        print(f"   - This is OK - you're using Ollama for embeddings anyway!")
    
    print(f"\n[TIP] You can switch embedding providers via EMBEDDING_PROVIDER in .env")
    print(f"   - EMBEDDING_PROVIDER=ollama  (for local, cost-effective)")
    print(f"   - EMBEDDING_PROVIDER=gemini  (for cloud, high-quality)")


async def main():
    """Main function."""
    settings = get_settings()
    
    print("\nCurrent Configuration:")
    print(f"  LLM Provider: {settings.llm_provider}")
    print(f"  Embedding Provider: {settings.embedding_provider}")
    print(f"  Ollama URL: {settings.ollama_base_url}")
    print(f"  Ollama Embedding Model: {settings.ollama_embedding_model}")
    
    await compare_embeddings()


if __name__ == "__main__":
    asyncio.run(main())
