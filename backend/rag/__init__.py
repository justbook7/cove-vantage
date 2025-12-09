"""
RAG (Retrieval-Augmented Generation) package for Cove.

Provides document ingestion, vector storage, and semantic search:
- Embeddings generation (OpenAI)
- Vector storage (Qdrant)
- Document chunking and processing
- Workspace-specific knowledge bases
"""

from .embeddings import get_embedding, get_embeddings_batch
from .vector_store import VectorStore
from .ingestor import DocumentIngestor

__all__ = [
    "get_embedding",
    "get_embeddings_batch",
    "VectorStore",
    "DocumentIngestor",
]
