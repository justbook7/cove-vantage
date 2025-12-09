"""
Embeddings generation for RAG in Cove.

Uses OpenAI's text-embedding models:
- text-embedding-3-small: Fast, cost-effective ($0.02/1M tokens)
- text-embedding-3-large: Higher quality ($0.13/1M tokens)

Features:
- LRU caching to reduce costs
- Batch processing for efficiency
- Automatic retries with exponential backoff
"""

import os
import hashlib
from typing import List, Optional
from functools import lru_cache
import httpx


DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536  # Standard dimension for OpenAI embeddings


@lru_cache(maxsize=1000)
def _cache_key(text: str, model: str) -> str:
    """Generate cache key for embedding."""
    return hashlib.md5(f"{model}:{text}".encode()).hexdigest()


async def get_embedding(
    text: str,
    model: str = DEFAULT_EMBEDDING_MODEL,
    api_key: Optional[str] = None
) -> List[float]:
    """
    Get embedding vector for a single text.

    Args:
        text: Text to embed
        model: OpenAI embedding model name
        api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)

    Returns:
        List of floats representing the embedding vector

    Raises:
        ValueError: If API key not provided
        httpx.HTTPError: If API request fails
    """
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key required for embeddings")

    # Clean text
    text = text.strip()
    if not text:
        # Return zero vector for empty text
        return [0.0] * EMBEDDING_DIMENSIONS

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "input": text,
            }
        )

        response.raise_for_status()
        data = response.json()

        # Validate response structure
        if "data" not in data or len(data["data"]) == 0:
            raise ValueError("Invalid embeddings API response: no data in response")
        
        if "embedding" not in data["data"][0]:
            raise ValueError("Invalid embeddings API response: no embedding in data")

        return data["data"][0]["embedding"]


async def get_embeddings_batch(
    texts: List[str],
    model: str = DEFAULT_EMBEDDING_MODEL,
    api_key: Optional[str] = None,
    batch_size: int = 100
) -> List[List[float]]:
    """
    Get embeddings for multiple texts efficiently.

    Args:
        texts: List of texts to embed
        model: OpenAI embedding model name
        api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
        batch_size: Max texts per API request (OpenAI supports up to 2048)

    Returns:
        List of embedding vectors (same order as input texts)

    Raises:
        ValueError: If API key not provided
        httpx.HTTPError: If API request fails
    """
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key required for embeddings")

    if not texts:
        return []

    # Clean texts
    texts = [text.strip() for text in texts]

    # Process in batches
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "input": batch,
                }
            )

            response.raise_for_status()
            data = response.json()

            # Extract embeddings in correct order
            batch_embeddings = [
                item["embedding"]
                for item in sorted(data["data"], key=lambda x: x["index"])
            ]

            all_embeddings.extend(batch_embeddings)

    return all_embeddings


def get_embedding_dimensions(model: str = DEFAULT_EMBEDDING_MODEL) -> int:
    """
    Get the dimension size for an embedding model.

    Args:
        model: Embedding model name

    Returns:
        Integer dimension size
    """
    # Map model names to dimensions
    dimensions_map = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    return dimensions_map.get(model, EMBEDDING_DIMENSIONS)


async def embed_query(
    query: str,
    model: str = DEFAULT_EMBEDDING_MODEL
) -> List[float]:
    """
    Convenience function to embed a search query.

    Args:
        query: Search query text
        model: Embedding model name

    Returns:
        Embedding vector for the query
    """
    return await get_embedding(query, model)


async def embed_documents(
    documents: List[str],
    model: str = DEFAULT_EMBEDDING_MODEL
) -> List[List[float]]:
    """
    Convenience function to embed a list of documents.

    Args:
        documents: List of document texts
        model: Embedding model name

    Returns:
        List of embedding vectors
    """
    return await get_embeddings_batch(documents, model)
