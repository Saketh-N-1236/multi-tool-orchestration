"""MLflow evaluation script for agent quality assessment."""

import asyncio
import json
import sys
import time
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Import mlflow FIRST, before modifying sys.path, to ensure we import the installed package
# #region debug log
import json
import os
_log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.cursor', 'debug.log')
try:
    with open(_log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps({"sessionId":"debug-session","runId":"script-import","hypothesisId":"A","location":"scripts/evaluate_agent.py:12","message":"About to import mlflow BEFORE sys.path modification","data":{},"timestamp":int(__import__('time').time()*1000)}) + '\n')
except: pass
# #endregion
try:
    import mlflow
    import os
    from importlib.metadata import version
    MLFLOW_AVAILABLE = True
    # Set tracking URI (defaults to http://127.0.0.1:5000 if not set in env)
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000")
    mlflow.set_tracking_uri(tracking_uri)
    # #region debug log
    try:
        with open(_log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"script-import","hypothesisId":"A","location":"scripts/evaluate_agent.py:22","message":"mlflow imported and tracking URI set BEFORE sys.path","data":{"mlflow_version":getattr(mlflow,'__version__','unknown'),"tracking_uri":tracking_uri,"has_set_tracking_uri":hasattr(mlflow,'set_tracking_uri')},"timestamp":int(__import__('time').time()*1000)}) + '\n')
    except: pass
    # #endregion
except ImportError as e:
    MLFLOW_AVAILABLE = False
    # #region debug log
    try:
        with open(_log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"script-import","hypothesisId":"A","location":"scripts/evaluate_agent.py:30","message":"mlflow import failed","data":{"error":str(e)},"timestamp":int(__import__('time').time()*1000)}) + '\n')
    except: pass
    # #endregion
    raise ImportError(f"MLflow is required but not available: {e}") from e

# Add project root to path (AFTER importing mlflow to avoid namespace conflicts)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agent.langgraph_agent import LangGraphAgent
# Alias for compatibility
AgentGraph = LangGraphAgent
from config.settings import get_settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if MLFLOW_AVAILABLE:
    logger.info(f"MLflow imported successfully, version: {version('mlflow')}")
    logger.info(f"MLflow tracking URI set to: {tracking_uri}")

# Import MLflowTracker from our local backend/mlflow/tracking.py module
# Use importlib to explicitly import from our local file, avoiding conflict with installed mlflow package
# #region debug log
try:
    with open(_log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps({"sessionId":"debug-session","runId":"script-import","hypothesisId":"E","location":"scripts/evaluate_agent.py:60","message":"About to import MLflowTracker from local module using importlib","data":{"mlflow_in_sys_modules":"mlflow" in __import__('sys').modules},"timestamp":int(__import__('time').time()*1000)}) + '\n')
except: pass
# #endregion
import importlib.util
_mlflow_tracking_path = Path(__file__).parent.parent / "mlflow" / "tracking.py"
_spec = importlib.util.spec_from_file_location("mlflow_tracking_local", _mlflow_tracking_path)
_mlflow_tracking_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mlflow_tracking_module)
MLflowTracker = _mlflow_tracking_module.MLflowTracker
# #region debug log
try:
    with open(_log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps({"sessionId":"debug-session","runId":"script-import","hypothesisId":"E","location":"scripts/evaluate_agent.py:72","message":"MLflowTracker imported from local module","data":{"MLflowTracker_class":str(MLflowTracker),"MLflowTracker_module":MLflowTracker.__module__},"timestamp":int(__import__('time').time()*1000)}) + '\n')
except: pass
# #endregion

# Import AIJudge from our local backend/mlflow/evaluation.py module
_mlflow_evaluation_path = Path(__file__).parent.parent / "mlflow" / "evaluation.py"
_spec_eval = importlib.util.spec_from_file_location("mlflow_evaluation_local", _mlflow_evaluation_path)
_mlflow_evaluation_module = importlib.util.module_from_spec(_spec_eval)
_spec_eval.loader.exec_module(_mlflow_evaluation_module)
AIJudge = _mlflow_evaluation_module.AIJudge


class RateLimitTracker:
    """Track API usage to avoid rate limits."""
    def __init__(self, max_requests: int = 20, delay_between_requests: float = 2.0):
        self.max_requests = max_requests
        self.request_count = 0
        self.delay_between_requests = delay_between_requests
        self.last_request_time = 0
    
    async def wait_if_needed(self):
        """Wait between requests to avoid rate limits."""
        if self.request_count >= self.max_requests:
            raise Exception(f"Rate limit reached: {self.max_requests} requests used")
        
        # Add delay between requests
        if self.last_request_time > 0:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.delay_between_requests:
                await asyncio.sleep(self.delay_between_requests - elapsed)
        
        self.last_request_time = time.time()
        self.request_count += 1
    
    def extract_retry_delay(self, error_msg: str) -> Optional[float]:
        """Extract retry delay from error message."""
        try:
            match = re.search(r"retry.*?(\d+(?:\.\d+)?)\s*s", error_msg, re.IGNORECASE)
            if match:
                return float(match.group(1)) + 2.0  # Add buffer
        except:
            pass
        return None


def load_evaluation_dataset(dataset_path: str) -> List[Dict[str, Any]]:
    """Load evaluation dataset from JSONL file.
    
    Args:
        dataset_path: Path to JSONL file
        
    Returns:
        List of test cases
    """
    test_cases = []
    dataset_file = Path(dataset_path)
    
    if not dataset_file.exists():
        raise FileNotFoundError(f"Evaluation dataset not found: {dataset_path}")
    
    with open(dataset_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                test_case = json.loads(line)
                # Validate required fields
                if "input" not in test_case:
                    logger.warning(f"Test case {line_num} missing 'input' field, skipping")
                    continue
                if "expected_output" not in test_case:
                    logger.warning(f"Test case {line_num} missing 'expected_output' field, skipping")
                    continue
                
                test_cases.append({
                    "test_id": line_num,
                    "input": test_case["input"],
                    "expected_output": test_case.get("expected_output", ""),
                    "category": test_case.get("category", "general"),
                    "expected_tools": test_case.get("expected_tools", [])
                })
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON on line {line_num}: {e}")
                continue
    
    logger.info(f"Loaded {len(test_cases)} test cases from {dataset_path}")
    return test_cases


async def run_evaluation(
    dataset_path: str = "backend/data/eval_dataset.jsonl",
    experiment_name: Optional[str] = None,
    max_iterations: int = 10,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    max_test_cases: Optional[int] = None,
    delay_between_tests: float = 5.0,
    max_requests_per_day: int = 20,
    skip_on_rate_limit: bool = True
) -> Dict[str, Any]:
    """Run evaluation pipeline with rate limit protection.
    
    Args:
        dataset_path: Path to evaluation dataset JSONL file
        experiment_name: MLflow experiment name (uses settings default if None)
        max_iterations: Maximum agent iterations
        temperature: LLM temperature
        max_tokens: Maximum tokens
        max_test_cases: Maximum number of test cases to run (None = all)
        delay_between_tests: Delay in seconds between test cases
        max_requests_per_day: Maximum API requests per day (free tier = 20)
        skip_on_rate_limit: If True, skip remaining tests when rate limit hit
        
    Returns:
        Evaluation results dictionary
    """
    settings = get_settings()
    
    # Load test cases
    test_cases = load_evaluation_dataset(dataset_path)
    
    if not test_cases:
        raise ValueError("No test cases found in dataset")
    
    # Limit test cases for free tier
    if max_test_cases and len(test_cases) > max_test_cases:
        logger.warning(
            f"Limiting to {max_test_cases} test cases (free tier limit). "
            f"Total available: {len(test_cases)}"
        )
        test_cases = test_cases[:max_test_cases]
    
    # Initialize rate limit tracker
    rate_tracker = RateLimitTracker(
        max_requests=max_requests_per_day,
        delay_between_requests=delay_between_tests
    )
    
    # Initialize MLflow tracker - MLflow is already confirmed available above
    # #region debug log
    try:
        with open(_log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"tracker-instantiation","hypothesisId":"D,E","location":"scripts/evaluate_agent.py:198","message":"About to instantiate MLflowTracker","data":{"mlflow_in_sys_modules":"mlflow" in __import__('sys').modules},"timestamp":int(__import__('time').time()*1000)}) + '\n')
    except: pass
    # #endregion
    tracker = MLflowTracker(
        experiment_name=experiment_name or settings.mlflow_experiment_name
    )
    # #region debug log
    try:
        with open(_log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"tracker-instantiation","hypothesisId":"D,E","location":"scripts/evaluate_agent.py:203","message":"MLflowTracker instantiated","data":{"tracker_enabled":tracker.enabled},"timestamp":int(__import__('time').time()*1000)}) + '\n')
    except: pass
    # #endregion
    
    if not tracker.enabled:
        # This should not happen if MLflow is available, but check anyway
        logger.warning("MLflow tracking is disabled. Evaluation will run but results won't be logged.")
        logger.warning("This may indicate a connection issue to the MLflow server.")
    
    # Initialize AI judge
    judge = AIJudge()
    
    # Initialize agent
    agent = AgentGraph()
    await agent.initialize()
    
    # Results storage
    all_results = []
    evaluation_id = f"eval_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    
    logger.info(f"Starting evaluation: {evaluation_id}")
    logger.info(f"Test cases: {len(test_cases)}")
    
    # Start evaluation run in MLflow
    eval_run_info = None
    if tracker.enabled:
        try:
            eval_run_context = tracker.start_run(
                request_id=evaluation_id,
                prompt_version="v1",
                model_name=settings.llm_provider,
                evaluation_id=evaluation_id,
                total_test_cases=len(test_cases)
            )
            eval_run_info = eval_run_context.__enter__()
        except Exception as e:
            logger.warning(f"Failed to start MLflow evaluation run: {e}")
    
    try:
        # Process each test case
        for idx, test_case in enumerate(test_cases, 1):
            test_id = test_case["test_id"]
            input_query = test_case["input"]
            expected_output = test_case["expected_output"]
            category = test_case["category"]
            expected_tools = test_case.get("expected_tools", [])
            
            logger.info(f"\n[{idx}/{len(test_cases)}] Test {test_id} ({category}): {input_query[:50]}...")
            
            # Check rate limit before processing
            try:
                await rate_tracker.wait_if_needed()
            except Exception as e:
                if skip_on_rate_limit:
                    logger.warning(
                        f"Rate limit reached. Skipping remaining {len(test_cases) - idx + 1} test cases. "
                        f"Processed {idx - 1} test cases successfully."
                    )
                    break
                else:
                    raise
            
            # Generate request ID for this test case
            import uuid
            request_id = f"{evaluation_id}_test_{test_id}"
            
            start_time = time.time()
            
            try:
                # Run agent with retry logic
                max_retries = 2
                state = None
                
                for attempt in range(max_retries + 1):
                    try:
                        state = await agent.invoke(
                            user_message=input_query,
                            request_id=request_id,
                            session_id=f"eval_{evaluation_id}",
                            max_iterations=max_iterations,
                            temperature=temperature,
                            max_tokens=max_tokens
                        )
                        break  # Success
                    except Exception as e:
                        error_msg = str(e)
                        
                        # Check for rate limit error
                        if ("429" in error_msg or "rate limit" in error_msg.lower()) and attempt < max_retries:
                            retry_delay = rate_tracker.extract_retry_delay(error_msg)
                            if not retry_delay:
                                retry_delay = 60.0  # Default 60 seconds
                            
                            logger.warning(
                                f"Rate limit hit on test {test_id} (attempt {attempt + 1}/{max_retries + 1}), "
                                f"waiting {retry_delay:.1f} seconds..."
                            )
                            await asyncio.sleep(retry_delay)
                            continue
                        else:
                            raise  # Re-raise if not rate limit or max retries reached
                
                if state is None:
                    raise Exception("Failed to get agent response after retries")
                
                duration = time.time() - start_time
                
                # Extract response
                assistant_messages = [
                    m for m in state.get("messages", [])
                    if m.get("role") == "assistant"
                ]
                actual_output = assistant_messages[-1].get("content", "") if assistant_messages else ""
                
                # Extract tool calls
                tool_calls = state.get("tool_calls", [])
                actual_tools = [
                    tc.get("tool_name", tc.get("tool", "unknown"))
                    for tc in tool_calls
                ]
                
                # Evaluate with AI judge (with retry logic)
                logger.info(f"Evaluating response with AI judge...")
                evaluation_scores = None
                max_judge_retries = 2
                
                for attempt in range(max_judge_retries + 1):
                    try:
                        evaluation_scores = await judge.evaluate_response(
                            input_query=input_query,
                            expected_output=expected_output,
                            actual_output=actual_output,
                            expected_tools=expected_tools,
                            actual_tools=actual_tools
                        )
                        break  # Success
                    except Exception as e:
                        error_msg = str(e)
                        if ("429" in error_msg or "rate limit" in error_msg.lower()) and attempt < max_judge_retries:
                            retry_delay = rate_tracker.extract_retry_delay(error_msg)
                            if not retry_delay:
                                retry_delay = 60.0
                            logger.warning(
                                f"Rate limit hit during AI judge evaluation (attempt {attempt + 1}), "
                                f"waiting {retry_delay:.1f} seconds..."
                            )
                            await asyncio.sleep(retry_delay)
                            continue
                        else:
                            # If judge fails, use default scores
                            logger.warning(f"AI judge evaluation failed: {e}. Using default scores.")
                            evaluation_scores = {
                                "correctness": 0.5,
                                "relevance": 0.5,
                                "completeness": 0.5,
                                "tool_usage": 0.5,
                                "overall_score": 0.5
                            }
                            break
                
                # Store result
                result = {
                    "test_id": test_id,
                    "input": input_query,
                    "expected_output": expected_output,
                    "actual_output": actual_output,
                    "category": category,
                    "scores": evaluation_scores,
                    "tools_used": actual_tools,
                    "expected_tools": expected_tools,
                    "duration": round(duration, 3),
                    "iterations": state.get("current_step", 0),
                    "error": state.get("error")
                }
                
                all_results.append(result)
                
                # Log to MLflow (individual test case)
                if tracker.enabled and eval_run_info:
                    try:
                        # Log metrics for this test case
                        metrics = {
                            f"test_{test_id}_correctness": evaluation_scores["correctness"],
                            f"test_{test_id}_relevance": evaluation_scores["relevance"],
                            f"test_{test_id}_completeness": evaluation_scores["completeness"],
                            f"test_{test_id}_tool_usage": evaluation_scores["tool_usage"],
                            f"test_{test_id}_overall": evaluation_scores["overall_score"],
                            f"test_{test_id}_duration": duration
                        }
                        tracker.log_metrics(eval_run_info.get("run_id"), metrics)
                    except Exception as e:
                        logger.warning(f"Failed to log test case {test_id} to MLflow: {e}")
                
                logger.info(
                    f"  Scores: correctness={evaluation_scores['correctness']:.2f}, "
                    f"relevance={evaluation_scores['relevance']:.2f}, "
                    f"completeness={evaluation_scores['completeness']:.2f}, "
                    f"overall={evaluation_scores['overall_score']:.2f}"
                )
                
            except Exception as e:
                duration = time.time() - start_time
                error_msg = str(e)
                
                # Check if it's a rate limit error
                if "429" in error_msg or "rate limit" in error_msg.lower():
                    logger.error(
                        f"Rate limit error on test case {test_id}: {error_msg}. "
                        f"Requests used: {rate_tracker.request_count}/{rate_tracker.max_requests}"
                    )
                    if skip_on_rate_limit:
                        logger.warning("Skipping remaining test cases due to rate limit.")
                        break
                
                logger.error(f"Error processing test case {test_id}: {e}", exc_info=True)
                
                result = {
                    "test_id": test_id,
                    "input": input_query,
                    "expected_output": expected_output,
                    "actual_output": "",
                    "category": category,
                    "scores": {
                        "correctness": 0.0,
                        "relevance": 0.0,
                        "completeness": 0.0,
                        "tool_usage": 0.0,
                        "overall_score": 0.0
                    },
                    "tools_used": [],
                    "expected_tools": expected_tools,
                    "duration": round(duration, 3),
                    "iterations": 0,
                    "error": str(e)
                }
                all_results.append(result)
            
            # Add delay between test cases
            if idx < len(test_cases):
                logger.info(f"Waiting {delay_between_tests}s before next test case...")
                await asyncio.sleep(delay_between_tests)
        
        # Calculate aggregate metrics
        if all_results:
            total_cases = len(all_results)
            successful_cases = sum(1 for r in all_results if not r.get("error"))
            
            avg_correctness = sum(r["scores"]["correctness"] for r in all_results) / total_cases
            avg_relevance = sum(r["scores"]["relevance"] for r in all_results) / total_cases
            avg_completeness = sum(r["scores"]["completeness"] for r in all_results) / total_cases
            avg_tool_usage = sum(r["scores"]["tool_usage"] for r in all_results) / total_cases
            avg_overall = sum(r["scores"]["overall_score"] for r in all_results) / total_cases
            avg_duration = sum(r["duration"] for r in all_results) / total_cases
            
            # Calculate by category
            category_stats = {}
            for result in all_results:
                cat = result["category"]
                if cat not in category_stats:
                    category_stats[cat] = {"count": 0, "scores": []}
                category_stats[cat]["count"] += 1
                category_stats[cat]["scores"].append(result["scores"]["overall_score"])
            
            for cat, stats in category_stats.items():
                stats["avg_score"] = sum(stats["scores"]) / len(stats["scores"])
            
            # Tool usage statistics
            tool_stats = {}
            for result in all_results:
                for tool in result["tools_used"]:
                    if tool not in tool_stats:
                        tool_stats[tool] = {"count": 0, "success_count": 0}
                    tool_stats[tool]["count"] += 1
                    if result["scores"]["overall_score"] > 0.7:
                        tool_stats[tool]["success_count"] += 1
            
            for tool, stats in tool_stats.items():
                stats["success_rate"] = stats["success_count"] / stats["count"] if stats["count"] > 0 else 0.0
            
            aggregate_results = {
                "evaluation_id": evaluation_id,
                "evaluation_date": datetime.utcnow().isoformat(),
                "total_test_cases": total_cases,
                "successful_cases": successful_cases,
                "failed_cases": total_cases - successful_cases,
                "overall_accuracy": round(avg_correctness, 3),
                "overall_relevance": round(avg_relevance, 3),
                "overall_completeness": round(avg_completeness, 3),
                "tool_usage_correctness": round(avg_tool_usage, 3),
                "overall_score": round(avg_overall, 3),
                "avg_response_time": round(avg_duration, 3),
                "category_stats": category_stats,
                "tool_usage_stats": tool_stats
            }
            
            # Log aggregate metrics to MLflow
            if tracker.enabled and eval_run_info:
                try:
                    aggregate_metrics = {
                        "total_test_cases": total_cases,
                        "successful_cases": successful_cases,
                        "failed_cases": total_cases - successful_cases,
                        "overall_accuracy": avg_correctness,
                        "overall_relevance": avg_relevance,
                        "overall_completeness": avg_completeness,
                        "tool_usage_correctness": avg_tool_usage,
                        "overall_score": avg_overall,
                        "avg_response_time": avg_duration
                    }
                    tracker.log_metrics(eval_run_info.get("run_id"), aggregate_metrics)
                    
                    # Log results as artifact
                    import tempfile
                    import os
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                        json.dump({
                            "evaluation_id": evaluation_id,
                            "aggregate_results": aggregate_results,
                            "test_case_results": all_results
                        }, f, indent=2)
                        temp_path = f.name
                    
                    try:
                        import mlflow
                        with mlflow.start_run(run_id=eval_run_info.get("run_id")):
                            mlflow.log_artifact(temp_path, "evaluation_results.json")
                    finally:
                        os.unlink(temp_path)
                        
                except Exception as e:
                    logger.warning(f"Failed to log aggregate results to MLflow: {e}")
            
            return {
                "aggregate_results": aggregate_results,
                "test_case_results": all_results
            }
        
        return {"aggregate_results": {}, "test_case_results": []}
    
    finally:
        # Close MLflow run
        if eval_run_info and tracker.enabled:
            try:
                # The context manager should handle this, but ensure it's closed
                pass
            except Exception as e:
                logger.warning(f"Error closing MLflow run: {e}")


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Evaluate agent using MLflow")
    parser.add_argument(
        "--dataset",
        type=str,
        default="backend/data/eval_dataset.jsonl",
        help="Path to evaluation dataset JSONL file"
    )
    parser.add_argument(
        "--experiment",
        type=str,
        default=None,
        help="MLflow experiment name (uses settings default if not specified)"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum agent iterations"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="LLM temperature"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=2000,
        help="Maximum tokens"
    )
    parser.add_argument(
        "--max-test-cases",
        type=int,
        default=None,
        help="Maximum number of test cases to run (for free tier, use 5-10 to stay under 20 request limit)"
    )
    parser.add_argument(
        "--delay-between-tests",
        type=float,
        default=5.0,
        help="Delay in seconds between test cases (default: 5.0)"
    )
    parser.add_argument(
        "--max-requests",
        type=int,
        default=20,
        help="Maximum API requests per day (free tier = 20, default: 20)"
    )
    parser.add_argument(
        "--skip-on-rate-limit",
        action="store_true",
        default=True,
        help="Skip remaining tests when rate limit is hit (default: True)"
    )
    parser.add_argument(
        "--no-skip-on-rate-limit",
        dest="skip_on_rate_limit",
        action="store_false",
        help="Don't skip remaining tests when rate limit is hit"
    )
    
    args = parser.parse_args()
    
    try:
        results = await run_evaluation(
            dataset_path=args.dataset,
            experiment_name=args.experiment,
            max_iterations=args.max_iterations,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            max_test_cases=args.max_test_cases,
            delay_between_tests=args.delay_between_tests,
            max_requests_per_day=args.max_requests,
            skip_on_rate_limit=args.skip_on_rate_limit
        )
        
        # Print summary
        print("\n" + "=" * 60)
        print("EVALUATION SUMMARY")
        print("=" * 60)
        
        agg = results["aggregate_results"]
        print(f"\nEvaluation ID: {agg.get('evaluation_id', 'N/A')}")
        print(f"Total Test Cases: {agg.get('total_test_cases', 0)}")
        print(f"Successful: {agg.get('successful_cases', 0)}")
        print(f"Failed: {agg.get('failed_cases', 0)}")
        print(f"\nOverall Scores:")
        print(f"  Accuracy: {agg.get('overall_accuracy', 0):.3f}")
        print(f"  Relevance: {agg.get('overall_relevance', 0):.3f}")
        print(f"  Completeness: {agg.get('overall_completeness', 0):.3f}")
        print(f"  Tool Usage: {agg.get('tool_usage_correctness', 0):.3f}")
        print(f"  Overall Score: {agg.get('overall_score', 0):.3f}")
        print(f"  Avg Response Time: {agg.get('avg_response_time', 0):.3f}s")
        
        print(f"\nCategory Statistics:")
        for cat, stats in agg.get("category_stats", {}).items():
            print(f"  {cat}: {stats['count']} cases, avg score: {stats['avg_score']:.3f}")
        
        print(f"\nTool Usage Statistics:")
        for tool, stats in agg.get("tool_usage_stats", {}).items():
            print(f"  {tool}: {stats['count']} uses, success rate: {stats['success_rate']:.3f}")
        
        print("\n" + "=" * 60)
        print("Evaluation complete! Check MLflow UI for detailed results.")
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"Evaluation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
