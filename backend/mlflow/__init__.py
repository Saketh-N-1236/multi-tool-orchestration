"""MLflow integration for tracking agent experiments and evaluation.

This module provides MLflow tracking functionality. To avoid circular imports
with the installed mlflow package, we use lazy imports.
"""

# Use lazy imports to avoid circular import conflicts with installed mlflow package
# Import only when needed, not at module level

__all__ = ["MLflowTracker", "AIJudge", "get_tracker"]

def __getattr__(name: str):
    """Lazy import to avoid circular imports.
    
    This function is called when an attribute is accessed that doesn't exist
    in the module. This allows us to delay imports until they're actually needed,
    preventing circular import issues with the installed mlflow package.
    """
    if name == "MLflowTracker":
        from .tracking import MLflowTracker
        return MLflowTracker
    elif name == "AIJudge":
        from .evaluation import AIJudge
        return AIJudge
    elif name == "get_tracker":
        from .tracking import get_tracker
        return get_tracker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
