"""
Tool orchestrator for Cove.

Coordinates tool execution with the LLM council:
1. Tool selection: Determine which tools are needed
2. Tool execution: Run tools in parallel where possible
3. Result formatting: Package results for council consumption
4. Error handling: Graceful degradation on tool failures

Integrates with intent classifier and workflows.
"""

from typing import List, Dict, Any, Optional
from .tools.registry import get_registry
from .tools.calculator import CalculatorTool
from .tools.web_search import WebSearchTool
from .tools.code_execution import CodeExecutionTool
from .tools.rag_search import RAGSearchTool
from .tools.sports_data import SportsDataTool
from .config import FEATURE_FLAGS


# Initialize global tool registry
def initialize_tools():
    """Register all available tools."""
    registry = get_registry()

    # Register calculator (always available)
    registry.register(CalculatorTool())

    # Register web search (always available)
    registry.register(WebSearchTool())

    # Register code execution (always available)
    registry.register(CodeExecutionTool())

    # Register sports data (always available)
    registry.register(SportsDataTool())

    # Register RAG search if enabled
    if FEATURE_FLAGS.get("rag_enabled", False):
        registry.register(RAGSearchTool())

    print(f"✓ Initialized {len(registry.list_tools())} tools")


async def run_with_tools(
    user_query: str,
    workspace: str,
    suggested_tools: List[str],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute tools and prepare augmented context for council.

    Args:
        user_query: User's question
        workspace: Workspace name
        suggested_tools: List of tool names to potentially use
        context: Additional context

    Returns:
        Dict with tool results and augmented query
    """
    registry = get_registry()

    # Filter to available tools
    available_tools = [
        tool for tool in suggested_tools
        if registry.has_tool(tool)
    ]

    if not available_tools:
        # No tools needed, return original query
        return {
            "tools_used": [],
            "tool_results": [],
            "augmented_query": user_query,
            "success": True
        }

    # Execute tools
    tool_results = []
    successful_tools = []

    for tool_name in available_tools:
        try:
            # Prepare tool parameters based on tool type
            params = _prepare_tool_params(
                tool_name,
                user_query,
                workspace,
                context
            )

            # Execute tool
            result = await registry.execute_tool(tool_name, **params)

            tool_results.append({
                "tool": tool_name,
                "success": result.success,
                "data": result.data,
                "error": result.error,
                "metadata": result.metadata or {}
            })

            if result.success:
                successful_tools.append(tool_name)

        except Exception as e:
            tool_results.append({
                "tool": tool_name,
                "success": False,
                "data": None,
                "error": str(e),
                "metadata": {}
            })

    # Format augmented query with tool results
    augmented_query = _format_augmented_query(
        user_query,
        tool_results
    )

    return {
        "tools_used": successful_tools,
        "tool_results": tool_results,
        "augmented_query": augmented_query,
        "success": len(successful_tools) > 0 or len(available_tools) == 0
    }


def _prepare_tool_params(
    tool_name: str,
    user_query: str,
    workspace: str,
    context: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Prepare parameters for tool execution.

    Args:
        tool_name: Tool to execute
        user_query: User's question
        workspace: Workspace name
        context: Additional context

    Returns:
        Dict of tool parameters
    """
    context = context or {}

    if tool_name == "calculator":
        # Extract mathematical expression from query
        # For now, pass the whole query and let the tool handle it
        return {"expression": user_query}

    elif tool_name == "web_search":
        return {
            "query": user_query,
            "num_results": 5,
            "include_content": False
        }

    elif tool_name == "code_execution":
        # Extract code from query if present
        # For now, return empty - typically code would be in context
        code = context.get("code", "")
        if not code:
            # No code to execute
            return {"code": "# No code provided"}
        return {"code": code}

    elif tool_name == "rag_search":
        return {
            "query": user_query,
            "workspace": workspace,
            "top_k": 5,
            "score_threshold": 0.7
        }

    elif tool_name == "sports_data":
        # Determine sport and data type from query
        sport = "americanfootball_ncaaf"  # Default to CFB
        data_type = "scores"  # Default to scores

        query_lower = user_query.lower()

        # Detect sport
        if any(word in query_lower for word in ["nfl", "pro football"]):
            sport = "americanfootball_nfl"
        elif any(word in query_lower for word in ["nba", "basketball"]):
            sport = "basketball_nba"
        elif any(word in query_lower for word in ["mlb", "baseball"]):
            sport = "baseball_mlb"

        # Detect data type
        if any(word in query_lower for word in ["odds", "line", "spread", "betting", "vegas"]):
            data_type = "odds"
        elif any(word in query_lower for word in ["schedule", "upcoming", "next game"]):
            data_type = "schedule"
        elif any(word in query_lower for word in ["stats", "statistics", "record"]):
            data_type = "stats"

        return {
            "sport": sport,
            "data_type": data_type
        }

    else:
        # Generic parameters
        return {"query": user_query}


def _format_augmented_query(
    original_query: str,
    tool_results: List[Dict[str, Any]]
) -> str:
    """
    Format tool results into augmented query for council.

    Args:
        original_query: Original user question
        tool_results: Results from tool execution

    Returns:
        Augmented query string with tool context
    """
    if not tool_results:
        return original_query

    parts = [f"User Question: {original_query}", ""]

    # Add successful tool results
    successful = [r for r in tool_results if r["success"]]

    if successful:
        parts.append("Additional Context from Tools:")
        parts.append("")

        for result in successful:
            tool_name = result["tool"]
            data = result["data"]

            parts.append(f"--- {tool_name.upper()} ---")

            if tool_name == "calculator":
                parts.append(f"Calculation Result: {data}")

            elif tool_name == "web_search":
                parts.append("Search Results:")
                for item in data[:3]:  # Limit to top 3 results
                    if "title" in item:
                        parts.append(f"- {item['title']}")
                        parts.append(f"  {item.get('snippet', item.get('content', ''))[:200]}")
                        parts.append(f"  URL: {item.get('url', 'N/A')}")

            elif tool_name == "rag_search":
                if "results" in data:
                    parts.append(f"Found {len(data['results'])} relevant document(s):")
                    for doc in data["results"]:
                        parts.append(f"- [{doc['title']}] (Relevance: {doc['relevance_score']})")
                        parts.append(f"  {doc['content'][:300]}...")
                else:
                    parts.append(data.get("message", "No results"))

            elif tool_name == "code_execution":
                if data.get("stdout"):
                    parts.append(f"Output: {data['stdout']}")
                if data.get("return_value") is not None:
                    parts.append(f"Return Value: {data['return_value']}")
                if data.get("stderr"):
                    parts.append(f"Errors: {data['stderr']}")

            elif tool_name == "sports_data":
                parts.append(f"Source: {data.get('source', 'unknown')}")
                if "games" in data:
                    parts.append(f"Found {data.get('count', 0)} game(s):")
                    for game in data["games"][:5]:  # Limit to 5 games
                        parts.append(f"- {game.get('name', 'Unknown game')}")
                        if "home_score" in game:
                            parts.append(f"  Score: {game.get('away_team', 'Away')} {game.get('away_score', '0')} - "
                                       f"{game.get('home_team', 'Home')} {game.get('home_score', '0')}")
                        if "status" in game:
                            parts.append(f"  Status: {game['status']}")
                        if "bookmakers" in game:
                            parts.append(f"  Odds available from {len(game['bookmakers'])} sportsbook(s)")
                elif "upcoming_games" in data:
                    parts.append(f"Found {data.get('count', 0)} upcoming game(s):")
                    for game in data["upcoming_games"][:5]:
                        parts.append(f"- {game.get('name', 'Unknown game')} on {game.get('date', 'TBD')}")
                elif "stats" in data:
                    stats = data["stats"]
                    parts.append(f"Team: {stats.get('team', 'Unknown')}")
                    parts.append(f"Record: {stats.get('wins', 0)}-{stats.get('losses', 0)}")

            parts.append("")

    # Note failed tools
    failed = [r for r in tool_results if not r["success"]]
    if failed:
        parts.append("Note: Some tools failed:")
        for result in failed:
            parts.append(f"- {result['tool']}: {result.get('error', 'Unknown error')}")
        parts.append("")

    return "\n".join(parts)


def get_available_tools() -> List[str]:
    """
    Get list of currently available tool names.

    Returns:
        List of tool names
    """
    return get_registry().list_tools()


def get_tools_description() -> str:
    """
    Get human-readable description of all tools.

    Returns:
        Formatted tool descriptions
    """
    return get_registry().get_tools_prompt()
