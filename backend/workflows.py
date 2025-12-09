"""
Workflow presets and workspace-specific configurations for Cove.

Defines how different workspaces (Wooster, Bellcourt, CFB 25, The Quant, General)
should handle queries, including:
- Default models to use
- Available tools
- RAG enablement
- Synthesis budget
- Special processing rules
"""

from typing import Dict, List, Any
from .config import COUNCIL_MODELS


WORKFLOW_CONFIGS: Dict[str, Dict[str, Any]] = {
    "General": {
        "description": "General-purpose queries and conversations",
        "default_models": COUNCIL_MODELS,
        "tools": ["web_search", "calculator"],
        "rag_enabled": False,
        "synthesis_budget": "standard",  # "minimal" | "standard" | "comprehensive"
        "skip_synthesis_for_simple": True,
        "auto_invoke_tools": False,
    },

    "Wooster": {
        "description": "Editorial content, articles, and essays with Wooster voice",
        "default_models": COUNCIL_MODELS,  # Always use full council for quality
        "tools": ["web_search", "rag_search"],
        "rag_enabled": True,
        "rag_collection": "wooster_docs",
        "rag_prompt_addition": "Answer in Wooster's voice: formal, precise, British.",
        "synthesis_budget": "comprehensive",  # Always full synthesis for content
        "skip_synthesis_for_simple": False,
        "auto_invoke_tools": True,  # Automatically search style guides
    },

    "Bellcourt": {
        "description": "Strategy, finance, and business analysis",
        "default_models": [
            "anthropic/claude-sonnet-4.5",  # Best for detailed analysis
            "openai/gpt-5.1",  # Strong reasoning
            "google/gemini-3-pro-preview",  # Good for data analysis
        ],
        "tools": ["rag_search", "web_search", "calculator"],
        "rag_enabled": True,
        "rag_collection": "bellcourt_docs",
        "synthesis_budget": "standard",
        "skip_synthesis_for_simple": True,
        "auto_invoke_tools": False,
    },

    "CFB 25": {
        "description": "College football analysis, stats, and media",
        "default_models": COUNCIL_MODELS,
        "tools": ["sports_data", "web_search", "calculator"],
        "rag_enabled": False,  # Sports data is real-time, not RAG-based
        "synthesis_budget": "standard",
        "skip_synthesis_for_simple": True,
        "auto_invoke_tools": True,  # Automatically fetch sports data
        "data_freshness": {
            "historical": "7 days",  # Cache historical data for 7 days
            "current_week": "1 hour",  # Current week data cached for 1 hour
            "injuries": "15 mins",  # Injury data cached for 15 minutes
        },
    },

    "The Quant": {
        "description": "Sports betting analysis with quantitative focus",
        "default_models": [
            "anthropic/claude-sonnet-4.5",  # Strong reasoning
            "openai/gpt-5.1",  # Good at math
        ],
        "tools": ["calculator", "sports_data", "code_execution"],
        "rag_enabled": False,
        "synthesis_budget": "minimal",  # Save tokens on analysis-heavy queries
        "skip_synthesis_for_simple": True,
        "auto_invoke_tools": False,
        "confidence_logic": {
            "require_consensus": True,  # All models must agree on edge
            "min_edge_pct": 3.0,  # Require >3% edge
            "max_std_dev": 0.02,  # Low standard deviation = high confidence
        },
    },
}


def get_workflow_config(workspace: str) -> Dict[str, Any]:
    """
    Get configuration for a specific workspace.

    Args:
        workspace: Workspace name (case-insensitive)

    Returns:
        Workflow configuration dict
    """
    # Normalize workspace name
    workspace_normalized = workspace.strip()

    # Return config or default to General
    return WORKFLOW_CONFIGS.get(workspace_normalized, WORKFLOW_CONFIGS["General"])


def list_workspaces() -> List[str]:
    """
    Get list of all available workspaces.

    Returns:
        List of workspace names
    """
    return list(WORKFLOW_CONFIGS.keys())


def get_workspace_description(workspace: str) -> str:
    """
    Get description of a workspace.

    Args:
        workspace: Workspace name

    Returns:
        Description string
    """
    config = get_workflow_config(workspace)
    return config.get("description", "No description available")


def is_rag_enabled(workspace: str) -> bool:
    """
    Check if RAG is enabled for a workspace.

    Args:
        workspace: Workspace name

    Returns:
        True if RAG is enabled
    """
    config = get_workflow_config(workspace)
    return config.get("rag_enabled", False)


def get_workspace_tools(workspace: str) -> List[str]:
    """
    Get list of available tools for a workspace.

    Args:
        workspace: Workspace name

    Returns:
        List of tool names
    """
    config = get_workflow_config(workspace)
    return config.get("tools", [])


def should_auto_invoke_tools(workspace: str) -> bool:
    """
    Check if tools should be automatically invoked for a workspace.

    Args:
        workspace: Workspace name

    Returns:
        True if tools should be auto-invoked
    """
    config = get_workflow_config(workspace)
    return config.get("auto_invoke_tools", False)


def get_synthesis_budget(workspace: str) -> str:
    """
    Get synthesis budget level for a workspace.

    Args:
        workspace: Workspace name

    Returns:
        "minimal" | "standard" | "comprehensive"
    """
    config = get_workflow_config(workspace)
    return config.get("synthesis_budget", "standard")
