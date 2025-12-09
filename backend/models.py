"""
SQLAlchemy ORM models for Cove database.

Schema includes:
- Conversations: Top-level conversation metadata
- Messages: User and assistant messages within conversations
- StageResults: Detailed results from each stage (1, 2, 3) per model
- ModelInvocations: Cost and performance tracking for every model API call
- ToolCalls: Tracking of tool executions (web search, calculator, etc.)
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from .database import Base


class Conversation(Base):
    """
    Represents a conversation session.
    """
    __tablename__ = "conversations"

    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    title = Column(String, default="New Conversation", nullable=False)
    workspace = Column(String, default="General", nullable=False, index=True)
    metadata_json = Column(JSON, nullable=True)  # Store additional metadata as JSON

    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Conversation(id={self.id}, title={self.title}, workspace={self.workspace})>"


class Message(Base):
    """
    Represents a single message (user or assistant) in a conversation.
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)  # For user messages, raw text. For assistant, JSON-encoded stages
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    stage_results = relationship("StageResult", back_populates="message", cascade="all, delete-orphan")
    tool_calls = relationship("ToolCall", back_populates="message", cascade="all, delete-orphan")

    # Indexes for common queries
    __table_args__ = (
        Index('ix_messages_conversation_created', 'conversation_id', 'created_at'),
    )

    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role}, conversation_id={self.conversation_id})>"


class StageResult(Base):
    """
    Stores detailed results from each stage of the council process.

    For each model invocation in Stage 1, 2, or 3, we store:
    - The model used
    - The response content
    - Tokens consumed
    - Cost incurred
    - Latency in milliseconds
    """
    __tablename__ = "stage_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False, index=True)
    stage_num = Column(Integer, nullable=False)  # 1, 2, or 3
    model = Column(String, nullable=False, index=True)
    response = Column(Text, nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    cost = Column(Float, default=0.0)  # Cost in USD
    latency_ms = Column(Float, default=0.0)  # Latency in milliseconds
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    message = relationship("Message", back_populates="stage_results")

    # Indexes for analytics queries
    __table_args__ = (
        Index('ix_stage_results_model_created', 'model', 'created_at'),
        Index('ix_stage_results_stage_model', 'stage_num', 'model'),
    )

    def __repr__(self):
        return f"<StageResult(id={self.id}, stage={self.stage_num}, model={self.model})>"


class ModelInvocation(Base):
    """
    Tracks every API call to a model for cost and performance analytics.

    This provides a detailed audit trail of all model usage across the system,
    enabling cost dashboards and performance analysis.
    """
    __tablename__ = "model_invocations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    model = Column(String, nullable=False, index=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    cost = Column(Float, default=0.0)  # Cost in USD
    latency_ms = Column(Float, default=0.0)  # Latency in milliseconds
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)  # Store additional context (conversation_id, workspace, etc.)

    # Indexes for dashboard queries
    __table_args__ = (
        Index('ix_invocations_timestamp_model', 'timestamp', 'model'),
        Index('ix_invocations_success', 'success'),
    )

    def __repr__(self):
        return f"<ModelInvocation(id={self.id}, model={self.model}, success={self.success}, cost=${self.cost:.4f})>"


class ToolCall(Base):
    """
    Tracks tool executions (web search, calculator, code execution, etc.)

    Enables analytics on tool usage, success rates, and performance.
    """
    __tablename__ = "tool_calls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=True, index=True)
    tool_name = Column(String, nullable=False, index=True)
    input_data = Column(JSON, nullable=True)  # Tool input parameters
    output_data = Column(JSON, nullable=True)  # Tool output result
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)
    latency_ms = Column(Float, default=0.0)

    # Relationships
    message = relationship("Message", back_populates="tool_calls")

    # Indexes for analytics
    __table_args__ = (
        Index('ix_tool_calls_timestamp_tool', 'timestamp', 'tool_name'),
        Index('ix_tool_calls_success', 'success'),
    )

    def __repr__(self):
        return f"<ToolCall(id={self.id}, tool={self.tool_name}, success={self.success})>"
