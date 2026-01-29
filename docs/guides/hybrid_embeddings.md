# Hybrid Embedding Approach

This project supports a **hybrid embedding approach** that allows you to use either **Ollama** (local) or **Gemini** (cloud) for embeddings, independently of your LLM provider choice.

## Why Hybrid Embeddings?

### Benefits:
- **Cost Optimization**: Use Ollama for high-volume, Gemini for quality-critical
- **Privacy Control**: Ollama keeps data local, Gemini for non-sensitive data
- **Flexibility**: Switch providers via configuration, no code changes
- **Fallback**: Use Gemini if Ollama is unavailable
- **Quality Testing**: Compare embeddings side-by-side

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Embedding Provider Selection
EMBEDDING_PROVIDER=ollama  # or "gemini"

# Ollama Configuration (if using Ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=llama3
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
```

### Settings

The embedding provider is **independent** of your LLM provider:

```python
# You can use Gemini for chat, Ollama for embeddings
LLM_PROVIDER=gemini
EMBEDDING_PROVIDER=ollama

# Or both from the same provider
LLM_PROVIDER=gemini
EMBEDDING_PROVIDER=gemini

# Or both from Ollama
LLM_PROVIDER=ollama
EMBEDDING_PROVIDER=ollama
```

## Usage

### Basic Usage

```python
from config.settings import get_settings
from llm.factory import LLMFactory
from llm.models import EmbeddingRequest

settings = get_settings()

# Create embedding provider (independent of LLM provider)
embedding_provider = LLMFactory.create_embedding_provider(settings)

# Get embeddings
request = EmbeddingRequest(
    texts=["Machine learning is AI", "Deep learning uses neural networks"]
)

response = await embedding_provider.get_embeddings(request)
print(f"Embeddings: {response.embeddings}")
print(f"Provider: {response.provider}")
print(f"Model: {response.model}")
```

### Switching Providers

Simply change `EMBEDDING_PROVIDER` in `.env`:

```bash
# Use Ollama (local, free)
EMBEDDING_PROVIDER=ollama

# Use Gemini (cloud, paid)
EMBEDDING_PROVIDER=gemini
```

No code changes needed!

## Setup Instructions

### Ollama Setup

1. **Install Ollama**: https://ollama.ai

2. **Pull embedding model**:
   ```bash
   ollama pull nomic-embed-text
   ```

3. **Verify Ollama is running**:
   ```bash
   curl http://localhost:11434/api/tags
   ```

4. **Configure in .env**:
   ```bash
   EMBEDDING_PROVIDER=ollama
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_EMBEDDING_MODEL=nomic-embed-text
   ```

### Gemini Setup

1. **Get API key**: https://makersuite.google.com/app/apikey

2. **Configure in .env**:
   ```bash
   EMBEDDING_PROVIDER=gemini
   GEMINI_API_KEY=your_key_here
   ```

## Available Embedding Models

### Ollama Models
- `nomic-embed-text` (recommended) - 768 dimensions
- `all-minilm` - 384 dimensions
- `mxbai-embed-large` - 1024 dimensions

Pull models with: `ollama pull <model-name>`

### Gemini Models
- `models/embedding-001` (default) - 768 dimensions

## Comparison

| Feature | Ollama | Gemini |
|---------|--------|--------|
| **Cost** | Free (local) | Pay per request |
| **Privacy** | 100% local | Data sent to Google |
| **Latency** | Low (local) | Network dependent |
| **Quality** | Good | Excellent |
| **Setup** | Requires installation | API key only |
| **Scalability** | Limited by hardware | Unlimited |
| **Quota** | None | Rate limits |

## Example: Hybrid Setup

```bash
# .env configuration
LLM_PROVIDER=gemini          # Use Gemini for chat (high quality)
EMBEDDING_PROVIDER=ollama    # Use Ollama for embeddings (cost-effective)

# This allows you to:
# - Get high-quality chat responses from Gemini
# - Generate embeddings locally with Ollama (no API costs)
# - Process large volumes of embeddings without quota limits
```

## Testing

Run the hybrid embedding example:

```bash
python examples/hybrid_embedding_example.py
```

This will:
1. Test Ollama embeddings (if available)
2. Test Gemini embeddings (if API key is set)
3. Compare both providers
4. Show configuration options

## Troubleshooting

### Ollama Not Found
- Ensure Ollama is installed and running
- Check `OLLAMA_BASE_URL` is correct
- Verify model is pulled: `ollama list`

### Gemini Quota Errors
- Check API key is valid
- Wait for quota reset
- Consider switching to Ollama for high-volume

### Embedding Dimension Mismatch
- Different models have different dimensions
- Ensure you use the same model for indexing and querying
- Ollama: 768 (nomic-embed-text) or 384 (all-minilm)
- Gemini: 768 (embedding-001)

## Best Practices

1. **Development**: Use Ollama (fast, free, no API keys)
2. **Production**: Choose based on:
   - **High volume**: Ollama
   - **Quality critical**: Gemini
   - **Privacy sensitive**: Ollama
3. **Testing**: Test both and compare quality
4. **Fallback**: Implement retry logic with provider fallback

## Architecture

```
┌─────────────────┐
│  Application    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LLM Factory    │
│  (Embedding)    │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌────────┐
│ Ollama │ │ Gemini │
│ (Local)│ │ (Cloud)│
└────────┘ └────────┘
```

The factory pattern allows seamless switching between providers without code changes.
