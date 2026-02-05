"""Logging package for inference logging."""

from typing import Optional
from .inference_logger import InferenceLogger

# Singleton instance
_inference_logger_instance: Optional[InferenceLogger] = None


def get_inference_logger(db_path: Optional[str] = None) -> InferenceLogger:
    """Get singleton InferenceLogger instance.
    
    This ensures all parts of the application use the same logger instance,
    preventing inconsistencies and unnecessary object creation.
    
    Args:
        db_path: Optional database path (only used on first initialization)
        
    Returns:
        InferenceLogger instance
    """
    global _inference_logger_instance
    if _inference_logger_instance is None:
        _inference_logger_instance = InferenceLogger(db_path=db_path)
    return _inference_logger_instance


def reset_inference_logger():
    """Reset singleton instance (useful for testing)."""
    global _inference_logger_instance
    _inference_logger_instance = None