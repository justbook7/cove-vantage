"""
Intent Classification and Smart Routing for Cove.

This module analyzes user queries to determine:
- Query complexity (simple, moderate, complex, expert)
- Which models to use (1-5 models based on complexity)
- Which tools might be needed
- Recommended workflow type

Implementation uses hybrid approach:
1. Rule-based classification for obvious patterns
2. Cheap model (gemini-2.5-flash) for ambiguous cases
"""

import json
import re
from typing import Dict, List, Any
from functools import lru_cache
import hashlib

from .config import COUNCIL_MODELS, INTENT_CLASSIFIER_MODEL


# Keyword patterns for rule-based classification
SIMPLE_PATTERNS = [
    r"\b(what is|what's|define|meaning of)\b",
    r"^\d+\s*[\+\-\*/]\s*\d+",  # Simple math: 2 + 2
    r"\b(hello|hi|hey|thanks|thank you)\b",  # Greetings
]

COMPLEX_PATTERNS = [
    r'\b(compare|contrast|analyze|evaluate|assess)\b',
    r'\b(why|how|explain|elaborate)\b.*\b(and|or)\b',  # Multiple questions
    r'\b(pros and cons|advantages and disadvantages)\b',
    r'\b(comprehensive|detailed|thorough)\b.*\b(analysis|review|report)\b',
]

MATH_CODE_PATTERNS = [
    r'\b(calculate|compute|algorithm|optimize|solve)\b',
    r'\b(code|script|program|function|class)\b',
    r'\b(python|javascript|java|sql)\b',
    r'\b(api|endpoint|database)\b',
]

CREATIVE_PATTERNS = [
    r'\b(write|draft|compose|create)\b.*\b(article|essay|story|blog|post)\b',
    r'\b(wooster|bellcourt)\b',  # Specific workspaces
    r'\b(style|tone|voice)\b',
]

SPORTS_PATTERNS = [
    r'\b(spread|total|parlay|slate|vegas|line|odds)\b',
    r'\b(cfb|nfl|nba|mlb)\b',
    r'\b(team|player|game|match|score)\b.*\b(stats|statistics|data)\b',
]

WEB_SEARCH_PATTERNS = [
    r'\b(latest|recent|current|today|this week|news)\b',
    r'\b(who is|who are|what happened|when did)\b',
    r'\b(price|cost|value)\b.*\b(of|for)\b',
]


def _count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def _matches_patterns(text: str, patterns: List[str]) -> bool:
    """Check if text matches any of the regex patterns."""
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in patterns)


def _rule_based_classification(query: str) -> Dict[str, Any]:
    """
    Fast rule-based classification for obvious cases.

    Returns dict with classification or None if uncertain.
    """
    word_count = _count_words(query)

    # Very short queries are usually simple
    if word_count < 10:
        if _matches_patterns(query, SIMPLE_PATTERNS):
            return {
                "complexity": "simple",
                "confidence": 0.9,
                "reasoning": "Short query with simple pattern",
            }

    # Math/code queries
    if _matches_patterns(query, MATH_CODE_PATTERNS):
        return {
            "complexity": "moderate",
            "confidence": 0.8,
            "reasoning": "Math or code-related query",
            "suggested_tools": ["calculator", "code_execution"],
        }

    # Sports queries
    if _matches_patterns(query, SPORTS_PATTERNS):
        return {
            "complexity": "moderate",
            "confidence": 0.85,
            "reasoning": "Sports data query",
            "suggested_tools": ["sports_data", "web_search"],
        }

    # Creative/content queries (often need full council)
    if _matches_patterns(query, CREATIVE_PATTERNS):
        return {
            "complexity": "complex",
            "confidence": 0.8,
            "reasoning": "Creative or content production query",
            "suggested_tools": ["rag_search", "web_search"],
        }

    # Complex analytical queries
    if _matches_patterns(query, COMPLEX_PATTERNS):
        return {
            "complexity": "complex",
            "confidence": 0.85,
            "reasoning": "Complex analytical query requiring multiple perspectives",
        }

    # Queries mentioning recent events need web search
    if _matches_patterns(query, WEB_SEARCH_PATTERNS):
        return {
            "complexity": "moderate",
            "confidence": 0.7,
            "reasoning": "Query requires current information",
            "suggested_tools": ["web_search"],
        }

    # Long queries (>50 words) are typically complex
    if word_count > 50:
        return {
            "complexity": "complex",
            "confidence": 0.75,
            "reasoning": "Long, detailed query",
        }

    # Uncertain - return None to trigger model-based classification
    return None


@lru_cache(maxsize=128)
def _cache_key(query: str) -> str:
    """Generate cache key for query classification."""
    return hashlib.md5(query.lower().strip().encode()).hexdigest()


async def _llm_classify_fallback(query: str) -> Dict[str, Any]:
    """
    Use cheap model (gemini-2.5-flash) for ambiguous case classification.

    Cost: ~$0.001 per classification
    Cached: Yes (128 most recent queries)

    Args:
        query: User's question

    Returns:
        Classification dict with complexity, reasoning, tools
    """
    # Import here to avoid circular dependency
    from .openrouter import query_model

    system_prompt = """You are an intent classifier for an LLM orchestration system.

Classify the query complexity and determine which tools might be needed.

**Complexity Levels:**
- simple: Quick factual questions, greetings, basic math (use 1 model)
- moderate: Questions requiring some analysis or current info (use 2-3 models)
- complex: Multi-faceted questions, comparisons, detailed analysis (use 3-4 models)
- expert: High-stakes content, deep analysis, multiple domains (use 4+ models)

**Available Tools:**
- calculator: Math and numerical computations
- web_search: Current events, recent information, facts
- code_execution: Running code, algorithms
- sports_data: Sports scores, odds, statistics
- rag_search: Search workspace documents

Respond with JSON only:
{
    "complexity": "simple|moderate|complex|expert",
    "reasoning": "brief explanation in 10 words or less",
    "tools_needed": ["tool1", "tool2"],
    "confidence": 0.0-1.0
}"""

    user_prompt = f"Classify this query:\n\n{query}"

    try:
        response = await query_model(
            INTENT_CLASSIFIER_MODEL,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            timeout=10.0
        )

        if not response or 'content' not in response:
            # Fallback to moderate if model fails
            return {
                "complexity": "moderate",
                "confidence": 0.3,
                "reasoning": "LLM classification failed, defaulting to moderate",
                "suggested_tools": [],
            }

        # Parse JSON response
        content = response['content'].strip()
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        result = json.loads(content)

        return {
            "complexity": result.get("complexity", "moderate"),
            "confidence": result.get("confidence", 0.7),
            "reasoning": result.get("reasoning", "LLM classification"),
            "suggested_tools": result.get("tools_needed", []),
        }

    except json.JSONDecodeError:
        # Failed to parse JSON
        return {
            "complexity": "moderate",
            "confidence": 0.3,
            "reasoning": "LLM returned invalid JSON, defaulting to moderate",
            "suggested_tools": [],
        }
    except Exception as e:
        # Any other error
        return {
            "complexity": "moderate",
            "confidence": 0.3,
            "reasoning": f"Classification error: {str(e)[:50]}",
            "suggested_tools": [],
        }


async def classify_intent(query: str, workspace: str = "General") -> Dict[str, Any]:
    """
    Classify query intent and determine routing strategy.

    Args:
        query: User's question/prompt
        workspace: Workspace context (Wooster, Bellcourt, CFB 25, The Quant, General)

    Returns:
        {
            "complexity": "simple" | "moderate" | "complex" | "expert",
            "suggested_models": List[str],  # 1-5 model identifiers
            "reasoning": str,  # Why this classification was chosen
            "use_tools": List[str],  # Suggested tools
            "workflow": str,  # "quick" | "dual_check" | "deliberation" | "expert_panel"
            "estimated_cost": float,  # Rough USD estimate
        }
    """

    # Try rule-based classification first (fast, free)
    result = _rule_based_classification(query)

    if result is None:
        # Ambiguous case - use cheap model classification (~$0.001)
        result = await _llm_classify_fallback(query)

    # Extract complexity and tools
    complexity = result["complexity"]
    suggested_tools = result.get("suggested_tools", [])

    # Route models based on complexity
    models = await route_models(complexity, workspace, suggested_tools)

    # Determine workflow type
    if complexity == "simple":
        workflow = "quick"
    elif complexity == "moderate":
        workflow = "dual_check" if len(models) == 2 else "deliberation"
    elif complexity == "complex":
        workflow = "deliberation"
    else:  # expert
        workflow = "expert_panel"

    # Estimate cost (very rough)
    # Assume average of 1000 input tokens, 500 output tokens per model
    avg_cost_per_model = 0.005  # $0.005 per model call
    estimated_cost = len(models) * avg_cost_per_model

    return {
        "complexity": complexity,
        "suggested_models": models,
        "reasoning": result["reasoning"],
        "use_tools": suggested_tools,
        "workflow": workflow,
        "estimated_cost": round(estimated_cost, 3),
        "confidence": result.get("confidence", 0.5),
    }


async def route_models(
    complexity: str,
    workspace: str = "General",
    suggested_tools: List[str] = None
) -> List[str]:
    """
    Select which models to use based on complexity and workspace.

    Args:
        complexity: Query complexity level
        workspace: User's workspace context
        suggested_tools: Tools that might be needed

    Returns:
        List of 1-5 model identifiers to use
    """

    # Workspace-specific overrides
    if workspace == "Wooster":
        # Wooster always uses full council for content quality
        return COUNCIL_MODELS

    if workspace == "The Quant":
        # Quant uses reasoning-focused models
        return [
            "anthropic/claude-sonnet-4.5",  # Strong reasoning
            "openai/gpt-5.1",  # Good at analysis
        ]

    if workspace == "Bellcourt":
        # Bellcourt uses analytical models
        return [
            "anthropic/claude-sonnet-4.5",
            "openai/gpt-5.1",
            "google/gemini-3-pro-preview",
        ]

    if workspace == "CFB 25":
        # Sports queries use full council
        return COUNCIL_MODELS

    # General workspace - route by complexity
    if complexity == "simple":
        # Single fastest model
        return ["google/gemini-3-pro-preview"]  # Fast and cheap

    elif complexity == "moderate":
        # Two complementary models
        return [
            "anthropic/claude-sonnet-4.5",
            "openai/gpt-5.1",
        ]

    elif complexity == "complex":
        # Three strong models
        return [
            "anthropic/claude-sonnet-4.5",
            "openai/gpt-5.1",
            "google/gemini-3-pro-preview",
        ]

    else:  # expert
        # Full council
        return COUNCIL_MODELS
