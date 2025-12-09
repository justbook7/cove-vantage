"""
RAG (Retrieval-Augmented Generation) search tool for Cove.

Searches workspace-specific document collections using semantic similarity.

Features:
- Semantic search using embeddings
- Workspace isolation
- Configurable result count and relevance threshold
- Returns document chunks with metadata
"""

from typing import Dict, Any
from .base import BaseTool, ToolResult, ToolError


class RAGSearchTool(BaseTool):
    """Search workspace documents using semantic similarity."""

    def __init__(self):
        """Initialize RAG search tool."""
        super().__init__()
        self.name = "rag_search"
        self._vector_store = None
        self._embeddings = None

    @property
    def vector_store(self):
        """Lazy load vector store."""
        if self._vector_store is None:
            from ..rag.vector_store import get_vector_store
            self._vector_store = get_vector_store()
        return self._vector_store

    @property
    def embeddings(self):
        """Lazy load embeddings module."""
        if self._embeddings is None:
            from ..rag import embeddings
            self._embeddings = embeddings
        return self._embeddings

    async def execute(
        self,
        query: str,
        workspace: str = "General",
        top_k: int = 5,
        score_threshold: float = 0.7
    ) -> ToolResult:
        """
        Search workspace documents for relevant information.

        Args:
            query: Search query text
            workspace: Workspace to search in
            top_k: Number of results to return (max: 10)
            score_threshold: Minimum relevance score (0-1, higher = more relevant)

        Returns:
            ToolResult with matching document chunks
        """
        if not query or not isinstance(query, str):
            raise ToolError("Query must be a non-empty string")

        # Validate parameters
        top_k = max(1, min(top_k, 10))
        score_threshold = max(0.0, min(score_threshold, 1.0))

        try:
            # Generate query embedding
            query_embedding = await self.embeddings.get_embedding(query)

            # Search vector store
            results = await self.vector_store.search(
                workspace=workspace,
                query_embedding=query_embedding,
                top_k=top_k,
                score_threshold=score_threshold
            )

            # Format results for LLM consumption
            if not results:
                return ToolResult(
                    success=True,
                    data={
                        "message": f"No relevant documents found in '{workspace}' workspace.",
                        "results": []
                    },
                    metadata={
                        "workspace": workspace,
                        "query": query,
                        "num_results": 0
                    }
                )

            # Format document chunks
            formatted_results = []
            for i, doc in enumerate(results, 1):
                formatted_results.append({
                    "rank": i,
                    "relevance_score": round(doc["score"], 3),
                    "content": doc["content"],
                    "source": doc["metadata"].get("source", "Unknown"),
                    "title": doc["metadata"].get("title", "Untitled"),
                    "chunk_info": f"Chunk {doc['metadata'].get('chunk_index', 0) + 1}/{doc['metadata'].get('total_chunks', 1)}"
                })

            return ToolResult(
                success=True,
                data={
                    "results": formatted_results,
                    "summary": f"Found {len(results)} relevant document(s) in '{workspace}' workspace."
                },
                metadata={
                    "workspace": workspace,
                    "query": query,
                    "num_results": len(results),
                    "avg_score": sum(r["score"] for r in results) / len(results) if results else 0
                }
            )

        except Exception as e:
            raise ToolError(f"RAG search failed: {str(e)}")

    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get JSON schema for RAG search parameters."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to find relevant information in workspace documents",
                },
                "workspace": {
                    "type": "string",
                    "description": "Workspace to search in (Wooster, Bellcourt, CFB 25, The Quant, General)",
                    "default": "General",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (1-10, default: 5)",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5,
                },
                "score_threshold": {
                    "type": "number",
                    "description": "Minimum relevance score (0-1, default: 0.7). Higher = stricter matching.",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "default": 0.7,
                },
            },
            "required": ["query"],
        }

    def get_description(self) -> str:
        """Get human-readable description."""
        return (
            "Searches workspace-specific document collections using semantic similarity. "
            "Returns relevant document chunks with relevance scores. "
            "Use for: retrieving context from uploaded documents, finding specific information "
            "in workspace knowledge bases, answering questions based on custom documents."
        )
