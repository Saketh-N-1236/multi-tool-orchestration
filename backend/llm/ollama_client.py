"""Ollama LLM provider implementation."""

import httpx
import logging
from typing import List, Dict, Any
from llm.base import LLMProvider
from llm.models import LLMRequest, LLMResponse, EmbeddingRequest, EmbeddingResponse

logger = logging.getLogger(__name__)


class OllamaClient(LLMProvider):
    """Ollama LLM provider implementation for local inference."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        chat_model: str = "llama3.2",
        embedding_model: str = "nomic-embed-text",
        timeout: int = 300
    ):
        """Initialize Ollama client.
        
        Args:
            base_url: Ollama server URL
            chat_model: Model name for chat completion
            embedding_model: Model name for embeddings
            timeout: Request timeout in seconds (default: 300 for model loading)
        """
        self._base_url = base_url.rstrip('/')
        self._chat_model = chat_model
        self._embedding_model = embedding_model
        self._timeout = timeout
        # Use a longer timeout for Ollama (models may need time to load)
        self._client = httpx.AsyncClient(timeout=float(timeout))
    
    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "ollama"
    
    @property
    def model_name(self) -> str:
        """Return model name."""
        return self._chat_model
    
    @property
    def supports_streaming(self) -> bool:
        """Ollama supports streaming."""
        return True
    
    async def chat_completion(self, request: LLMRequest) -> LLMResponse:
        """Generate chat completion using Ollama.
        
        Args:
            request: LLM request with messages and parameters
            
        Returns:
            LLMResponse with generated content
        """
        try:
            # Convert messages to Ollama format
            messages = []
            for msg in request.messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                # Ollama uses 'system', 'user', 'assistant' roles
                if role in ["system", "user", "assistant"]:
                    messages.append({"role": role, "content": content})
                elif role == "model":
                    # Convert 'model' to 'assistant' for Ollama
                    messages.append({"role": "assistant", "content": content})
            
            # Prepare request
            # Set stream: false to get a single complete response instead of streaming
            payload = {
                "model": self._chat_model,
                "messages": messages,
                "stream": False,  # Important: disable streaming to get complete response
                "options": {
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens,
                }
            }
            
            if request.top_p is not None:
                payload["options"]["top_p"] = request.top_p
            
            # Make API call
            response = await self._client.post(
                f"{self._base_url}/api/chat",
                json=payload
            )
            
            # Check for HTTP errors
            if response.status_code != 200:
                error_detail = f"HTTP {response.status_code}"
                try:
                    error_body = response.json()
                    if "error" in error_body:
                        error_detail = error_body["error"]
                    elif "message" in error_body:
                        error_detail = error_body["message"]
                except (ValueError, json.JSONDecodeError):
                    error_detail = response.text or f"HTTP {response.status_code}"
                
                # Provide specific error messages for common issues
                if response.status_code == 404:
                    raise Exception(
                        f"Ollama API error: Model '{self._chat_model}' not found. "
                        f"Please pull the model first: 'ollama pull {self._chat_model}'. "
                        f"Server: {self._base_url}"
                    )
                elif response.status_code == 500:
                    raise Exception(
                        f"Ollama API error: Server error (500). "
                        f"Details: {error_detail}. "
                        f"Model: {self._chat_model}, Server: {self._base_url}"
                    )
                else:
                    raise Exception(
                        f"Ollama API error: {error_detail} "
                        f"(Status: {response.status_code}, Model: {self._chat_model})"
                    )
            
            result = response.json()
            
            # Check if response has error field
            if "error" in result:
                raise Exception(
                    f"Ollama API error: {result['error']}. "
                    f"Model: {self._chat_model}, Server: {self._base_url}"
                )
            
            # Extract response
            content = result.get("message", {}).get("content", "")
            done_reason = result.get("done_reason", "")
            
            # Check for blocking or filtering
            if not content:
                # Check if there's a specific reason for empty content
                if done_reason and done_reason not in ["stop", "end"]:
                    raise Exception(
                        f"Ollama API returned empty response. "
                        f"Done reason: {done_reason}. "
                        f"This might indicate content was filtered or blocked. "
                        f"Model: {self._chat_model}, Server: {self._base_url}"
                    )
                
                # Check if model actually generated tokens
                eval_count = result.get("eval_count", 0)
                if eval_count == 0:
                    raise Exception(
                        f"Ollama API returned empty response - model generated no tokens. "
                        f"This might indicate: "
                        f"1) The prompt was too long or invalid, "
                        f"2) The model needs to be pulled/updated, "
                        f"3) There's an issue with the model. "
                        f"Model: {self._chat_model}, Server: {self._base_url}. "
                        f"Try: 'ollama pull {self._chat_model}' or check the model status."
                    )
                else:
                    # Model generated tokens but content is empty - might be a parsing issue
                    raise Exception(
                        f"Ollama API returned empty content despite generating {eval_count} tokens. "
                        f"Done reason: {done_reason}. "
                        f"This might indicate a response parsing issue or content filtering. "
                        f"Model: {self._chat_model}, Server: {self._base_url}. "
                        f"Full response: {result}"
                    )
            
            # Build usage info if available
            usage = None
            if "prompt_eval_count" in result or "eval_count" in result:
                usage = {
                    "prompt_tokens": result.get("prompt_eval_count", 0),
                    "completion_tokens": result.get("eval_count", 0),
                    "total_tokens": result.get("prompt_eval_count", 0) + result.get("eval_count", 0),
                }
            
            return LLMResponse(
                content=content,
                model=self._chat_model,
                provider=self.provider_name,
                usage=usage,
                finish_reason=result.get("done_reason")
            )
            
        except httpx.ConnectError as e:
            raise Exception(
                f"Ollama connection error: Cannot connect to Ollama server at {self._base_url}. "
                f"Make sure Ollama is running: 'ollama serve' or check if the server is accessible. "
                f"Error: {str(e)}"
            )
        except httpx.TimeoutException as e:
            raise Exception(
                f"Ollama timeout error: Request to {self._base_url} timed out after {self._timeout} seconds. "
                f"This usually happens when: "
                f"1) The model '{self._chat_model}' is loading for the first time (can take 1-5 minutes), "
                f"2) The model is very large and needs more time, "
                f"3) Your system is under heavy load. "
                f"Solutions: "
                f"1) Pre-load the model: 'ollama run {self._chat_model}' (let it load, then Ctrl+C), "
                f"2) Increase timeout in .env: OLLAMA_TIMEOUT=600 (10 minutes), "
                f"3) Try again in a few moments. "
                f"Error: {str(e)}"
            )
        except httpx.HTTPStatusError as e:
            error_msg = str(e)
            status_code = e.response.status_code if hasattr(e, 'response') else None
            if status_code == 404:
                raise Exception(
                    f"Ollama API error: Model '{self._chat_model}' not found. "
                    f"Please pull the model first: 'ollama pull {self._chat_model}'"
                )
            raise Exception(
                f"Ollama API HTTP error: {error_msg} "
                f"(Status: {status_code}, Model: {self._chat_model})"
            )
        except httpx.HTTPError as e:
            raise Exception(
                f"Ollama API HTTP error: {str(e)}. "
                f"Server: {self._base_url}, Model: {self._chat_model}"
            )
        except Exception as e:
            error_msg = str(e) if str(e) else repr(e)
            raise Exception(
                f"Ollama error: {error_msg}. "
                f"Server: {self._base_url}, Model: {self._chat_model}"
            )
    
    async def get_embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Get embeddings using Ollama.
        
        Args:
            request: Embedding request with texts
            
        Returns:
            EmbeddingResponse with embeddings
            
        Raises:
            Exception: If embedding generation fails
        """
        try:
            embeddings = []
            
            # Ollama processes one text at a time
            for text in request.texts:
                # Truncate very long texts (Ollama has context limits)
                max_text_length = 2048  # nomic-embed-text has 2048 context length
                if len(text) > max_text_length:
                    logger.warning(
                        f"Text length ({len(text)}) exceeds model context ({max_text_length}). "
                        f"Truncating to first {max_text_length} characters."
                    )
                    text = text[:max_text_length]
                
                payload = {
                    "model": self._embedding_model,
                    "prompt": text
                }
                
                try:
                    logger.debug(
                        f"Calling Ollama embeddings API: {self._base_url}/api/embeddings "
                        f"with model={self._embedding_model}, text_length={len(text)}"
                    )
                    
                    response = await self._client.post(
                        f"{self._base_url}/api/embeddings",
                        json=payload,
                        timeout=self._timeout
                    )
                    
                    logger.debug(f"Ollama embeddings API response status: {response.status_code}")
                    
                    response.raise_for_status()
                    result = response.json()
                    
                    # Extract embedding
                    embedding = result.get("embedding", [])
                    if not embedding:
                        logger.error(f"No embedding in response: {result}")
                        raise ValueError(f"No embedding returned for text: {text[:50]}...")
                    
                    logger.debug(f"Successfully generated embedding of dimension {len(embedding)}")
                    embeddings.append(embedding)
                    
                except httpx.HTTPStatusError as e:
                    # Handle specific HTTP errors
                    status_code = e.response.status_code
                    error_detail = ""
                    try:
                        error_body = e.response.json()
                        error_detail = error_body.get("error", {}).get("message", str(e))
                        logger.error(
                            f"Ollama embeddings API error ({status_code}): {error_detail}. "
                            f"Response body: {error_body}"
                        )
                    except Exception as parse_error:
                        error_detail = str(e)
                        try:
                            error_text = e.response.text
                            logger.error(
                                f"Ollama embeddings API error ({status_code}): {error_detail}. "
                                f"Response text: {error_text[:500]}"
                            )
                        except:
                            logger.error(f"Ollama embeddings API error ({status_code}): {error_detail}")
                    
                    if status_code == 404:
                        raise Exception(
                            f"Ollama embedding model '{self._embedding_model}' not found. "
                            f"Please ensure the model is installed. "
                            f"Run: ollama pull {self._embedding_model}"
                        )
                    elif status_code == 500:
                        raise Exception(
                            f"Ollama embedding API error (500): {error_detail}. "
                            f"This usually means:\n"
                            f"1. The embedding model '{self._embedding_model}' is not installed. "
                            f"   Run: ollama pull {self._embedding_model}\n"
                            f"2. The model doesn't support embeddings. "
                            f"   Try a different model like 'nomic-embed-text' or 'all-minilm'\n"
                            f"3. Ollama server is having issues. Check: ollama list"
                        )
                    else:
                        raise Exception(
                            f"Ollama embedding API error ({status_code}): {error_detail}"
                        )
                except httpx.TimeoutException:
                    raise Exception(
                        f"Ollama embedding API timeout. "
                        f"The model '{self._embedding_model}' might be loading. "
                        f"Try again in a few moments."
                    )
                except httpx.RequestError as e:
                    raise Exception(
                        f"Ollama embedding API connection error: {str(e)}. "
                        f"Ensure Ollama is running at {self._base_url}"
                    )
            
            return EmbeddingResponse(
                embeddings=embeddings,
                model=self._embedding_model,
                provider=self.provider_name,
                usage=None  # Ollama doesn't provide detailed usage for embeddings
            )
            
        except Exception as e:
            # Re-raise if it's already a formatted Exception
            if isinstance(e, Exception) and "Ollama" in str(e):
                raise
            # Otherwise, wrap it
            raise Exception(f"Ollama embedding error: {str(e)}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._client.aclose()
    
    def __del__(self):
        """Cleanup on deletion."""
        try:
            if hasattr(self, '_client'):
                # Note: httpx client cleanup should be done explicitly
                pass
        except:
            pass
