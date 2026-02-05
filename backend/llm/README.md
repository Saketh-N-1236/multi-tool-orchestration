# LLM Provider Abstraction

This module provides a clean abstraction layer for multiple LLM providers, allowing easy switching between different providers without changing application code.

## 🎯 Hybrid Embedding Support

**NEW**: This module now supports **hybrid embeddings** - use Ollama (local) or Gemini (cloud) for embeddings independently of your LLM provider choice. See [docs/guides/hybrid_embeddings.md](../docs/guides/hybrid_embeddings.md) for details.

## Architecture

### Components

1. **`base.py`** - Abstract base class (`LLMProvider`) that all providers must implement
2. **`factory.py`** - Factory pattern for creating provider instances based on configuration
3. **`models.py`** - Common Pydantic models for requests and responses
4. **Provider Implementations**:
   - `gemini_client.py` - Google Gemini implementation (fully implemented)
   - `openai_client.py` - OpenAI implementation (placeholder)
   - `anthropic_client.py` - Anthropic implementation (placeholder)

## Hybrid Embedding Approach

You can use different providers for chat and embeddings:

```python
# Use Gemini for chat, Ollama for embeddings (cost-effective)
settings.llm_provider = "gemini"
settings.embedding_provider = "ollama"

llm_provider = LLMFactory.create_provider(settings)
embedding_provider = LLMFactory.create_embedding_provider(settings)
```

See [docs/guides/hybrid_embeddings.md](../docs/guides/hybrid_embeddings.md) for complete guide.

## Usage

### Basic Usage

```python
from config.settings import get_settings
from llm.factory import LLMFactory
from llm.models import LLMRequest

# Get settings
settings = get_settings()

# Create provider (automatically selects based on LLM_PROVIDER env var)
llm_provider = LLMFactory.create_provider(settings)

# Make a request
request = LLMRequest(
    messages=[
        {"role": "user", "content": "Hello, how are you?"}
    ],
    temperature=0.7,
    max_tokens=1000
)

# Get response
response = await llm_provider.chat_completion(request)
print(response.content)
```

### Switching Providers

Simply change the `LLM_PROVIDER` environment variable:

```bash
# Use Gemini
LLM_PROVIDER=gemini

# Use OpenAI (when implemented)
LLM_PROVIDER=openai

# Use Anthropic (when implemented)
LLM_PROVIDER=anthropic
```

### Getting Embeddings

```python
from llm.models import EmbeddingRequest

request = EmbeddingRequest(texts=["Hello world", "AI is great"])
response = await llm_provider.get_embeddings(request)

# response.embeddings is a list of embedding vectors
for embedding in response.embeddings:
    print(f"Embedding dimension: {len(embedding)}")
```

## Adding a New Provider

1. Create a new file (e.g., `new_provider_client.py`)
2. Inherit from `LLMProvider` and implement all abstract methods
3. Add provider creation logic to `factory.py`
4. Add configuration to `config/settings.py`
5. Update `.env.example` with new provider settings

Example:

```python
# llm/new_provider_client.py
from llm.base import LLMProvider
from llm.models import LLMRequest, LLMResponse, EmbeddingRequest, EmbeddingResponse

class NewProviderClient(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self._api_key = api_key
        self._model_name = model
        # Initialize your client here
    
    @property
    def provider_name(self) -> str:
        return "new_provider"
    
    @property
    def model_name(self) -> str:
        return self._model_name
    
    @property
    def supports_streaming(self) -> bool:
        return True
    
    async def chat_completion(self, request: LLMRequest) -> LLMResponse:
        # Implement chat completion
        pass
    
    async def get_embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        # Implement embeddings
        pass
```

## Benefits

1. **Provider Agnostic**: Application code doesn't depend on specific providers
2. **Easy Testing**: Mock providers for unit tests
3. **Flexible Configuration**: Switch providers via environment variables
4. **Consistent Interface**: All providers follow the same interface
5. **Extensible**: Easy to add new providers

## Configuration

All provider settings are in `config/settings.py` and can be set via environment variables:

- `LLM_PROVIDER` - Provider to use (gemini, openai, anthropic)
- `GEMINI_API_KEY` - Gemini API key
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key
- `LLM_TEMPERATURE` - Temperature for all providers
- `LLM_MAX_TOKENS` - Max tokens for all providers

See `.env.example` for all available configuration options.
