"""Database-based storage for conversations."""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from .database import get_db
from .models import Conversation, Message, StageResult


async def create_conversation(
    conversation_id: str,
    workspace: str = "General"
) -> Dict[str, Any]:
    """
    Create a new conversation.

    Args:
        conversation_id: Unique identifier for the conversation
        workspace: Workspace context (Wooster, Bellcourt, etc.)

    Returns:
        New conversation dict
    """
    async with get_db() as db:
        conversation = Conversation(
            id=conversation_id,
            created_at=datetime.utcnow(),
            title="New Conversation",
            workspace=workspace,
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

        return {
            "id": conversation.id,
            "created_at": conversation.created_at.isoformat(),
            "title": conversation.title,
            "workspace": conversation.workspace,
            "messages": []
        }


async def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a conversation from storage.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        Conversation dict or None if not found
    """
    async with get_db() as db:
        # Load conversation with messages eagerly
        result = await db.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.messages))
        )
        conversation = result.scalar_one_or_none()

        if conversation is None:
            return None

        # Convert to dict format
        messages = []
        for msg in sorted(conversation.messages, key=lambda m: m.created_at):
            if msg.role == "user":
                messages.append({
                    "role": "user",
                    "content": msg.content
                })
            else:
                # Assistant message - parse JSON content
                try:
                    stage_data = json.loads(msg.content)
                    messages.append({
                        "role": "assistant",
                        "stage1": stage_data.get("stage1", []),
                        "stage2": stage_data.get("stage2", []),
                        "stage3": stage_data.get("stage3", {})
                    })
                except json.JSONDecodeError:
                    # Fallback for malformed data
                    messages.append({
                        "role": "assistant",
                        "stage1": [],
                        "stage2": [],
                        "stage3": {"model": "error", "response": msg.content}
                    })

        return {
            "id": conversation.id,
            "created_at": conversation.created_at.isoformat(),
            "title": conversation.title,
            "workspace": conversation.workspace,
            "messages": messages
        }


async def save_conversation(conversation: Dict[str, Any]):
    """
    Save a conversation to storage.

    Note: This is a legacy function for backwards compatibility.
    In the new system, conversations are saved incrementally via
    add_user_message() and add_assistant_message().

    Args:
        conversation: Conversation dict to save
    """
    # This is mostly a no-op now since we save incrementally
    # But we can update the title if changed
    async with get_db() as db:
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation['id'])
        )
        conv = result.scalar_one_or_none()

        if conv:
            conv.title = conversation.get('title', conv.title)
            await db.commit()


async def list_conversations() -> List[Dict[str, Any]]:
    """
    List all conversations (metadata only).

    Returns:
        List of conversation metadata dicts, sorted by creation time (newest first)
    """
    async with get_db() as db:
        # Query conversations with message count
        result = await db.execute(
            select(
                Conversation.id,
                Conversation.created_at,
                Conversation.title,
                Conversation.workspace,
                func.count(Message.id).label('message_count')
            )
            .outerjoin(Message, Conversation.id == Message.conversation_id)
            .group_by(Conversation.id, Conversation.created_at, Conversation.title, Conversation.workspace)
            .order_by(desc(Conversation.created_at))
        )

        conversations = []
        for row in result.all():
            conversations.append({
                "id": row.id,
                "created_at": row.created_at.isoformat(),
                "title": row.title,
                "workspace": row.workspace,
                "message_count": row.message_count
            })

        return conversations


async def add_user_message(conversation_id: str, content: str):
    """
    Add a user message to a conversation.

    Args:
        conversation_id: Conversation identifier
        content: User message content
    """
    async with get_db() as db:
        # Check if conversation exists
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()

        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Create user message
        message = Message(
            conversation_id=conversation_id,
            role="user",
            content=content,
            created_at=datetime.utcnow()
        )
        db.add(message)
        await db.commit()


async def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any]
):
    """
    Add an assistant message with all 3 stages to a conversation.

    Args:
        conversation_id: Conversation identifier
        stage1: List of individual model responses
        stage2: List of model rankings
        stage3: Final synthesized response
    """
    async with get_db() as db:
        # Check if conversation exists
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()

        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Serialize stage data as JSON
        stage_data = {
            "stage1": stage1,
            "stage2": stage2,
            "stage3": stage3
        }

        # Create assistant message
        message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=json.dumps(stage_data),
            created_at=datetime.utcnow()
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)

        # Optionally create StageResult records for detailed analytics
        # (This is for future Phase 3 analytics - commented out for now)
        # for stage1_result in stage1:
        #     stage_result = StageResult(
        #         message_id=message.id,
        #         stage_num=1,
        #         model=stage1_result['model'],
        #         response=stage1_result['response'],
        #         # tokens and cost would come from openrouter response
        #     )
        #     db.add(stage_result)


async def update_conversation_title(conversation_id: str, title: str):
    """
    Update the title of a conversation.

    Args:
        conversation_id: Conversation identifier
        title: New title for the conversation
    """
    async with get_db() as db:
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()

        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        conversation.title = title
        await db.commit()


# ============================================================================
# New functions for analytics and stats
# ============================================================================

async def get_conversation_stats(conversation_id: str) -> Dict[str, Any]:
    """
    Get statistics for a specific conversation.

    Args:
        conversation_id: Conversation identifier

    Returns:
        Dict with stats (message_count, models_used, etc.)
    """
    async with get_db() as db:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.messages))
        )
        conversation = result.scalar_one_or_none()

        if conversation is None:
            return {}

        message_count = len(conversation.messages)
        user_messages = sum(1 for m in conversation.messages if m.role == "user")
        assistant_messages = sum(1 for m in conversation.messages if m.role == "assistant")

        return {
            "conversation_id": conversation_id,
            "message_count": message_count,
            "user_messages": user_messages,
            "assistant_messages": assistant_messages,
            "created_at": conversation.created_at.isoformat(),
            "workspace": conversation.workspace
        }


async def get_recent_conversations(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get the most recent conversations.

    Args:
        limit: Maximum number of conversations to return

    Returns:
        List of conversation dicts
    """
    async with get_db() as db:
        result = await db.execute(
            select(Conversation)
            .order_by(desc(Conversation.created_at))
            .limit(limit)
        )
        conversations = result.scalars().all()

        return [
            {
                "id": conv.id,
                "created_at": conv.created_at.isoformat(),
                "title": conv.title,
                "workspace": conv.workspace
            }
            for conv in conversations
        ]


async def delete_conversation(conversation_id: str) -> bool:
    """
    Delete a conversation and all its messages.

    Args:
        conversation_id: Conversation identifier

    Returns:
        True if deleted, False if not found
    """
    async with get_db() as db:
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()

        if conversation is None:
            return False

        # Delete the conversation (cascade will delete messages)
        # Note: db.delete() is synchronous in SQLAlchemy async sessions
        db.delete(conversation)
        await db.commit()
        return True
