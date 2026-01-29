"""Gemini LLM provider implementation using google-genai package."""

import os
from typing import List, Dict, Any
from google import genai
from llm.base import LLMProvider
from llm.models import LLMRequest, LLMResponse, EmbeddingRequest, EmbeddingResponse


class GeminiClient(LLMProvider):
    """Gemini LLM provider implementation using google-genai."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-pro"):
        """Initialize Gemini client.
        
        Args:
            api_key: Gemini API key
            model: Model name to use
        """
        self._api_key = api_key
        self._model_name = model
        self._client = genai.Client(api_key=api_key)
    
    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "gemini"
    
    @property
    def model_name(self) -> str:
        """Return model name."""
        return self._model_name
    
    @property
    def supports_streaming(self) -> bool:
        """Gemini supports streaming."""
        return True
    
    async def chat_completion(self, request: LLMRequest) -> LLMResponse:
        """Generate chat completion using Gemini.
        
        Args:
            request: LLM request with messages and parameters
            
        Returns:
            LLMResponse with generated content
        """
        try:
            # Convert messages to format expected by google-genai
            contents = []
            system_instruction = None
            
            for msg in request.messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "system":
                    # Store system instruction - will prepend to first user message
                    system_instruction = content
                elif role == "user":
                    # Prepend system instruction to first user message if present
                    user_content = content
                    if system_instruction and not contents:
                        user_content = f"{system_instruction}\n\n{content}"
                        system_instruction = None  # Clear after using
                    contents.append({"role": "user", "parts": [{"text": user_content}]})
                elif role == "assistant":
                    contents.append({"role": "model", "parts": [{"text": content}]})
            
            # Prepare generation config
            config = {
                "temperature": request.temperature,
                "max_output_tokens": request.max_tokens,
            }
            
            if request.top_p is not None:
                config["top_p"] = request.top_p
            
            # Generate content using google-genai
            # Note: system_instruction is not a direct parameter, handled above
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=contents,
                config=config
            )
            
            # Extract response
            content = response.text if hasattr(response, 'text') else str(response)
            
            # Build usage info if available
            usage = None
            if hasattr(response, 'usage_metadata'):
                usage_metadata = response.usage_metadata
                usage = {
                    "prompt_tokens": getattr(usage_metadata, 'prompt_token_count', 0),
                    "completion_tokens": getattr(usage_metadata, 'completion_token_count', 0),
                    "total_tokens": getattr(usage_metadata, 'total_token_count', 0),
                }
            
            return LLMResponse(
                content=content,
                model=self._model_name,
                provider=self.provider_name,
                usage=usage,
                finish_reason=getattr(response, 'finish_reason', None)
            )
            
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")
    
    async def get_embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Get embeddings using Gemini.
        
        Args:
            request: Embedding request with texts
            
        Returns:
            EmbeddingResponse with embeddings
        """
        try:
            embeddings = []
            
            for text in request.texts:
                # Use the embedding API with google-genai
                # The correct API call structure for google-genai package
                response = self._client.models.embed_content(
                    model="text-embedding-004",
                    contents=text  # Note: 'contents' (plural) is the correct parameter
                )
                
                # Extract embedding from EmbedContentResponse
                # Response has 'embeddings' attribute (list of Embedding objects)
                if hasattr(response, 'embeddings') and response.embeddings:
                    # embeddings is a list, get the first one
                    embedding_obj = response.embeddings[0]
                    # Each embedding has 'values' attribute (list of floats)
                    if hasattr(embedding_obj, 'values'):
                        embeddings.append(list(embedding_obj.values))
                    elif isinstance(embedding_obj, list):
                        embeddings.append(embedding_obj)
                    else:
                        embeddings.append(list(embedding_obj))
                else:
                    raise ValueError(
                        f"No embeddings found in response. "
                        f"Response type: {type(response)}, "
                        f"Has 'embeddings': {hasattr(response, 'embeddings')}"
                    )
            
            return EmbeddingResponse(
                embeddings=embeddings,
                model="text-embedding-004",
                provider=self.provider_name,
                usage=None  # Gemini embedding API doesn't provide usage
            )
            
        except Exception as e:
            raise Exception(f"Gemini embedding API error: {str(e)}")
