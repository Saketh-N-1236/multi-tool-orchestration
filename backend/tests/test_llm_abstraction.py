"""Tests for LLM abstraction layer."""

import pytest
from unittest.mock import Mock, patch
from llm.base import LLMProvider
from llm.factory import LLMFactory
from llm.models import LLMRequest, EmbeddingRequest
from config.settings import Settings


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""
    
    def __init__(self, provider_name: str, model_name: str):
        self._provider_name = provider_name
        self._model_name = model_name
    
    @property
    def provider_name(self) -> str:
        return self._provider_name
    
    @property
    def model_name(self) -> str:
        return self._model_name
    
    @property
    def supports_streaming(self) -> bool:
        return True
    
    async def chat_completion(self, request):
        from llm.models import LLMResponse
        return LLMResponse(
            content="Test response",
            model=self._model_name,
            provider=self._provider_name
        )
    
    async def get_embeddings(self, request):
        from llm.models import EmbeddingResponse
        return EmbeddingResponse(
            embeddings=[[0.1, 0.2, 0.3] for _ in request.texts],
            model=self._model_name,
            provider=self._provider_name
        )


def test_llm_factory_available_providers():
    """Test that factory returns available providers."""
    providers = LLMFactory.get_available_providers()
    assert "gemini" in providers
    assert "openai" in providers
    assert "anthropic" in providers
    assert "ollama" in providers


def test_llm_factory_unsupported_provider():
    """Test that factory raises error for unsupported provider."""
    settings = Settings(llm_provider="invalid_provider")
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        LLMFactory.create_provider(settings)


def test_llm_factory_missing_api_key():
    """Test that factory raises error when API key is missing."""
    settings = Settings(llm_provider="gemini", gemini_api_key=None)
    with pytest.raises(ValueError, match="API key is required"):
        LLMFactory.create_provider(settings)


@pytest.mark.asyncio
async def test_llm_provider_interface():
    """Test that LLM provider interface works correctly."""
    provider = MockLLMProvider("test", "test-model")
    
    request = LLMRequest(
        messages=[{"role": "user", "content": "Hello"}],
        temperature=0.7
    )
    
    response = await provider.chat_completion(request)
    assert response.content == "Test response"
    assert response.provider == "test"
    assert response.model == "test-model"
    
    embedding_request = EmbeddingRequest(texts=["test"])
    embedding_response = await provider.get_embeddings(embedding_request)
    assert len(embedding_response.embeddings) == 1
    assert embedding_response.provider == "test"
