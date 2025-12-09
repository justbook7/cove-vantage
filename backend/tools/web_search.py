"""
Web search tool for retrieving current information.

Supports multiple providers:
- Tavily API (recommended, requires API key)
- DuckDuckGo (fallback, no API key needed)

Provides:
- Search results with titles, URLs, snippets
- Optional content extraction from pages
- Configurable result limits
"""

import os
from typing import Dict, Any, List, Optional
import httpx
from .base import BaseTool, ToolResult, ToolError


class WebSearchTool(BaseTool):
    """Web search tool using Tavily or DuckDuckGo."""

    def __init__(self):
        """Initialize web search tool."""
        super().__init__()
        self.name = "web_search"
        self.tavily_api_key = os.getenv("TAVILY_API_KEY")
        self.timeout = 30.0

    async def execute(
        self,
        query: str,
        num_results: int = 5,
        include_content: bool = False
    ) -> ToolResult:
        """
        Search the web for current information.

        Args:
            query: Search query string
            num_results: Number of results to return (default: 5, max: 10)
            include_content: Whether to extract page content (slower)

        Returns:
            ToolResult with search results list
        """
        if not query or not isinstance(query, str):
            raise ToolError("Query must be a non-empty string")

        # Validate num_results
        num_results = max(1, min(num_results, 10))

        # Try Tavily API if available
        if self.tavily_api_key:
            try:
                results = await self._search_tavily(query, num_results, include_content)
                return ToolResult(
                    success=True,
                    data=results,
                    metadata={
                        "provider": "tavily",
                        "query": query,
                        "num_results": len(results)
                    }
                )
            except Exception as e:
                # Fall through to DuckDuckGo
                print(f"Tavily search failed: {e}")

        # Fallback to DuckDuckGo
        try:
            results = await self._search_duckduckgo(query, num_results)
            return ToolResult(
                success=True,
                data=results,
                metadata={
                    "provider": "duckduckgo",
                    "query": query,
                    "num_results": len(results)
                }
            )
        except Exception as e:
            raise ToolError(f"Web search failed: {str(e)}")

    async def _search_tavily(
        self,
        query: str,
        num_results: int,
        include_content: bool
    ) -> List[Dict[str, Any]]:
        """
        Search using Tavily API.

        Args:
            query: Search query
            num_results: Number of results
            include_content: Whether to include full content

        Returns:
            List of search result dicts
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.tavily_api_key,
                    "query": query,
                    "max_results": num_results,
                    "include_answer": True,
                    "include_raw_content": include_content,
                },
                headers={"Content-Type": "application/json"}
            )

            response.raise_for_status()
            data = response.json()

            # Format results
            results = []
            for item in data.get("results", []):
                result = {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                }
                if include_content and "raw_content" in item:
                    result["content"] = item["raw_content"][:5000]  # Limit content size

                results.append(result)

            # Add answer if available
            if data.get("answer"):
                results.insert(0, {
                    "type": "answer",
                    "content": data["answer"]
                })

            return results

    async def _search_duckduckgo(
        self,
        query: str,
        num_results: int
    ) -> List[Dict[str, Any]]:
        """
        Search using DuckDuckGo instant answer API.

        Args:
            query: Search query
            num_results: Number of results (limited to related topics)

        Returns:
            List of search result dicts
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # DuckDuckGo instant answer API
            response = await client.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": query,
                    "format": "json",
                    "no_html": 1,
                    "skip_disambig": 1,
                }
            )

            response.raise_for_status()
            data = response.json()

            results = []

            # Add abstract if available
            if data.get("Abstract"):
                results.append({
                    "type": "answer",
                    "title": data.get("Heading", "Answer"),
                    "content": data["Abstract"],
                    "url": data.get("AbstractURL", ""),
                })

            # Add related topics
            for topic in data.get("RelatedTopics", [])[:num_results]:
                if isinstance(topic, dict) and "Text" in topic:
                    text = topic.get("Text", "")
                    # Safely split and get first part, handling empty strings
                    title_parts = text.split(" - ")
                    title = title_parts[0] if title_parts else text
                    results.append({
                        "title": title,
                        "snippet": text,
                        "url": topic.get("FirstURL", ""),
                    })

            # If no results, provide a message
            if not results:
                results.append({
                    "type": "info",
                    "content": (
                        f"No direct results found for '{query}'. "
                        "Try rephrasing or use more specific terms."
                    )
                })

            return results

    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get JSON schema for web search parameters."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to find information on the web",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of search results to return (1-10, default: 5)",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5,
                },
                "include_content": {
                    "type": "boolean",
                    "description": "Whether to extract full page content (slower)",
                    "default": False,
                },
            },
            "required": ["query"],
        }

    def get_description(self) -> str:
        """Get human-readable description."""
        provider = "Tavily" if self.tavily_api_key else "DuckDuckGo"
        return (
            f"Searches the web for current information using {provider}. "
            "Returns titles, URLs, and snippets from search results. "
            "Use for: recent events, current prices, latest news, fact-checking."
        )
