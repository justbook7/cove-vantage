"""
Document ingestor for RAG in Cove.

Processes various document formats and ingests them into the vector store:
- Text files (.txt, .md)
- PDF documents
- Web pages (URLs)

Features:
- Smart text chunking with overlap
- Metadata extraction
- Batch embedding generation
- Progress tracking
"""

import os
from typing import List, Dict, Any, Optional
from pathlib import Path
import hashlib
from .embeddings import get_embeddings_batch
from .vector_store import get_vector_store


class DocumentIngestor:
    """
    Processes and ingests documents into vector store.

    Handles chunking, embedding generation, and storage.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        embedding_model: str = "text-embedding-3-small"
    ):
        """
        Initialize document ingestor.

        Args:
            chunk_size: Max characters per chunk
            chunk_overlap: Overlap between chunks for context
            embedding_model: OpenAI embedding model to use
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_model = embedding_model
        self.vector_store = get_vector_store()

    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.

        Args:
            text: Text to chunk

        Returns:
            List of text chunks
        """
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings near chunk boundary
                for punct in ['. ', '.\n', '! ', '?\n', '? ']:
                    last_punct = text.rfind(punct, start, end)
                    if last_punct != -1:
                        end = last_punct + len(punct)
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start position with overlap
            start = end - self.chunk_overlap if end < len(text) else len(text)

        return chunks

    async def ingest_text(
        self,
        workspace: str,
        text: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Ingest plain text into vector store.

        Args:
            workspace: Workspace name
            text: Text content
            metadata: Document metadata (title, source, etc.)

        Returns:
            Dict with ingestion results
        """
        # Chunk the text
        chunks = self._chunk_text(text)

        # Generate embeddings for all chunks
        embeddings = await get_embeddings_batch(
            chunks,
            model=self.embedding_model
        )

        # Store each chunk
        doc_ids = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_metadata = {
                **metadata,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }

            doc_id = await self.vector_store.add_document(
                workspace=workspace,
                content=chunk,
                embedding=embedding,
                metadata=chunk_metadata
            )
            doc_ids.append(doc_id)

        return {
            "success": True,
            "document_ids": doc_ids,
            "chunks_created": len(chunks),
            "total_chars": len(text),
        }

    async def ingest_file(
        self,
        workspace: str,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ingest a file into vector store.

        Args:
            workspace: Workspace name
            file_path: Path to file
            metadata: Optional metadata (auto-generated if not provided)

        Returns:
            Dict with ingestion results
        """
        path = Path(file_path)

        if not path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }

        # Auto-generate metadata if not provided
        if metadata is None:
            metadata = {}

        metadata.update({
            "filename": path.name,
            "source": str(path),
            "file_type": path.suffix,
        })

        # Read file based on extension
        try:
            if path.suffix in ['.txt', '.md']:
                text = path.read_text(encoding='utf-8')
            elif path.suffix == '.pdf':
                text = await self._extract_pdf_text(path)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported file type: {path.suffix}"
                }

            return await self.ingest_text(workspace, text, metadata)

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _extract_pdf_text(self, path: Path) -> str:
        """
        Extract text from PDF file.

        Args:
            path: Path to PDF

        Returns:
            Extracted text
        """
        try:
            import pypdf

            text_parts = []
            with open(path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                for page in pdf_reader.pages:
                    text_parts.append(page.extract_text())

            return '\n\n'.join(text_parts)

        except ImportError:
            raise ImportError(
                "pypdf not installed. Install with: pip install pypdf"
            )
        except Exception as e:
            raise Exception(f"Failed to extract PDF text: {str(e)}")

    async def ingest_url(
        self,
        workspace: str,
        url: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ingest content from a URL.

        Args:
            workspace: Workspace name
            url: URL to fetch
            metadata: Optional metadata

        Returns:
            Dict with ingestion results
        """
        try:
            import httpx
            from bs4 import BeautifulSoup

            # Fetch URL
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Extract text
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            text = '\n'.join(line for line in lines if line)

            # Metadata
            if metadata is None:
                metadata = {}

            metadata.update({
                "source": url,
                "title": soup.title.string if soup.title else url,
                "source_type": "web",
            })

            return await self.ingest_text(workspace, text, metadata)

        except ImportError:
            return {
                "success": False,
                "error": "beautifulsoup4 not installed. Install with: pip install beautifulsoup4"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to fetch URL: {str(e)}"
            }

    async def ingest_directory(
        self,
        workspace: str,
        directory: str,
        pattern: str = "*.txt",
        recursive: bool = True
    ) -> Dict[str, Any]:
        """
        Ingest all matching files from a directory.

        Args:
            workspace: Workspace name
            directory: Directory path
            pattern: File pattern to match (e.g., "*.txt", "*.md")
            recursive: Whether to search subdirectories

        Returns:
            Dict with batch ingestion results
        """
        path = Path(directory)

        if not path.is_dir():
            return {
                "success": False,
                "error": f"Not a directory: {directory}"
            }

        # Find matching files
        if recursive:
            files = list(path.rglob(pattern))
        else:
            files = list(path.glob(pattern))

        # Ingest each file
        results = {
            "total_files": len(files),
            "successful": 0,
            "failed": 0,
            "files": []
        }

        for file_path in files:
            result = await self.ingest_file(workspace, str(file_path))

            if result.get("success"):
                results["successful"] += 1
            else:
                results["failed"] += 1

            results["files"].append({
                "path": str(file_path),
                "result": result
            })

        results["success"] = results["failed"] == 0

        return results


# Global ingestor instance
_global_ingestor = None


def get_ingestor() -> DocumentIngestor:
    """Get the global document ingestor instance."""
    global _global_ingestor
    if _global_ingestor is None:
        _global_ingestor = DocumentIngestor()
    return _global_ingestor
