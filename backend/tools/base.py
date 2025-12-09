"""
Base tool interface for Cove.

All tools must inherit from BaseTool and implement:
- execute(): Async method to run the tool
- get_parameters_schema(): JSON schema for parameters
- get_description(): Human-readable description for LLMs
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ToolResult:
    """Result from tool execution."""

    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata or {},
        }


class ToolError(Exception):
    """Exception raised when tool execution fails."""
    pass


class BaseTool(ABC):
    """Abstract base class for all tools."""

    def __init__(self):
        """Initialize the tool."""
        self.name = self.__class__.__name__.replace("Tool", "").lower()

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool with given parameters.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            ToolResult with success status and data/error

        Raises:
            ToolError: If tool execution fails critically
        """
        pass

    @abstractmethod
    def get_parameters_schema(self) -> Dict[str, Any]:
        """
        Get JSON schema for tool parameters.

        Returns:
            JSON schema dict compatible with OpenAI function calling format
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """
        Get human-readable description for LLMs.

        Returns:
            Description string explaining what the tool does
        """
        pass

    def get_name(self) -> str:
        """Get the tool name."""
        return self.name

    def to_llm_function(self) -> Dict[str, Any]:
        """
        Convert tool to LLM function calling format.

        Returns:
            Dict compatible with OpenAI/Anthropic function calling
        """
        return {
            "name": self.get_name(),
            "description": self.get_description(),
            "parameters": self.get_parameters_schema(),
        }

    async def safe_execute(self, **kwargs) -> ToolResult:
        """
        Execute tool with error handling.

        Args:
            **kwargs: Tool parameters

        Returns:
            ToolResult (never raises, always returns result)
        """
        try:
            return await self.execute(**kwargs)
        except ToolError as e:
            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                metadata={"error_type": "ToolError"}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"Unexpected error: {str(e)}",
                metadata={"error_type": type(e).__name__}
            )
