"""
Tool registry for managing available tools in Cove.

The registry:
- Stores all available tools
- Provides tool lookup by name
- Generates LLM-readable tool descriptions
- Executes tools safely
"""

from typing import Dict, List, Optional, Any
from .base import BaseTool, ToolResult


class ToolRegistry:
    """Central registry for all available tools."""

    def __init__(self):
        """Initialize empty registry."""
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """
        Register a tool in the registry.

        Args:
            tool: BaseTool instance to register

        Raises:
            ValueError: If tool with same name already registered
        """
        tool_name = tool.get_name()
        if tool_name in self._tools:
            raise ValueError(f"Tool '{tool_name}' is already registered")

        self._tools[tool_name] = tool
        print(f"✓ Registered tool: {tool_name}")

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        Get a tool by name.

        Args:
            name: Tool name

        Returns:
            BaseTool instance or None if not found
        """
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """
        Get list of all registered tool names.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """
        Get all tools in LLM function calling format.

        Returns:
            List of tool definitions compatible with OpenAI/Anthropic
        """
        return [tool.to_llm_function() for tool in self._tools.values()]

    def get_tools_prompt(self) -> str:
        """
        Generate human-readable tool descriptions for LLM prompts.

        Returns:
            Formatted string describing all available tools
        """
        if not self._tools:
            return "No tools available."

        lines = ["Available tools:"]
        for tool in self._tools.values():
            name = tool.get_name()
            desc = tool.get_description()
            schema = tool.get_parameters_schema()

            # Extract required parameters
            required = schema.get("required", [])
            properties = schema.get("properties", {})

            param_str = ", ".join(
                f"{param}{'*' if param in required else ''}: {properties.get(param, {}).get('type', 'any')}"
                for param in properties.keys()
            )

            lines.append(f"- {name}({param_str}): {desc}")

        return "\n".join(lines)

    async def execute_tool(self, name: str, **kwargs) -> ToolResult:
        """
        Execute a tool by name.

        Args:
            name: Tool name
            **kwargs: Tool parameters

        Returns:
            ToolResult with execution results

        Raises:
            ValueError: If tool not found
        """
        tool = self.get_tool(name)
        if not tool:
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool '{name}' not found. Available tools: {', '.join(self.list_tools())}",
                metadata={"available_tools": self.list_tools()}
            )

        return await tool.safe_execute(**kwargs)

    def has_tool(self, name: str) -> bool:
        """
        Check if a tool is registered.

        Args:
            name: Tool name

        Returns:
            True if tool exists
        """
        return name in self._tools

    def unregister(self, name: str) -> bool:
        """
        Remove a tool from registry.

        Args:
            name: Tool name

        Returns:
            True if tool was removed, False if not found
        """
        if name in self._tools:
            del self._tools[name]
            return True
        return False


# Global registry instance
_global_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    return _global_registry
