"""MLflow evaluation module with AI judge for response quality assessment."""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    from llm.factory import LLMFactory
    from llm.models import LLMRequest
    from config.settings import get_settings
except ImportError:
    # Handle import errors gracefully
    LLMFactory = None
    LLMRequest = None
    get_settings = None

logger = logging.getLogger(__name__)


class AIJudge:
    """AI judge for evaluating agent response quality."""
    
    def __init__(self, llm_provider=None):
        """Initialize AI judge.
        
        Args:
            llm_provider: LLM provider instance (uses factory if None)
        """
        if llm_provider is None:
            if get_settings is None or LLMFactory is None:
                raise ImportError("Required modules not available. Ensure llm.factory and config.settings are importable.")
            settings = get_settings()
            self.llm_provider = LLMFactory.create_provider(settings)
        else:
            self.llm_provider = llm_provider
    
    async def evaluate_correctness(
        self,
        input_query: str,
        expected_output: str,
        actual_output: str
    ) -> float:
        """Evaluate if the actual output is factually correct compared to expected.
        
        Args:
            input_query: Original user query
            expected_output: Expected answer
            actual_output: Actual agent response
            
        Returns:
            Score between 0.0 and 1.0 (1.0 = fully correct)
        """
        prompt = f"""You are an AI judge evaluating the correctness of an agent's response.

User Query: {input_query}

Expected Answer: {expected_output}

Actual Answer: {actual_output}

Evaluate if the actual answer is factually correct compared to the expected answer.
Consider:
- Are the facts accurate?
- Are the key points present?
- Is the information correct even if wording differs?

Respond with ONLY a JSON object:
{{
    "score": <float between 0.0 and 1.0>,
    "reasoning": "<brief explanation>"
}}

Score guide:
- 1.0: Fully correct, all facts accurate
- 0.8-0.9: Mostly correct, minor differences
- 0.6-0.7: Partially correct, some inaccuracies
- 0.4-0.5: Some correct information, but significant errors
- 0.0-0.3: Mostly incorrect or irrelevant
"""
        
        try:
            request = LLMRequest(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # Low temperature for consistent scoring
                max_tokens=200
            )
            
            response = await self.llm_provider.chat_completion(request)
            content = response.content.strip()
            
            # Extract JSON from response
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                result = json.loads(json_str)
                score = float(result.get("score", 0.5))
                return max(0.0, min(1.0, score))  # Clamp between 0 and 1
            
            # Fallback: try to extract score from text
            if "score" in content.lower():
                # Try to find a number between 0 and 1
                import re
                scores = re.findall(r'0\.\d+|1\.0', content)
                if scores:
                    return float(scores[0])
            
            logger.warning(f"Could not parse correctness score from: {content}")
            return 0.5  # Default neutral score
            
        except Exception as e:
            logger.error(f"Error evaluating correctness: {e}", exc_info=True)
            return 0.5  # Default neutral score
    
    async def evaluate_relevance(
        self,
        input_query: str,
        actual_output: str
    ) -> float:
        """Evaluate if the actual output is relevant to the query.
        
        Args:
            input_query: Original user query
            actual_output: Actual agent response
            
        Returns:
            Score between 0.0 and 1.0 (1.0 = fully relevant)
        """
        prompt = f"""You are an AI judge evaluating the relevance of an agent's response.

User Query: {input_query}

Agent Response: {actual_output}

Evaluate if the agent's response is relevant to the user's query.
Consider:
- Does it address the question asked?
- Is it on-topic?
- Does it provide useful information related to the query?

Respond with ONLY a JSON object:
{{
    "score": <float between 0.0 and 1.0>,
    "reasoning": "<brief explanation>"
}}

Score guide:
- 1.0: Fully relevant, directly addresses the query
- 0.8-0.9: Mostly relevant, minor tangents
- 0.6-0.7: Somewhat relevant, partially addresses query
- 0.4-0.5: Partially relevant, but misses key aspects
- 0.0-0.3: Not relevant or off-topic
"""
        
        try:
            request = LLMRequest(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200
            )
            
            response = await self.llm_provider.chat_completion(request)
            content = response.content.strip()
            
            # Extract JSON from response
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                result = json.loads(json_str)
                score = float(result.get("score", 0.5))
                return max(0.0, min(1.0, score))
            
            # Fallback
            import re
            scores = re.findall(r'0\.\d+|1\.0', content)
            if scores:
                return float(scores[0])
            
            logger.warning(f"Could not parse relevance score from: {content}")
            return 0.5
            
        except Exception as e:
            logger.error(f"Error evaluating relevance: {e}", exc_info=True)
            return 0.5
    
    async def evaluate_completeness(
        self,
        input_query: str,
        expected_output: str,
        actual_output: str
    ) -> float:
        """Evaluate if the actual output is complete compared to expected.
        
        Args:
            input_query: Original user query
            expected_output: Expected answer (may contain multiple aspects)
            actual_output: Actual agent response
            
        Returns:
            Score between 0.0 and 1.0 (1.0 = fully complete)
        """
        prompt = f"""You are an AI judge evaluating the completeness of an agent's response.

User Query: {input_query}

Expected Answer (reference): {expected_output}

Actual Answer: {actual_output}

Evaluate if the actual answer covers all aspects that should be addressed.
Consider:
- Are all key points covered?
- Is the answer comprehensive?
- Are important details included?

Respond with ONLY a JSON object:
{{
    "score": <float between 0.0 and 1.0>,
    "reasoning": "<brief explanation>"
}}

Score guide:
- 1.0: Fully complete, covers all aspects
- 0.8-0.9: Mostly complete, minor omissions
- 0.6-0.7: Partially complete, some aspects missing
- 0.4-0.5: Incomplete, significant aspects missing
- 0.0-0.3: Very incomplete or superficial
"""
        
        try:
            request = LLMRequest(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200
            )
            
            response = await self.llm_provider.chat_completion(request)
            content = response.content.strip()
            
            # Extract JSON from response
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                result = json.loads(json_str)
                score = float(result.get("score", 0.5))
                return max(0.0, min(1.0, score))
            
            # Fallback
            import re
            scores = re.findall(r'0\.\d+|1\.0', content)
            if scores:
                return float(scores[0])
            
            logger.warning(f"Could not parse completeness score from: {content}")
            return 0.5
            
        except Exception as e:
            logger.error(f"Error evaluating completeness: {e}", exc_info=True)
            return 0.5
    
    async def evaluate_tool_usage(
        self,
        expected_tools: List[str],
        actual_tools: List[str]
    ) -> float:
        """Evaluate if the correct tools were used.
        
        Args:
            expected_tools: List of expected tool names
            actual_tools: List of actual tool names used
            
        Returns:
            Score between 0.0 and 1.0 (1.0 = all expected tools used)
        """
        if not expected_tools:
            # If no expected tools, check if tools were used appropriately
            return 1.0 if actual_tools else 0.5
        
        if not actual_tools:
            return 0.0  # Expected tools but none used
        
        # Calculate overlap
        expected_set = set(expected_tools)
        actual_set = set(actual_tools)
        
        # Precision: how many used tools were expected
        if actual_set:
            precision = len(actual_set & expected_set) / len(actual_set)
        else:
            precision = 0.0
        
        # Recall: how many expected tools were used
        recall = len(actual_set & expected_set) / len(expected_set) if expected_set else 0.0
        
        # F1 score (harmonic mean)
        if precision + recall > 0:
            f1 = 2 * (precision * recall) / (precision + recall)
        else:
            f1 = 0.0
        
        return f1
    
    async def evaluate_response(
        self,
        input_query: str,
        expected_output: str,
        actual_output: str,
        expected_tools: Optional[List[str]] = None,
        actual_tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Evaluate a complete response with all metrics.
        
        Args:
            input_query: Original user query
            expected_output: Expected answer
            actual_output: Actual agent response
            expected_tools: List of expected tool names
            actual_tools: List of actual tool names used
            
        Returns:
            Dictionary with all evaluation scores
        """
        expected_tools = expected_tools or []
        actual_tools = actual_tools or []
        
        # Evaluate all aspects
        correctness = await self.evaluate_correctness(input_query, expected_output, actual_output)
        relevance = await self.evaluate_relevance(input_query, actual_output)
        completeness = await self.evaluate_completeness(input_query, expected_output, actual_output)
        tool_usage = await self.evaluate_tool_usage(expected_tools, actual_tools)
        
        # Calculate overall score (weighted average)
        overall = (correctness * 0.4 + relevance * 0.3 + completeness * 0.2 + tool_usage * 0.1)
        
        return {
            "correctness": round(correctness, 3),
            "relevance": round(relevance, 3),
            "completeness": round(completeness, 3),
            "tool_usage": round(tool_usage, 3),
            "overall_score": round(overall, 3),
            "expected_tools": expected_tools,
            "actual_tools": actual_tools
        }
