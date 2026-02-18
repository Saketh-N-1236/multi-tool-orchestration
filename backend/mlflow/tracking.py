"""MLflow tracking integration for agent experiments.

This module provides MLflow tracking functionality to log:
- Prompt versions
- Model names
- Request IDs for correlation
- Agent execution metrics
- Tool usage statistics
"""

import logging
import os
import json
import sys
import importlib
import importlib.util
import site
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from contextlib import contextmanager

# Debug logging flag (set to False to disable debug logs)
_debug_log_enabled = False  # Set to True for debugging

# #region debug log
if _debug_log_enabled:
    import json
    import os
    _log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.cursor', 'debug.log')
    try:
        with open(_log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"import-check","hypothesisId":"A,B,C,D,E","location":"mlflow/tracking.py:17","message":"Starting mlflow import check","data":{"file":__file__},"timestamp":int(__import__('time').time()*1000)}) + '\n')
    except: pass
# #endregion
# Lazy import approach: Import mlflow at module level, but MlflowClient only when needed
# This avoids circular import when this module is imported as 'mlflow.tracking'
# CRITICAL: We must import from the installed mlflow package, not our local backend/mlflow/
try:
    # Step 1: Remove our local mlflow from sys.modules if present
    _local_mlflow_modules = []
    for module_name in list(sys.modules.keys()):
        if module_name.startswith('mlflow'):
            module = sys.modules[module_name]
            if hasattr(module, '__file__') and module.__file__:
                module_file = str(module.__file__)
                # Check if it's from our local backend/mlflow/
                if ('backend' + os.sep + 'mlflow' in module_file or 
                    'backend/mlflow' in module_file or
                    module_file.endswith(os.sep + 'mlflow' + os.sep + '__init__.py') or
                    module_file.endswith(os.sep + 'mlflow' + os.sep + 'tracking.py') or
                    module_file.endswith(os.sep + 'mlflow' + os.sep + 'evaluation.py')):
                    _local_mlflow_modules.append(module_name)
    
    # Remove local mlflow modules
    for module_name in _local_mlflow_modules:
        del sys.modules[module_name]
    
    # Step 2: Temporarily remove backend/ from sys.path to ensure we import installed package
    _backend_paths_removed = []
    _backend_paths_info = []
    # Iterate backwards to avoid index issues when removing items
    for i in range(len(sys.path) - 1, -1, -1):
        path = sys.path[i]
        path_str = str(path)
        if (path_str.endswith('backend') or 
            path_str.endswith('backend\\') or 
            path_str.endswith('backend/') or
            ('backend' in path_str and Path(path_str).name == 'backend')):
            _backend_paths_removed.insert(0, sys.path.pop(i))
            _backend_paths_info.insert(0, (i, path_str))
    
    try:
        # Step 3: Try to import from site-packages directly
        _mlflow_imported = False
        for site_package in site.getsitepackages():
            mlflow_path = Path(site_package) / 'mlflow' / '__init__.py'
            if mlflow_path.exists():
                try:
                    _spec = importlib.util.spec_from_file_location('mlflow_installed_pkg', mlflow_path)
                    _mlflow_installed = importlib.util.module_from_spec(_spec)
                    _spec.loader.exec_module(_mlflow_installed)
                    sys.modules['mlflow'] = _mlflow_installed
                    mlflow = _mlflow_installed
                    _mlflow_imported = True
                    break
                except Exception:
                    continue
        
        # Step 4: Fallback to normal import if direct import failed
        if not _mlflow_imported:
            import mlflow
            # Verify it's from site-packages
            if hasattr(mlflow, '__file__') and mlflow.__file__:
                _mlflow_file = str(mlflow.__file__)
                if 'site-packages' not in _mlflow_file and 'dist-packages' not in _mlflow_file:
                    # Still got local, try to force import from site-packages again
                    raise ImportError(f"Imported mlflow from wrong location: {_mlflow_file}")
    finally:
        # Step 5: Restore backend/ paths to sys.path
        for i, path in reversed(_backend_paths_info):  # Insert in reverse order to maintain indices
            sys.path.insert(i, _backend_paths_removed.pop(0))
    
    MLFLOW_AVAILABLE = True
    # Don't import MlflowClient here - import it lazily in __init__ to avoid circular import
    MlflowClient = None
    # #region debug log
    try:
        with open(_log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"import-check","hypothesisId":"A","location":"mlflow/tracking.py:20","message":"mlflow import succeeded","data":{"mlflow_version":getattr(mlflow,'__version__','unknown'),"MLFLOW_AVAILABLE":MLFLOW_AVAILABLE},"timestamp":int(__import__('time').time()*1000)}) + '\n')
    except: pass
    # #endregion
except ImportError as e:
    MLFLOW_AVAILABLE = False
    mlflow = None
    MlflowClient = None
    # #region debug log
    if _debug_log_enabled:
        try:
            with open(_log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"import-check","hypothesisId":"B","location":"mlflow/tracking.py:23","message":"mlflow ImportError caught","data":{"error_type":type(e).__name__,"error_msg":str(e),"MLFLOW_AVAILABLE":MLFLOW_AVAILABLE},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
    # #endregion
except Exception as e:
    MLFLOW_AVAILABLE = False
    mlflow = None
    MlflowClient = None
    # #region debug log
    if _debug_log_enabled:
        try:
            with open(_log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"import-check","hypothesisId":"C","location":"mlflow/tracking.py:30","message":"mlflow non-ImportError exception","data":{"error_type":type(e).__name__,"error_msg":str(e),"MLFLOW_AVAILABLE":MLFLOW_AVAILABLE},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
    # #endregion

from config.settings import get_settings

logger = logging.getLogger(__name__)


class MLflowTracker:
    """MLflow tracker for agent experiments with request ID correlation."""
    
    def __init__(
        self,
        tracking_uri: Optional[str] = None,
        experiment_name: Optional[str] = None,
        enabled: bool = True
    ):
        """Initialize MLflow tracker.
        
        Args:
            tracking_uri: MLflow tracking URI (defaults to settings)
            experiment_name: Experiment name (defaults to settings)
            enabled: Whether tracking is enabled (defaults to True)
        """
        self.settings = get_settings()
        self.tracking_uri = tracking_uri or self.settings.mlflow_tracking_uri
        self.experiment_name = experiment_name or self.settings.mlflow_experiment_name
        
        # Lazy import MlflowClient here (after module is fully loaded) to avoid circular import
        # Use importlib to import from the actual installed mlflow package, not our local module
        global MlflowClient
        if MLFLOW_AVAILABLE and MlflowClient is None:
            try:
                import importlib
                import sys
                # Get the installed mlflow package (not our local module)
                # First, ensure we have the real mlflow package imported
                if 'mlflow' not in sys.modules or sys.modules['mlflow'].__file__ is None or 'site-packages' not in str(sys.modules['mlflow'].__file__):
                    # Force reimport of the installed mlflow package
                    if 'mlflow' in sys.modules:
                        del sys.modules['mlflow']
                    if 'mlflow.tracking' in sys.modules:
                        del sys.modules['mlflow.tracking']
                
                # Import the installed mlflow package
                _installed_mlflow = importlib.import_module('mlflow')
                # Access MlflowClient via attribute access on the installed package
                if hasattr(_installed_mlflow, 'tracking') and hasattr(_installed_mlflow.tracking, 'MlflowClient'):
                    MlflowClient = _installed_mlflow.tracking.MlflowClient
                else:
                    # Fallback: try importing mlflow.tracking directly
                    _saved_module = sys.modules.pop('mlflow.tracking', None)
                    try:
                        _mlflow_tracking = importlib.import_module('mlflow.tracking')
                        MlflowClient = _mlflow_tracking.MlflowClient
                    finally:
                        if _saved_module is not None:
                            sys.modules['mlflow.tracking'] = _saved_module
                
                # #region debug log
                if _debug_log_enabled:
                    try:
                        with open(_log_path, 'a', encoding='utf-8') as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"tracker-init","hypothesisId":"D","location":"mlflow/tracking.py:120","message":"MlflowClient imported successfully","data":{"MlflowClient_available":MlflowClient is not None},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                    except: pass
                # #endregion
            except (ImportError, AttributeError, Exception) as e:
                # #region debug log
                if _debug_log_enabled:
                    try:
                        with open(_log_path, 'a', encoding='utf-8') as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"tracker-init","hypothesisId":"D","location":"mlflow/tracking.py:135","message":"Failed to import MlflowClient lazily","data":{"error_type":type(e).__name__,"error":str(e),"mlflow_in_modules":"mlflow" in sys.modules},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                    except: pass
                # #endregion
                pass
        
        # #region debug log
        if _debug_log_enabled:
            try:
                with open(_log_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"tracker-init","hypothesisId":"D,E","location":"mlflow/tracking.py:90","message":"MLflowTracker.__init__ called","data":{"MLFLOW_AVAILABLE":MLFLOW_AVAILABLE,"MlflowClient_available":MlflowClient is not None,"mlflow_module":str(mlflow) if mlflow else None,"enabled_param":enabled},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except: pass
        # #endregion
        self.enabled = enabled and MLFLOW_AVAILABLE and MlflowClient is not None
        
        if not self.enabled:
            # #region debug log
            if _debug_log_enabled:
                try:
                    with open(_log_path, 'a', encoding='utf-8') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"tracker-init","hypothesisId":"D","location":"mlflow/tracking.py:110","message":"MLflowTracker disabled","data":{"MLFLOW_AVAILABLE":MLFLOW_AVAILABLE,"MlflowClient_available":MlflowClient is not None,"mlflow_in_sys_modules":"mlflow" in __import__('sys').modules},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                except: pass
            # #endregion
            # Check if mlflow is actually in sys.modules to distinguish between
            # "not installed" vs "import failed due to circular import"
            mlflow_imported = "mlflow" in __import__('sys').modules
            if mlflow_imported and MLFLOW_AVAILABLE and MlflowClient is None:
                logger.warning(
                    "MLflow package is installed but MlflowClient failed to import. "
                    "MLflow tracking will be disabled. This may be due to a circular import issue."
                )
            elif not mlflow_imported:
                logger.warning(
                    "MLflow is not installed. Install with: pip install mlflow>=2.15.0. "
                    "MLflow tracking will be disabled."
                )
            else:
                logger.warning(
                    "MLflow tracking is disabled. Check MLFLOW_AVAILABLE and MlflowClient availability."
                )
            return
        
        if self.enabled:
            try:
                mlflow.set_tracking_uri(self.tracking_uri)
                # Get or create experiment
                try:
                    experiment = mlflow.get_experiment_by_name(self.experiment_name)
                    if experiment is None:
                        experiment_id = mlflow.create_experiment(self.experiment_name)
                        logger.info(f"Created MLflow experiment: {self.experiment_name} (ID: {experiment_id})")
                    else:
                        logger.info(f"Using MLflow experiment: {self.experiment_name} (ID: {experiment.experiment_id})")
                except Exception as e:
                    logger.warning(f"Failed to setup MLflow experiment: {e}. Tracking disabled.")
                    self.enabled = False
            except Exception as e:
                logger.warning(f"Failed to connect to MLflow at {self.tracking_uri}: {e}. Tracking disabled.")
                self.enabled = False
    
    @contextmanager
    def start_run(
        self,
        request_id: str,
        prompt_version: str,
        model_name: str,
        session_id: Optional[str] = None,
        **kwargs
    ):
        """Start an MLflow run with request ID correlation.
        
        Args:
            request_id: Request ID for correlation
            prompt_version: Prompt version being used
            model_name: LLM model name
            session_id: Optional session ID
            **kwargs: Additional parameters to log
            
        Yields:
            MLflow run context
        """
        if not self.enabled:
            yield None
            return
        
        try:
            # Set tracking URI and experiment
            mlflow.set_tracking_uri(self.tracking_uri)
            
            # Get or create experiment (handle deleted experiments)
            try:
                experiment = mlflow.get_experiment_by_name(self.experiment_name)
                if experiment is None:
                    # Experiment doesn't exist, create it
                    experiment_id = mlflow.create_experiment(self.experiment_name)
                    logger.info(f"Created MLflow experiment: {self.experiment_name} (ID: {experiment_id})")
                    mlflow.set_experiment(self.experiment_name)
                elif experiment.lifecycle_stage == "deleted":
                    # Experiment was deleted, recreate it with the same name
                    # Don't create a new timestamped experiment - just recreate the original
                    logger.warning(
                        f"Experiment '{self.experiment_name}' was deleted. "
                        f"Recreating with the same name."
                    )
                    try:
                        # Delete the old experiment record if possible, then create new one
                        experiment_id = mlflow.create_experiment(self.experiment_name)
                        mlflow.set_experiment(self.experiment_name)
                        logger.info(f"Recreated MLflow experiment: {self.experiment_name} (ID: {experiment_id})")
                    except Exception as recreate_error:
                        # If recreation fails (e.g., name conflict), try with a small suffix
                        new_experiment_name = f"{self.experiment_name}_recreated"
                        logger.warning(f"Could not recreate '{self.experiment_name}', using '{new_experiment_name}'")
                        experiment_id = mlflow.create_experiment(new_experiment_name)
                        mlflow.set_experiment(new_experiment_name)
                        self.experiment_name = new_experiment_name
                else:
                    # Experiment exists and is active
                    mlflow.set_experiment(self.experiment_name)
            except Exception as exp_error:
                logger.error(f"Error setting up experiment: {exp_error}", exc_info=True)
                raise
            
            # Start the run
            run = mlflow.start_run(run_name=f"request_{request_id[:8]}")
            
            try:
                # Log core parameters
                mlflow.log_param("request_id", request_id)
                mlflow.log_param("prompt_version", prompt_version)
                mlflow.log_param("model_name", model_name)
                mlflow.log_param("llm_provider", self.settings.llm_provider)
                mlflow.log_param("embedding_provider", self.settings.embedding_provider)
                
                if session_id:
                    mlflow.log_param("session_id", session_id)
                
                # Log additional parameters
                for key, value in kwargs.items():
                    if value is not None:
                        try:
                            mlflow.log_param(key, str(value))
                        except Exception as param_error:
                            logger.warning(f"Failed to log parameter {key}: {param_error}")
                
                # Log timestamp
                mlflow.log_param("start_time", datetime.utcnow().isoformat())
                
                # Store run info for later use
                run_info = {
                    "run_id": run.info.run_id,
                    "request_id": request_id,
                    "experiment_id": run.info.experiment_id
                }
                
                logger.info(f"Started MLflow run: {run.info.run_id} for request: {request_id}")
                
                yield run_info
                
                # Log end time
                try:
                    mlflow.log_param("end_time", datetime.utcnow().isoformat())
                except Exception:
                    pass  # Don't fail if end_time logging fails
                    
            finally:
                # Always end the run
                try:
                    # Check if there's an active run before ending
                    try:
                        active_run = mlflow.active_run()
                        if active_run:
                            mlflow.end_run()
                    except Exception:
                        # If we can't check or end, try to end anyway
                        try:
                            mlflow.end_run()
                        except Exception:
                            pass  # Ignore errors when ending run
                except Exception as end_error:
                    # Log error but don't fail
                    try:
                        error_msg = str(end_error)
                        # Filter out Unicode errors from logging
                        if 'codec' not in error_msg.lower() and 'encode' not in error_msg.lower():
                            logger.warning(f"Error ending MLflow run: {end_error}")
                    except Exception:
                        pass  # Ignore logging errors
                
        except Exception as e:
            logger.error(f"Error in MLflow tracking for request {request_id}: {e}", exc_info=True)
            # Try to get more details about the error
            import traceback
            logger.error(f"MLflow error traceback: {traceback.format_exc()}")
            yield None
    
    def log_metrics(
        self,
        run_id: Optional[str],
        metrics: Dict[str, float],
        step: Optional[int] = None
    ):
        """Log metrics to MLflow run.
        
        Args:
            run_id: MLflow run ID (if None, uses current active run)
            metrics: Dictionary of metric names to values
            step: Optional step number for metric logging
        """
        if not self.enabled or not metrics:
            return
        
        try:
            mlflow.set_tracking_uri(self.tracking_uri)
            
            if run_id:
                # Validate run_id exists before trying to log to it
                try:
                    client = MlflowClient(tracking_uri=self.tracking_uri)
                    # Verify run exists
                    run = client.get_run(run_id)
                    if run is None:
                        logger.warning(f"Run {run_id} not found, skipping metric logging")
                        return
                except Exception as validate_error:
                    logger.warning(
                        f"Failed to validate run_id {run_id}: {validate_error}. "
                        f"Attempting to log to run anyway."
                    )
                    # Continue to attempt logging - run might exist but validation failed
                
                # Check if this run is already active
                try:
                    active_run = mlflow.active_run()
                    if active_run and active_run.info.run_id == run_id:
                        # Run is already active, just log metrics directly
                        for key, value in metrics.items():
                            mlflow.log_metric(key, value, step=step)
                    else:
                        # Run is not active, start it
                        with mlflow.start_run(run_id=run_id):
                            for key, value in metrics.items():
                                mlflow.log_metric(key, value, step=step)
                except Exception:
                    # No active run, start the specified run
                    with mlflow.start_run(run_id=run_id):
                        for key, value in metrics.items():
                            mlflow.log_metric(key, value, step=step)
            else:
                # Try to log to active run
                for key, value in metrics.items():
                    mlflow.log_metric(key, value, step=step)
        except Exception as e:
            logger.error(f"Error logging metrics to MLflow: {e}", exc_info=True)
    
    def log_agent_execution(
        self,
        run_id: Optional[str],
        request_id: str,
        iterations: int,
        tool_calls: List[Dict[str, Any]],
        tool_results: List[Dict[str, Any]],
        duration_seconds: Optional[float] = None,
        error: Optional[str] = None
    ):
        """Log agent execution details.
        
        Args:
            run_id: MLflow run ID
            request_id: Request ID for correlation
            iterations: Number of agent iterations
            tool_calls: List of tool calls made
            tool_results: List of tool results
            duration_seconds: Total execution duration
            error: Error message if any
        """
        if not self.enabled:
            return
        
        try:
            metrics = {
                "agent_iterations": iterations,
                "tool_calls_count": len(tool_calls),
                "tool_results_count": len(tool_results)
            }
            
            # Count tools by type
            tool_types = {}
            for tool_call in tool_calls:
                tool_name = tool_call.get("tool_name", "unknown")
                server = tool_name.split("::")[0] if "::" in tool_name else "unknown"
                tool_types[server] = tool_types.get(server, 0) + 1
            
            for server, count in tool_types.items():
                metrics[f"tools_{server}_count"] = count
            
            # Count successful vs failed tools
            successful_tools = sum(1 for tr in tool_results if tr.get("error") is None)
            failed_tools = len(tool_results) - successful_tools
            metrics["tool_success_count"] = successful_tools
            metrics["tool_failure_count"] = failed_tools
            
            if duration_seconds is not None:
                metrics["duration_seconds"] = duration_seconds
                if iterations > 0:
                    metrics["avg_iteration_time"] = duration_seconds / iterations
            
            if error:
                metrics["has_error"] = 1.0
                mlflow.log_text(error, "error_message.txt")
            else:
                metrics["has_error"] = 0.0
            
            self.log_metrics(run_id, metrics)
            
            # Log tool calls as artifacts (JSON)
            if tool_calls:
                import json
                import tempfile
                import os
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    json.dump(tool_calls, f, indent=2)
                    temp_path = f.name
                
                try:
                    if run_id:
                        # Check if run is already active
                        active_run = mlflow.active_run()
                        if active_run and active_run.info.run_id == run_id:
                            # Run is already active, just log the artifact
                            mlflow.log_artifact(temp_path, "tool_calls.json")
                        else:
                            # Run is not active, start it
                            with mlflow.start_run(run_id=run_id):
                                mlflow.log_artifact(temp_path, "tool_calls.json")
                    else:
                        mlflow.log_artifact(temp_path, "tool_calls.json")
                finally:
                    os.unlink(temp_path)
            
        except Exception as e:
            logger.error(f"Error logging agent execution to MLflow: {e}", exc_info=True)
    
    def log_evaluation_scores(
        self,
        run_id: Optional[str],
        request_id: str,
        evaluation_scores: Dict[str, float]
    ):
        """Log AI judge evaluation scores as MLflow metrics.
        
        Args:
            run_id: MLflow run ID
            request_id: Request ID for correlation
            evaluation_scores: Dictionary with evaluation scores
                Expected keys: correctness, relevance, completeness, tool_usage, overall_score
        """
        if not self.enabled:
            return
        
        try:
            metrics = {
                "ai_judge_correctness": evaluation_scores.get("correctness", 0.0),
                "ai_judge_relevance": evaluation_scores.get("relevance", 0.0),
                "ai_judge_completeness": evaluation_scores.get("completeness", 0.0),
                "ai_judge_tool_usage": evaluation_scores.get("tool_usage", 0.0),
                "ai_judge_overall_score": evaluation_scores.get("overall_score", 0.0)
            }
            
            self.log_metrics(run_id, metrics)
            logger.debug(f"Logged AI judge evaluation scores for request: {request_id}")
        except Exception as e:
            logger.error(f"Error logging evaluation scores to MLflow: {e}", exc_info=True)
    
    def log_llm_call(
        self,
        run_id: Optional[str],
        request_id: str,
        model: str,
        provider: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        duration_seconds: Optional[float] = None
    ):
        """Log LLM call details.
        
        Args:
            run_id: MLflow run ID
            request_id: Request ID for correlation
            model: Model name used
            provider: LLM provider (gemini, ollama, etc.)
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            total_tokens: Total tokens used
            duration_seconds: LLM call duration
        """
        if not self.enabled:
            return
        
        try:
            metrics = {}
            
            if prompt_tokens is not None:
                metrics["llm_prompt_tokens"] = prompt_tokens
            if completion_tokens is not None:
                metrics["llm_completion_tokens"] = completion_tokens
            if total_tokens is not None:
                metrics["llm_total_tokens"] = total_tokens
            if duration_seconds is not None:
                metrics["llm_duration_seconds"] = duration_seconds
                if total_tokens and total_tokens > 0:
                    metrics["llm_tokens_per_second"] = total_tokens / duration_seconds
            
            if metrics:
                self.log_metrics(run_id, metrics)
                
        except Exception as e:
            logger.error(f"Error logging LLM call to MLflow: {e}", exc_info=True)
    
    def search_runs_by_request_id(self, request_id: str) -> List[Dict[str, Any]]:
        """Search for runs by request ID.
        
        Args:
            request_id: Request ID to search for
            
        Returns:
            List of run information dictionaries
        """
        if not self.enabled:
            return []
        
        try:
            client = MlflowClient(tracking_uri=self.tracking_uri)
            experiment = mlflow.get_experiment_by_name(self.experiment_name)
            
            if experiment is None:
                return []
            
            # Search for runs with matching request_id parameter
            runs = client.search_runs(
                experiment_ids=[experiment.experiment_id],
                filter_string=f"params.request_id = '{request_id}'",
                max_results=10
            )
            
            return [
                {
                    "run_id": run.info.run_id,
                    "request_id": request_id,
                    "start_time": run.info.start_time,
                    "status": run.info.status,
                    "metrics": {k: v for k, v in run.data.metrics.items()},
                    "params": {k: v for k, v in run.data.params.items()}
                }
                for run in runs
            ]
        except Exception as e:
            logger.error(f"Error searching MLflow runs: {e}", exc_info=True)
            return []


# Global tracker instance (lazy initialization)
_tracker: Optional[MLflowTracker] = None


def get_tracker() -> MLflowTracker:
    """Get global MLflow tracker instance.
    
    Initializes tracker with settings from config/settings.py if not already initialized.
    
    Returns:
        MLflowTracker instance
    """
    global _tracker
    if _tracker is None:
        # Import settings here to avoid circular import
        try:
            from config.settings import get_settings
            settings = get_settings()
            
            # Use settings values
            tracking_uri = settings.mlflow_tracking_uri
            experiment_name = settings.mlflow_experiment_name
            enabled = settings.enable_mlflow_tracking
            
            _tracker = MLflowTracker(
                tracking_uri=tracking_uri,
                experiment_name=experiment_name,
                enabled=enabled
            )
        except Exception as e:
            # Fallback to defaults if settings import fails
            logger.warning(f"Failed to load MLflow settings, using defaults: {e}")
            _tracker = MLflowTracker()
    return _tracker


def reset_tracker():
    """Reset global tracker instance (useful for testing)."""
    global _tracker
    _tracker = None
