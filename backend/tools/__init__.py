"""
Tools package for Cove.

Provides pluggable tools for model enhancement:
- Web search (current information)
- Calculator (mathematical computations)
- Code execution (running Python code)
- RAG search (workspace document retrieval)
- Sports data (scores, odds, statistics)
"""

from .base import BaseTool, ToolResult, ToolError
from .registry import ToolRegistry

__all__ = ["BaseTool", "ToolResult", "ToolError", "ToolRegistry"]
