"""Gemini LLM provider implementation using google-genai package."""

import os
import json
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
            
            # Prepare tools for function calling if provided
            # Note: Function calling support may vary by google-genai version
            # We'll try it, but fall back gracefully if not supported
            tools = None
            use_function_calling = False
            
            if request.tools:
                try:
                    # Convert to Gemini's function calling format
                    # Gemini expects: [{"functionDeclarations": [...]}]
                    function_declarations = []
                    for tool in request.tools:
                        if isinstance(tool, dict) and "name" in tool:
                            function_declarations.append(tool)
                    
                    if function_declarations:
                        tools = [{"functionDeclarations": function_declarations}]
                        use_function_calling = True
                except Exception as e:
                    # If tool formatting fails, continue without function calling
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Function calling setup failed, using text parsing: {e}")
                    use_function_calling = False
            
            # Generate content using google-genai
            # Note: system_instruction is not a direct parameter, handled above
            generate_kwargs = {
                "model": self._model_name,
                "contents": contents,
                "config": config
            }
            
            # Try to add tools if available (for function calling)
            # If the API doesn't support it, we'll catch the error and retry without tools
            try:
                if use_function_calling and tools:
                    generate_kwargs["tools"] = tools
                
                response = self._client.models.generate_content(**generate_kwargs)
            except TypeError as e:
                # If 'tools' parameter is not supported, retry without it
                if "tools" in str(e) or "unexpected keyword" in str(e).lower():
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info("Function calling not supported by this google-genai version, falling back to text parsing")
                    # Remove tools and retry
                    generate_kwargs.pop("tools", None)
                    response = self._client.models.generate_content(**generate_kwargs)
                else:
                    raise
            
            # Extract response content - handle multiple possible response structures
            content = None
            
            # Try candidates structure first (most reliable for google-genai)
            if hasattr(response, 'candidates') and response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                # Check for finish_reason to understand why content might be empty
                finish_reason = None
                if hasattr(candidate, 'finish_reason'):
                    finish_reason = candidate.finish_reason
                
                # Handle UNEXPECTED_TOOL_CALL - function calling failed, retry without tools
                if finish_reason and 'UNEXPECTED_TOOL_CALL' in str(finish_reason):
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning("Gemini returned UNEXPECTED_TOOL_CALL, retrying without function calling")
                    # Retry without tools
                    generate_kwargs_retry = {
                        "model": self._model_name,
                        "contents": contents,
                        "config": config
                    }
                    response = self._client.models.generate_content(**generate_kwargs_retry)
                    # Re-extract candidate and finish_reason after retry
                    if hasattr(response, 'candidates') and response.candidates and len(response.candidates) > 0:
                        candidate = response.candidates[0]
                        if hasattr(candidate, 'finish_reason'):
                            finish_reason = candidate.finish_reason
                
                if hasattr(candidate, 'content') and candidate.content:
                    if hasattr(candidate.content, 'parts') and candidate.content.parts:
                        # Extract text and function calls from all parts
                        text_parts = []
                        function_calls = []
                        
                        for part in candidate.content.parts:
                            # Check if part has text attribute
                            if hasattr(part, 'text'):
                                part_text = part.text
                                # Handle different types of part_text
                                if part_text is not None:
                                    # If it's already a string, use it directly
                                    if isinstance(part_text, str):
                                        if part_text:  # Only add non-empty strings
                                            text_parts.append(part_text)
                                    # If it's an object, check if it has a text attribute
                                    elif hasattr(part_text, 'text'):
                                        nested_text = part_text.text
                                        if nested_text and isinstance(nested_text, str):
                                            text_parts.append(nested_text)
                                    else:
                                        # Try string conversion, but validate it's useful
                                        text_str = str(part_text)
                                        # Reject if it looks like object representation
                                        if text_str and not (
                                            text_str.startswith('<') or 
                                            'object at 0x' in text_str or
                                            'Response' in text_str and '=' in text_str
                                        ):
                                            text_parts.append(text_str)
                            # Handle function calls (for native function calling)
                            elif hasattr(part, 'function_call'):
                                func_call = part.function_call
                                if func_call:
                                    function_calls.append({
                                        "name": getattr(func_call, 'name', ''),
                                        "args": getattr(func_call, 'args', {})
                                    })
                            # Handle inline data if present (skip for now)
                            elif hasattr(part, 'inline_data'):
                                continue
                        
                        if text_parts:
                            content = ''.join(text_parts)
                            # If content is empty and finish_reason is MAX_TOKENS, that's expected
                            if not content and finish_reason and 'MAX_TOKENS' in str(finish_reason):
                                # Content was truncated - return empty string (will be handled below)
                                content = ""
                        
                        # If we have function calls, format them as JSON tool calls
                        if function_calls:
                            # Convert function calls to our tool call format
                            tool_calls_json = []
                            for func_call in function_calls:
                                func_name = func_call.get("name", "")
                                func_args = func_call.get("args", {})
                                
                                # Convert function name back to tool key format (catalog_list_tables -> catalog::list_tables)
                                if "_" in func_name:
                                    parts = func_name.split("_", 1)
                                    if len(parts) == 2:
                                        tool_key = f"{parts[0]}::{parts[1]}"
                                    else:
                                        tool_key = func_name
                                else:
                                    tool_key = func_name
                                
                                tool_calls_json.append({
                                    "tool": tool_key,
                                    "params": func_args
                                })
                            
                            # Append tool calls as JSON to content
                            if content:
                                content += "\n\n" + json.dumps(tool_calls_json, indent=2)
                            else:
                                content = json.dumps(tool_calls_json, indent=2)
            
            # Try direct text attribute as fallback (some response formats)
            if not content and hasattr(response, 'text'):
                text_attr = response.text
                if text_attr is not None:
                    # Check if it's a callable (method) or attribute
                    if callable(text_attr):
                        try:
                            content = text_attr()
                        except (AttributeError, TypeError) as e:
                            # Silently skip if method call fails
                            pass
                    else:
                        content = str(text_attr) if text_attr else None
            
            # Check if content was blocked or filtered
            if content is None:
                # Check for safety ratings or blocking reasons
                block_reason = None
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'finish_reason'):
                        block_reason = candidate.finish_reason
                    if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
                        block_reason = "Content blocked by safety filters"
                
                # If still None, try additional extraction methods
                if content is None:
                    # Try to access text through different paths
                    try:
                        # Check if response has a method to get text
                        if hasattr(response, 'text') and callable(getattr(response, 'text', None)):
                            content = response.text()
                        # Try accessing candidates more directly
                        elif hasattr(response, 'candidates') and response.candidates:
                            candidate = response.candidates[0]
                            # Try to get text directly from candidate
                            if hasattr(candidate, 'text'):
                                candidate_text = candidate.text
                                if callable(candidate_text):
                                    content = candidate_text()
                                else:
                                    content = str(candidate_text) if candidate_text else None
                    except Exception as e:
                        # Don't use str(response) as it gives object representation
                        pass
                
                # If content is still None, check for MAX_TOKENS, UNEXPECTED_TOOL_CALL, and provide helpful error
                if content is None:
                    finish_reason_str = None
                    if hasattr(response, 'candidates') and response.candidates:
                        candidate = response.candidates[0]
                        if hasattr(candidate, 'finish_reason'):
                            finish_reason = candidate.finish_reason
                            finish_reason_str = str(finish_reason) if finish_reason else None
                    
                    # Handle UNEXPECTED_TOOL_CALL - retry without tools
                    if finish_reason_str and 'UNEXPECTED_TOOL_CALL' in finish_reason_str:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning("Gemini returned UNEXPECTED_TOOL_CALL, retrying without function calling")
                        # Retry without tools
                        generate_kwargs_retry = {
                            "model": self._model_name,
                            "contents": contents,
                            "config": config
                        }
                        response = self._client.models.generate_content(**generate_kwargs_retry)
                        # Re-extract content after retry
                        if hasattr(response, 'candidates') and response.candidates and len(response.candidates) > 0:
                            candidate = response.candidates[0]
                            if hasattr(candidate, 'content') and candidate.content:
                                if hasattr(candidate.content, 'parts') and candidate.content.parts:
                                    text_parts = []
                                    for part in candidate.content.parts:
                                        if hasattr(part, 'text'):
                                            part_text = part.text
                                            if part_text and isinstance(part_text, str):
                                                text_parts.append(part_text)
                                    if text_parts:
                                        content = ''.join(text_parts)
                    
                    # If still None after retry, raise error
                    if content is None:
                        error_msg = f"Gemini API returned empty or unparseable response"
                        if block_reason:
                            error_msg += f" (blocked: {block_reason})"
                        elif finish_reason_str and 'MAX_TOKENS' in finish_reason_str:
                            error_msg += f". Response was truncated due to max_tokens limit (finish_reason: {finish_reason_str}). Try increasing max_tokens (current: {request.max_tokens})."
                        else:
                            error_msg += f" (finish_reason: {finish_reason_str})"
                        
                        raise Exception(error_msg)
            
            # Handle empty content when MAX_TOKENS (truncated response)
            if content == "":
                # Check if it's due to MAX_TOKENS
                finish_reason_str = None
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'finish_reason'):
                        finish_reason = candidate.finish_reason
                        finish_reason_str = str(finish_reason) if finish_reason else None
                        if finish_reason_str and 'MAX_TOKENS' in finish_reason_str:
                            # Content was truncated - provide a helpful message
                            content = f"[Response truncated due to max_tokens limit ({request.max_tokens}). Please increase max_tokens to see the full response.]"
            
            # Ensure content is a string (not None)
            if not isinstance(content, str):
                if content is None:
                    content = ""
                else:
                    # Only convert to string if it doesn't look like object representation
                    content_str = str(content)
                    if content_str.startswith('<') or 'object at 0x' in content_str or ('Response' in content_str and '=' in content_str):
                        # This is object representation, not actual content
                        content = ""
                    else:
                        content = content_str
            
            # Build usage info if available
            usage = None
            if hasattr(response, 'usage_metadata'):
                usage_metadata = response.usage_metadata
                usage = {
                    "prompt_tokens": getattr(usage_metadata, 'prompt_token_count', 0),
                    "completion_tokens": getattr(usage_metadata, 'completion_token_count', 0),
                    "total_tokens": getattr(usage_metadata, 'total_token_count', 0),
                }
            
            # Get finish reason
            finish_reason = None
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason'):
                    finish_reason = candidate.finish_reason
            elif hasattr(response, 'finish_reason'):
                finish_reason = response.finish_reason
            
            return LLMResponse(
                content=content,
                model=self._model_name,
                provider=self.provider_name,
                usage=usage,
                finish_reason=finish_reason
            )
            
        except Exception as e:
            error_str = str(e)
            # Check for specific error types
            if "503" in error_str or "UNAVAILABLE" in error_str or "overloaded" in error_str.lower():
                raise Exception(
                    f"Gemini API temporarily unavailable (503): The model is overloaded. "
                    f"Please try again in a few moments. Error: {error_str}"
                )
            elif "429" in error_str or "quota" in error_str.lower() or "rate limit" in error_str.lower():
                # Extract retry delay from error message if available
                retry_delay = None
                try:
                    import re
                    # Look for "retry in Xs" or "retryDelay: 'Xs'"
                    match = re.search(r"retry.*?(\d+(?:\.\d+)?)\s*s", error_str, re.IGNORECASE)
                    if match:
                        retry_delay = float(match.group(1))
                except:
                    pass
                
                error_msg = f"Gemini API rate limit exceeded (429) [gemini_client.py]: You've exceeded your quota or rate limit."
                if retry_delay:
                    error_msg += f" Please retry in {retry_delay:.1f} seconds."
                else:
                    error_msg += " Please wait before trying again."
                error_msg += f" Error: {error_str}"
                
                # Store retry delay in exception for upstream retry logic
                exc = Exception(error_msg)
                if retry_delay:
                    exc.retry_delay = retry_delay
                raise exc
            elif "401" in error_str or "403" in error_str or "unauthorized" in error_str.lower():
                raise Exception(
                    f"Gemini API authentication error: Invalid API key or insufficient permissions. "
                    f"Please check your API key. Error: {error_str}"
                )
            else:
                raise Exception(f"Gemini API error: {error_str}")
    
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
            error_str = str(e)
            # Check for rate limit errors in embeddings too
            if "429" in error_str or "quota" in error_str.lower() or "rate limit" in error_str.lower():
                raise Exception(
                    f"Gemini embedding API rate limit exceeded (429) [gemini_client.py]: You've exceeded your quota or rate limit. "
                    f"Please wait before trying again. Error: {error_str}"
                )
            raise Exception(f"Gemini embedding API error [gemini_client.py]: {error_str}")
