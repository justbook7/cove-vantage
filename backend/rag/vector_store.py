"""
Vector store using Qdrant for semantic search in Cove.

Features:
- Local Qdrant storage (no server required)
- Workspace-specific collections
- Efficient similarity search
- Metadata filtering
- Document management (add, delete, list)
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid


class VectorStore:
    """
    Vector database interface using Qdrant.

    Stores document embeddings for semantic search.
    Organizes documents by workspace.
    """

    def __init__(self, path: str = None):
        """
        Initialize vector store.

        Args:
            path: Path to Qdrant storage directory (default: data/qdrant)
        """
        self.path = path or os.path.join("data", "qdrant")
        self.collection_prefix = "cove_"
        self._client = None
        self._ensure_directory()

    def _ensure_directory(self):
        """Create Qdrant storage directory if it doesn't exist."""
        os.makedirs(self.path, exist_ok=True)

    @property
    def client(self):
        """Get Qdrant client (lazy initialization)."""
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.models import Distance, VectorParams

                self._client = QdrantClient(path=self.path)
                self._distance = Distance
                self._vector_params = VectorParams
            except ImportError:
                raise ImportError(
                    "Qdrant client not installed. "
                    "Install with: pip install qdrant-client"
                )

        return self._client

    def _get_collection_name(self, workspace: str) -> str:
        """Get Qdrant collection name for a workspace."""
        # Sanitize workspace name for collection
        safe_name = workspace.lower().replace(" ", "_")
        return f"{self.collection_prefix}{safe_name}"

    async def ensure_collection(self, workspace: str, vector_size: int = 1536):
        """
        Ensure collection exists for workspace.

        Args:
            workspace: Workspace name
            vector_size: Embedding dimension (default: 1536 for OpenAI)
        """
        collection_name = self._get_collection_name(workspace)

        try:
            # Check if collection exists
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]

            if collection_name not in collection_names:
                # Create new collection
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=self._vector_params(
                        size=vector_size,
                        distance=self._distance.COSINE
                    )
                )
                print(f"✓ Created vector collection: {collection_name}")

        except Exception as e:
            print(f"Error ensuring collection: {e}")
            raise

    async def add_document(
        self,
        workspace: str,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any]
    ) -> str:
        """
        Add a document to the vector store.

        Args:
            workspace: Workspace name
            content: Document text content
            embedding: Vector embedding
            metadata: Document metadata (title, source, etc.)

        Returns:
            Document ID
        """
        from qdrant_client.models import PointStruct

        collection_name = self._get_collection_name(workspace)
        await self.ensure_collection(workspace, len(embedding))

        # Generate unique ID
        doc_id = str(uuid.uuid4())

        # Prepare payload
        payload = {
            "content": content,
            "workspace": workspace,
            "created_at": datetime.utcnow().isoformat(),
            **metadata
        }

        # Insert into Qdrant
        self.client.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=doc_id,
                    vector=embedding,
                    payload=payload
                )
            ]
        )

        return doc_id

    async def search(
        self,
        workspace: str,
        query_embedding: List[float],
        top_k: int = 5,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents.

        Args:
            workspace: Workspace to search in
            query_embedding: Query vector embedding
            top_k: Number of results to return
            score_threshold: Minimum similarity score (0-1)

        Returns:
            List of matching documents with scores
        """
        collection_name = self._get_collection_name(workspace)

        try:
            # Check if collection exists
            await self.ensure_collection(workspace, len(query_embedding))

            # Search
            results = self.client.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                limit=top_k,
                score_threshold=score_threshold
            )

            # Format results
            documents = []
            for result in results:
                doc = {
                    "id": result.id,
                    "score": result.score,
                    "content": result.payload.get("content", ""),
                    "metadata": {
                        k: v for k, v in result.payload.items()
                        if k not in ["content", "workspace"]
                    }
                }
                documents.append(doc)

            return documents

        except Exception as e:
            print(f"Search error: {e}")
            return []

    async def delete_document(self, workspace: str, doc_id: str) -> bool:
        """
        Delete a document from the vector store.

        Args:
            workspace: Workspace name
            doc_id: Document ID to delete

        Returns:
            True if deleted successfully
        """
        collection_name = self._get_collection_name(workspace)

        try:
            self.client.delete(
                collection_name=collection_name,
                points_selector=[doc_id]
            )
            return True
        except Exception as e:
            print(f"Delete error: {e}")
            return False

    async def list_documents(
        self,
        workspace: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List all documents in a workspace.

        Args:
            workspace: Workspace name
            limit: Max documents to return
            offset: Number of documents to skip

        Returns:
            List of document metadata
        """
        collection_name = self._get_collection_name(workspace)

        try:
            # Scroll through collection
            result, _ = self.client.scroll(
                collection_name=collection_name,
                limit=limit,
                offset=offset,
                with_vectors=False
            )

            documents = []
            for point in result:
                doc = {
                    "id": point.id,
                    "content_preview": point.payload.get("content", "")[:200],
                    "metadata": {
                        k: v for k, v in point.payload.items()
                        if k not in ["content", "workspace"]
                    }
                }
                documents.append(doc)

            return documents

        except Exception as e:
            print(f"List error: {e}")
            return []

    async def get_collection_stats(self, workspace: str) -> Dict[str, Any]:
        """
        Get statistics for a workspace collection.

        Args:
            workspace: Workspace name

        Returns:
            Dict with collection stats
        """
        collection_name = self._get_collection_name(workspace)

        try:
            info = self.client.get_collection(collection_name)
            return {
                "name": workspace,
                "document_count": info.points_count,
                "vector_size": info.config.params.vectors.size,
            }
        except Exception:
            return {
                "name": workspace,
                "document_count": 0,
                "vector_size": 0,
            }


# Global vector store instance
_global_vector_store = None


def get_vector_store() -> VectorStore:
    """Get the global vector store instance."""
    global _global_vector_store
    if _global_vector_store is None:
        _global_vector_store = VectorStore()
    return _global_vector_store
