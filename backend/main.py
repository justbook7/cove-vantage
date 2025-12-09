"""FastAPI backend for Project Cove."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio

from . import storage
from .database import init_db
from .council import (
    run_adaptive_council,
    generate_conversation_title,
)
from .intent_classifier import classify_intent
from .metrics import metrics_collector
from .config import FEATURE_FLAGS
from .tool_orchestrator import initialize_tools
from .rag.ingestor import get_ingestor
from .rag.vector_store import get_vector_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and tools on startup."""
    import os
    from pathlib import Path
    
    # Ensure data directory exists
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    print(f"✓ Data directory ready: {data_dir.absolute()}")
    
    # Initialize database tables
    try:
        await init_db()
        print("✓ Database initialized")
    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
        raise

    # Initialize tools
    try:
        initialize_tools()
    except Exception as e:
        print(f"✗ Tool initialization failed: {e}")
        raise

    yield
    # Cleanup on shutdown (if needed)


app = FastAPI(title="Project Cove API", lifespan=lifespan)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    workspace: Optional[str] = "General"


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str
    workspace: Optional[str] = "General"


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    workspace: str
    message_count: int


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    workspace: str
    messages: List[Dict[str, Any]]


# ============================================================================
# Core API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Project Cove API",
        "features": FEATURE_FLAGS
    }


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return await storage.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    conversation = await storage.create_conversation(
        conversation_id,
        workspace=request.workspace or "General"
    )
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = await storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    deleted = await storage.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted", "id": conversation_id}


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the adaptive council process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists
    conversation = await storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Add user message
    await storage.add_user_message(conversation_id, request.content)

    # Classify intent if feature enabled
    intent = None
    models = None
    workflow = "deliberation"
    suggested_tools = None

    if FEATURE_FLAGS.get("intent_classification", True):
        intent = await classify_intent(
            request.content,
            workspace=request.workspace or conversation.get("workspace", "General")
        )
        models = intent["suggested_models"]
        workflow = intent["workflow"]
        suggested_tools = intent.get("use_tools", [])

    # If this is the first message, generate a title in parallel
    title_task = None
    if is_first_message:
        title_task = asyncio.create_task(
            generate_conversation_title(request.content)
        )

    # Run the adaptive council process
    stage1_results, stage2_results, stage3_result, metadata = await run_adaptive_council(
        user_query=request.content,
        workspace=request.workspace or conversation.get("workspace", "General"),
        models=models,
        workflow=workflow,
        suggested_tools=suggested_tools,
        metadata={
            "conversation_id": conversation_id,
            "workspace": request.workspace or conversation.get("workspace", "General")
        }
    )

    # Wait for title if it was being generated
    if title_task:
        title = await title_task
        await storage.update_conversation_title(conversation_id, title)

    # Add assistant message with all stages
    await storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result
    )

    # Return the complete response with metadata and intent
    response = {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }

    if intent:
        response["intent"] = intent

    return response


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the adaptive council process.
    Returns Server-Sent Events as each stage completes.
    """
    # Check if conversation exists
    conversation = await storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0
    workspace = request.workspace or conversation.get("workspace", "General")

    async def event_generator():
        try:
            # Add user message
            await storage.add_user_message(conversation_id, request.content)

            # Classify intent if feature enabled
            intent = None
            models = None
            workflow = "deliberation"
            suggested_tools = None

            if FEATURE_FLAGS.get("intent_classification", True):
                yield f"data: {json.dumps({'type': 'intent_start'})}\n\n"

                intent = await classify_intent(request.content, workspace=workspace)
                models = intent["suggested_models"]
                workflow = intent["workflow"]
                suggested_tools = intent.get("use_tools", [])

                yield f"data: {json.dumps({'type': 'intent_complete', 'data': intent})}\n\n"

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(
                    generate_conversation_title(request.content)
                )

            # Run adaptive council
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"

            stage1_results, stage2_results, stage3_result, metadata = await run_adaptive_council(
                user_query=request.content,
                workspace=workspace,
                models=models,
                workflow=workflow,
                suggested_tools=suggested_tools,
                metadata={
                    "conversation_id": conversation_id,
                    "workspace": workspace
                }
            )

            # Send stage results as they complete
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            if stage2_results:
                yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
                yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': metadata})}\n\n"

            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                await storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Save complete assistant message
            await storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result
            )

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============================================================================
# Metrics & Analytics Endpoints
# ============================================================================

@app.get("/api/metrics/daily")
async def get_daily_metrics(date: Optional[str] = None):
    """
    Get daily cost and usage metrics.

    Args:
        date: Date string (YYYY-MM-DD), defaults to today

    Returns:
        Daily aggregated statistics
    """
    if not FEATURE_FLAGS.get("cost_dashboard", True):
        raise HTTPException(status_code=404, detail="Cost dashboard not enabled")

    return await metrics_collector.get_daily_stats(date)


@app.get("/api/metrics/models")
async def get_model_metrics(model: Optional[str] = None, days: int = 30):
    """
    Get per-model performance statistics.

    Args:
        model: Specific model to query (optional)
        days: Number of days to look back (default 30)

    Returns:
        List of model statistics
    """
    if not FEATURE_FLAGS.get("cost_dashboard", True):
        raise HTTPException(status_code=404, detail="Cost dashboard not enabled")

    return await metrics_collector.get_model_stats(model, days)


@app.get("/api/metrics/dashboard")
async def get_dashboard_metrics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Get comprehensive metrics for cost dashboard.

    Args:
        start_date: Start date (YYYY-MM-DD), defaults to 30 days ago
        end_date: End date (YYYY-MM-DD), defaults to today

    Returns:
        Dashboard data with daily costs, model costs, and performance
    """
    if not FEATURE_FLAGS.get("cost_dashboard", True):
        raise HTTPException(status_code=404, detail="Cost dashboard not enabled")

    return await metrics_collector.get_dashboard_data(start_date, end_date)


@app.get("/api/conversations/{conversation_id}/stats")
async def get_conversation_stats(conversation_id: str):
    """Get statistics for a specific conversation."""
    stats = await storage.get_conversation_stats(conversation_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return stats


# ============================================================================
# Document Management Endpoints (RAG)
# ============================================================================

class DocumentUploadRequest(BaseModel):
    """Request model for document upload."""
    content: str
    title: str
    source: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@app.post("/api/workspaces/{workspace}/documents")
async def upload_document(workspace: str, request: DocumentUploadRequest):
    """
    Upload a document to workspace knowledge base.

    Args:
        workspace: Workspace name
        request: Document content and metadata

    Returns:
        Document ingestion results
    """
    if not FEATURE_FLAGS.get("rag_enabled", False):
        raise HTTPException(status_code=404, detail="RAG not enabled")

    ingestor = get_ingestor()

    metadata = request.metadata or {}
    metadata.update({
        "title": request.title,
        "source": request.source or "direct_upload",
    })

    result = await ingestor.ingest_text(
        workspace=workspace,
        text=request.content,
        metadata=metadata
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Upload failed"))

    return result


@app.get("/api/workspaces/{workspace}/documents")
async def list_documents(
    workspace: str,
    limit: int = 100,
    offset: int = 0
):
    """
    List all documents in a workspace.

    Args:
        workspace: Workspace name
        limit: Max documents to return
        offset: Skip first N documents

    Returns:
        List of document metadata
    """
    if not FEATURE_FLAGS.get("rag_enabled", False):
        raise HTTPException(status_code=404, detail="RAG not enabled")

    vector_store = get_vector_store()

    documents = await vector_store.list_documents(
        workspace=workspace,
        limit=limit,
        offset=offset
    )

    return {
        "workspace": workspace,
        "documents": documents,
        "count": len(documents)
    }


@app.delete("/api/workspaces/{workspace}/documents/{doc_id}")
async def delete_document(workspace: str, doc_id: str):
    """
    Delete a document from workspace.

    Args:
        workspace: Workspace name
        doc_id: Document ID to delete

    Returns:
        Success status
    """
    if not FEATURE_FLAGS.get("rag_enabled", False):
        raise HTTPException(status_code=404, detail="RAG not enabled")

    vector_store = get_vector_store()

    success = await vector_store.delete_document(workspace, doc_id)

    if not success:
        raise HTTPException(status_code=404, detail="Document not found or delete failed")

    return {"success": True, "doc_id": doc_id}


@app.get("/api/workspaces/{workspace}/stats")
async def get_workspace_stats(workspace: str):
    """
    Get statistics for a workspace knowledge base.

    Args:
        workspace: Workspace name

    Returns:
        Workspace statistics
    """
    if not FEATURE_FLAGS.get("rag_enabled", False):
        raise HTTPException(status_code=404, detail="RAG not enabled")

    vector_store = get_vector_store()

    stats = await vector_store.get_collection_stats(workspace)

    return stats


# ============================================================================
# Server Entrypoint
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
