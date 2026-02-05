"""Analytics aggregator for inference logs."""

import json
import aiosqlite
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict, Counter
from statistics import mean, median

from inference_logging import get_inference_logger
from config.settings import get_settings


class AnalyticsAggregator:
    """Aggregates analytics from inference logs."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize analytics aggregator.
        
        Args:
            db_path: Path to SQLite database (uses settings if None)
        """
        # Use singleton logger instance
        self.logger = get_inference_logger(db_path=db_path)
        settings = get_settings()
        self.db_path = db_path or settings.inference_log_db_path
    
    async def _get_all_logs(self) -> List[Dict[str, Any]]:
        """Get all logs from database.
        
        Returns:
            List of all log entries
        """
        # Use the logger's ensure_db_initialized method
        await self.logger._ensure_db_initialized()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM inference_logs
                ORDER BY timestamp DESC
            """) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    def _parse_metadata(self, metadata_str: Optional[str]) -> Dict[str, Any]:
        """Parse metadata JSON string.
        
        Args:
            metadata_str: Metadata as JSON string or dict
            
        Returns:
            Parsed metadata dict
        """
        if not metadata_str:
            return {}
        
        if isinstance(metadata_str, dict):
            return metadata_str
        
        try:
            return json.loads(metadata_str)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    async def get_overview_stats(self) -> Dict[str, Any]:
        """Get overview statistics.
        
        Returns:
            Dictionary with overview statistics
        """
        logs = await self._get_all_logs()
        
        if not logs:
            return {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "success_rate": 0.0,
                "avg_duration": 0.0,
                "median_duration": 0.0,
                "min_duration": 0.0,
                "max_duration": 0.0,
                "total_duration": 0.0,
                "error_rate": 0.0,
                "requests_by_status": {},
                "requests_by_path": {},
                "requests_by_method": {},
                "total_tool_calls": 0,
                "total_iterations": 0,
                "avg_iterations": 0.0,
                "avg_tool_calls_per_request": 0.0
            }
        
        successful = sum(1 for log in logs if log.get("status_code", 0) < 400)
        failed = len(logs) - successful
        durations = [log.get("duration", 0) for log in logs]
        
        # Parse metadata for tool stats
        total_tool_calls = 0
        total_iterations = 0
        requests_with_tools = 0
        
        for log in logs:
            metadata = self._parse_metadata(log.get("metadata"))
            tool_count = metadata.get("tool_count", 0)
            iterations = metadata.get("iterations", 0)
            
            if tool_count > 0:
                requests_with_tools += 1
                total_tool_calls += tool_count
                total_iterations += iterations
        
        # Status code distribution
        status_counter = Counter(log.get("status_code", 0) for log in logs)
        requests_by_status = {str(k): v for k, v in status_counter.items()}
        
        # Path distribution
        path_counter = Counter(log.get("path", "unknown") for log in logs)
        requests_by_path = dict(path_counter)
        
        # Method distribution
        method_counter = Counter(log.get("method", "unknown") for log in logs)
        requests_by_method = dict(method_counter)
        
        return {
            "total_requests": len(logs),
            "successful_requests": successful,
            "failed_requests": failed,
            "success_rate": (successful / len(logs) * 100) if logs else 0.0,
            "avg_duration": mean(durations) if durations else 0.0,
            "median_duration": median(durations) if durations else 0.0,
            "min_duration": min(durations) if durations else 0.0,
            "max_duration": max(durations) if durations else 0.0,
            "total_duration": sum(durations),
            "error_rate": (failed / len(logs) * 100) if logs else 0.0,
            "requests_by_status": requests_by_status,
            "requests_by_path": requests_by_path,
            "requests_by_method": requests_by_method,
            "total_tool_calls": total_tool_calls,
            "total_iterations": total_iterations,
            "avg_iterations": (total_iterations / len(logs)) if logs else 0.0,
            "avg_tool_calls_per_request": (total_tool_calls / len(logs)) if logs else 0.0,
            "requests_with_tools": requests_with_tools
        }
    
    async def get_tool_usage_stats(self) -> Dict[str, Any]:
        """Get tool usage statistics.
        
        Returns:
            Dictionary with tool usage statistics
        """
        logs = await self._get_all_logs()
        
        tool_usage = defaultdict(lambda: {
            "count": 0,
            "success_count": 0,
            "failure_count": 0,
            "total_duration": 0.0,
            "avg_duration": 0.0,
            "requests": []
        })
        
        for log in logs:
            metadata = self._parse_metadata(log.get("metadata"))
            tool_calls = metadata.get("tool_calls", [])
            tool_results = metadata.get("tool_results", [])
            
            # Create a mapping of tool names to results
            tool_results_map = {}
            for result in tool_results:
                tool_name = result.get("tool_name")
                if tool_name:
                    tool_results_map[tool_name] = result
            
            for tool_call in tool_calls:
                tool_name = tool_call.get("tool_name", "unknown")
                tool_usage[tool_name]["count"] += 1
                tool_usage[tool_name]["requests"].append(log.get("request_id"))
                
                # Check if tool succeeded
                tool_result = tool_results_map.get(tool_name)
                if tool_result:
                    if tool_result.get("error") is None:
                        tool_usage[tool_name]["success_count"] += 1
                    else:
                        tool_usage[tool_name]["failure_count"] += 1
                
                # Note: Individual tool duration not tracked, using request duration
                tool_usage[tool_name]["total_duration"] += log.get("duration", 0)
        
        # Calculate averages and clean up
        result = {}
        for tool_name, stats in tool_usage.items():
            count = stats["count"]
            result[tool_name] = {
                "count": count,
                "success_count": stats["success_count"],
                "failure_count": stats["failure_count"],
                "success_rate": (stats["success_count"] / count * 100) if count > 0 else 0.0,
                "failure_rate": (stats["failure_count"] / count * 100) if count > 0 else 0.0,
                "total_duration": stats["total_duration"],
                "avg_duration": stats["total_duration"] / count if count > 0 else 0.0,
                "unique_requests": len(set(stats["requests"]))
            }
        
        # Sort by count (most used first)
        sorted_tools = dict(sorted(result.items(), key=lambda x: x[1]["count"], reverse=True))
        
        return {
            "tools": sorted_tools,
            "total_unique_tools": len(sorted_tools),
            "total_tool_calls": sum(stats["count"] for stats in sorted_tools.values())
        }
    
    async def get_response_time_stats(self, time_window_hours: Optional[int] = None) -> Dict[str, Any]:
        """Get response time statistics.
        
        Args:
            time_window_hours: Optional time window in hours (e.g., 24 for last 24 hours)
            
        Returns:
            Dictionary with response time statistics
        """
        logs = await self._get_all_logs()
        
        # Filter by time window if provided
        if time_window_hours:
            cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
            logs = [
                log for log in logs
                if datetime.fromisoformat(log.get("timestamp", "")) >= cutoff_time
            ]
        
        if not logs:
            return {
                "total_requests": 0,
                "avg_duration": 0.0,
                "median_duration": 0.0,
                "p95_duration": 0.0,
                "p99_duration": 0.0,
                "min_duration": 0.0,
                "max_duration": 0.0,
                "duration_by_path": {},
                "duration_by_status": {}
            }
        
        durations = [log.get("duration", 0) for log in logs]
        sorted_durations = sorted(durations)
        
        # Calculate percentiles
        p95_idx = int(len(sorted_durations) * 0.95)
        p99_idx = int(len(sorted_durations) * 0.99)
        
        # Duration by path
        duration_by_path = defaultdict(list)
        for log in logs:
            path = log.get("path", "unknown")
            duration_by_path[path].append(log.get("duration", 0))
        
        path_stats = {}
        for path, path_durations in duration_by_path.items():
            path_stats[path] = {
                "count": len(path_durations),
                "avg": mean(path_durations),
                "median": median(path_durations),
                "min": min(path_durations),
                "max": max(path_durations)
            }
        
        # Duration by status
        duration_by_status = defaultdict(list)
        for log in logs:
            status = log.get("status_code", 0)
            duration_by_status[status].append(log.get("duration", 0))
        
        status_stats = {}
        for status, status_durations in duration_by_status.items():
            status_stats[str(status)] = {
                "count": len(status_durations),
                "avg": mean(status_durations),
                "median": median(status_durations),
                "min": min(status_durations),
                "max": max(status_durations)
            }
        
        return {
            "total_requests": len(logs),
            "avg_duration": mean(durations),
            "median_duration": median(durations),
            "p95_duration": sorted_durations[p95_idx] if sorted_durations else 0.0,
            "p99_duration": sorted_durations[p99_idx] if sorted_durations else 0.0,
            "min_duration": min(durations),
            "max_duration": max(durations),
            "duration_by_path": path_stats,
            "duration_by_status": status_stats,
            "time_window_hours": time_window_hours
        }
    
    async def get_error_patterns(self) -> Dict[str, Any]:
        """Get error pattern analysis.
        
        Returns:
            Dictionary with error patterns
        """
        logs = await self._get_all_logs()
        
        error_logs = [log for log in logs if log.get("error") or log.get("status_code", 0) >= 400]
        
        if not error_logs:
            return {
                "total_errors": 0,
                "errors_by_status": {},
                "errors_by_path": {},
                "common_errors": [],
                "error_messages": []
            }
        
        # Errors by status
        error_status_counter = Counter(log.get("status_code", 0) for log in error_logs)
        errors_by_status = {str(k): v for k, v in error_status_counter.items()}
        
        # Errors by path
        error_path_counter = Counter(log.get("path", "unknown") for log in error_logs)
        errors_by_path = dict(error_path_counter)
        
        # Error messages
        error_messages = []
        for log in error_logs:
            error_msg = log.get("error")
            if error_msg:
                error_messages.append({
                    "request_id": log.get("request_id"),
                    "timestamp": log.get("timestamp"),
                    "path": log.get("path"),
                    "status_code": log.get("status_code"),
                    "error": error_msg
                })
        
        # Common errors (group by error message)
        error_message_counter = Counter(
            log.get("error", "Unknown error") for log in error_logs if log.get("error")
        )
        common_errors = [
            {"error": error, "count": count}
            for error, count in error_message_counter.most_common(10)
        ]
        
        return {
            "total_errors": len(error_logs),
            "error_rate": (len(error_logs) / len(logs) * 100) if logs else 0.0,
            "errors_by_status": errors_by_status,
            "errors_by_path": errors_by_path,
            "common_errors": common_errors,
            "error_messages": error_messages[:50]  # Limit to 50 most recent
        }
    
    async def get_time_series_stats(self, time_window_hours: int = 24, interval_minutes: int = 60) -> Dict[str, Any]:
        """Get time series statistics.
        
        Args:
            time_window_hours: Time window in hours (default: 24)
            interval_minutes: Interval in minutes for bucketing (default: 60)
            
        Returns:
            Dictionary with time series data
        """
        logs = await self._get_all_logs()
        
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
        filtered_logs = [
            log for log in logs
            if datetime.fromisoformat(log.get("timestamp", "")) >= cutoff_time
        ]
        
        if not filtered_logs:
            return {
                "time_series": [],
                "time_window_hours": time_window_hours,
                "interval_minutes": interval_minutes
            }
        
        # Group by time intervals
        time_buckets = defaultdict(lambda: {
            "count": 0,
            "success_count": 0,
            "error_count": 0,
            "total_duration": 0.0,
            "tool_calls": 0
        })
        
        for log in filtered_logs:
            timestamp = datetime.fromisoformat(log.get("timestamp", ""))
            # Round to nearest interval
            bucket_time = timestamp.replace(
                minute=(timestamp.minute // interval_minutes) * interval_minutes,
                second=0,
                microsecond=0
            )
            bucket_key = bucket_time.isoformat()
            
            time_buckets[bucket_key]["count"] += 1
            if log.get("status_code", 0) < 400:
                time_buckets[bucket_key]["success_count"] += 1
            else:
                time_buckets[bucket_key]["error_count"] += 1
            
            time_buckets[bucket_key]["total_duration"] += log.get("duration", 0)
            
            metadata = self._parse_metadata(log.get("metadata"))
            time_buckets[bucket_key]["tool_calls"] += metadata.get("tool_count", 0)
        
        # Convert to sorted list
        time_series = []
        for bucket_time in sorted(time_buckets.keys()):
            bucket = time_buckets[bucket_time]
            time_series.append({
                "timestamp": bucket_time,
                "count": bucket["count"],
                "success_count": bucket["success_count"],
                "error_count": bucket["error_count"],
                "avg_duration": bucket["total_duration"] / bucket["count"] if bucket["count"] > 0 else 0.0,
                "total_duration": bucket["total_duration"],
                "tool_calls": bucket["tool_calls"]
            })
        
        return {
            "time_series": time_series,
            "time_window_hours": time_window_hours,
            "interval_minutes": interval_minutes
        }
