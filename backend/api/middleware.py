"""API middleware for logging and rate limiting."""

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
import time
import logging
import sys
from pathlib import Path
from typing import Callable

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from inference_logging import get_inference_logger
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
inference_logger = get_inference_logger()


def setup_middleware(app: FastAPI):
    """Setup all middleware for the application.
    
    Args:
        app: FastAPI application instance
    """
    # Inference logging middleware
    @app.middleware("http")
    async def inference_logging_middleware(request: Request, call_next: Callable):
        """Log inference requests and responses."""
        # Skip logging for health checks and docs
        if request.url.path in ["/health", "/docs", "/openapi.json", "/"]:
            return await call_next(request)
        
        # Get request_id from request state (set by main.py middleware)
        request_id = getattr(request.state, "request_id", None)
        
        # If not set, try to get from header (fallback)
        if not request_id:
            request_id = request.headers.get("X-Request-ID")
        
        # Final fallback - generate one (shouldn't happen if middleware order is correct)
        if not request_id:
            import uuid
            request_id = str(uuid.uuid4())
            request.state.request_id = request_id
        
        start_time = time.time()
        
        # Log request
        logger.info(
            f"Request: {request.method} {request.url.path}",
            extra={"request_id": request_id}
        )
        
        # Note: We don't read request body here to avoid consuming it before the endpoint
        # Request body metadata will be captured from request.state if set by endpoint
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log response
            logger.info(
                f"Response: {response.status_code} ({duration:.3f}s)",
                extra={"request_id": request_id, "duration": duration}
            )
            
            # Log to inference logger if it's an API endpoint and request_id is valid
            # Skip logging for the logs endpoints themselves to avoid recursion
            should_log = (
                request.url.path.startswith("/api/v1") and 
                request_id and 
                request_id != "unknown" and
                not request.url.path.startswith("/api/v1/logs")
            )
            
            if should_log:
                try:
                    # Extract metadata from request (if available)
                    metadata = {}
                    
                    # Try to get request body data from request.state (set by endpoint if needed)
                    request_body_data = getattr(request.state, "body_data", None)
                    if request_body_data and isinstance(request_body_data, dict):
                        metadata.update({
                            "session_id": request_body_data.get("session_id"),
                            "max_iterations": request_body_data.get("max_iterations"),
                            "temperature": request_body_data.get("temperature"),
                            "max_tokens": request_body_data.get("max_tokens"),
                            "collection": request_body_data.get("collection")
                        })
                        # Remove None values
                        metadata = {k: v for k, v in metadata.items() if v is not None}
                    
                    # Extract tool_calls from request state (set by chat endpoint)
                    # Check all possible attributes
                    tool_calls = getattr(request.state, "tool_calls", None)
                    tool_results = getattr(request.state, "tool_results", None)
                    iterations = getattr(request.state, "iterations", None)
                    
                    # Debug: Log what we found
                    logger.debug(f"Request state check for {request_id}: tool_calls={tool_calls is not None}, tool_results={tool_results is not None}, iterations={iterations}")
                    if hasattr(request.state, "__dict__"):
                        logger.debug(f"Request state attributes: {list(request.state.__dict__.keys())}")
                    
                    # Add tool information to metadata if available
                    if tool_calls is not None:
                        # Store tool calls summary (full list can be large, so we store it)
                        metadata["tool_calls"] = tool_calls
                        metadata["tool_count"] = len(tool_calls) if tool_calls else 0
                        
                        # Store tool names for quick filtering
                        if tool_calls:
                            tool_names = [tc.get("tool_name", tc.get("tool", "unknown")) for tc in tool_calls]
                            metadata["tool_names"] = list(set(tool_names))  # Unique tool names
                    
                    if tool_results is not None:
                        # Store tool results summary (can be large, so store carefully)
                        metadata["tool_results_count"] = len(tool_results) if tool_results else 0
                        
                        # Count successful vs failed tool calls
                        if tool_results:
                            successful = sum(1 for tr in tool_results if not tr.get("error"))
                            failed = len(tool_results) - successful
                            metadata["tool_success_count"] = successful
                            metadata["tool_failure_count"] = failed
                    
                    if iterations is not None:
                        metadata["iterations"] = iterations
                    
                    # Extract question and answer for chat endpoints
                    question = None
                    answer = None
                    
                    # For chat and chat/stream endpoints, extract question from request body and answer from response
                    if request.url.path in ["/api/v1/chat", "/api/v1/chat/stream"]:
                        # Get question from request state (set by chat endpoint)
                        question = getattr(request.state, "question", None)
                        if not question:
                            # Fallback: try to get from request body data
                            question = request_body_data.get("message") if request_body_data else None
                        
                        # Get answer from request state (set by endpoint)
                        answer = getattr(request.state, "answer", None)
                        
                        # Add question and answer to metadata
                        if question:
                            metadata["question"] = question
                        if answer:
                            metadata["answer"] = answer
                    
                    # Log the request (always log, even if metadata is empty)
                    await inference_logger.log_request(
                        request_id=request_id,
                        method=request.method,
                        path=str(request.url.path),
                        status_code=response.status_code,
                        duration=duration,
                        metadata=metadata if metadata else None,
                        question=question,
                        answer=answer
                    )
                    tool_count = metadata.get('tool_count', 0) if metadata else 0
                    logger.debug(f"Logged inference request: {request_id} - {request.method} {request.url.path} - {tool_count} tools, metadata keys: {list(metadata.keys()) if metadata else 'none'}")
                except Exception as log_error:
                    # Don't fail the request if logging fails, but log the error
                    logger.warning(f"Failed to log request {request_id}: {log_error}", exc_info=True)
            else:
                # Debug why logging was skipped
                logger.debug(
                    f"Skipped logging for {request.url.path}: "
                    f"request_id={request_id}, "
                    f"is_api={request.url.path.startswith('/api/v1')}, "
                    f"is_logs_endpoint={request.url.path.startswith('/api/v1/logs')}"
                )
            
            return response
        
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Request failed: {str(e)}",
                extra={"request_id": request_id, "duration": duration},
                exc_info=True
            )
            
            # Log error to inference logger if request_id is valid
            if request.url.path.startswith("/api/v1") and request_id and request_id != "unknown":
                try:
                    # Extract question for error logging (if available)
                    question = None
                    error_metadata = {}
                    
                    if request.url.path == "/api/v1/chat":
                        request_body_data = getattr(request.state, "body_data", None)
                        question = getattr(request.state, "question", None) or (
                            request_body_data.get("message") if request_body_data else None
                        )
                        
                        # Add question to error metadata
                        if question:
                            error_metadata["question"] = question
                    
                    await inference_logger.log_error(
                        request_id=request_id,
                        method=request.method,
                        path=str(request.url.path),
                        error=str(e),
                        duration=duration,
                        question=question,
                        answer=None,  # No answer for errors
                        metadata=error_metadata if error_metadata else None
                    )
                except Exception as log_error:
                    # Don't fail the request if logging fails
                    logger.warning(f"Failed to log error: {log_error}")
            
            # Return error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "request_id": request_id
                }
            )
    
    # Rate limiting middleware (simple implementation)
    # For production, consider using slowapi or similar
    if settings.api_key:
        @app.middleware("http")
        async def api_key_middleware(request: Request, call_next: Callable):
            """Validate API key for protected endpoints."""
            # Skip auth for health and docs
            if request.url.path in ["/health", "/docs", "/openapi.json", "/"]:
                return await call_next(request)
            
            # Check API key
            api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").replace("Bearer ", "")
            
            if not api_key or api_key != settings.api_key:
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "Unauthorized",
                        "message": "Invalid or missing API key"
                    }
                )
            
            return await call_next(request)
