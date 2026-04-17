import enum
from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Enum,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mimir.base import Base


# ---------------------------------------------------------------------------
# Conversation / message models
# ---------------------------------------------------------------------------


class ConversationModel(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_active: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    consolidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consolidation_retries: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    messages: Mapped[list["MessageModel"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class MessageModel(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        String, ForeignKey("conversations.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation: Mapped[ConversationModel] = relationship(back_populates="messages")

    __table_args__ = (
        Index("ix_messages_conversation_timestamp", "conversation_id", "timestamp"),
    )


# ---------------------------------------------------------------------------
# Episodic memory model
# ---------------------------------------------------------------------------


class EpisodicMemoryModel(Base):
    __tablename__ = "episodic_memories"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_episodic_memories_embedding",
            "embedding",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_using="hnsw",
            postgresql_with={"m": "16", "ef_construction": "64"},
        ),
    )


# ---------------------------------------------------------------------------
# RAG / document chunk model
# ---------------------------------------------------------------------------


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=True)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_document_chunks_source_path", "source_path"),
        Index("ix_document_chunks_source_type", "source_type"),
        Index(
            "ix_document_chunks_embedding",
            "embedding",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_using="hnsw",
            postgresql_with={"m": "16", "ef_construction": "64"},
        ),
    )


class ActionStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    discussing = "discussing"
    completed = "completed"
    failed = "failed"


class PendingActionModel(Base):
    __tablename__ = "pending_actions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    status: Mapped[ActionStatus] = mapped_column(
        Enum(ActionStatus, name="action_status", create_type=True),
        nullable=False,
        server_default=ActionStatus.pending.value,
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    channel_id: Mapped[str] = mapped_column(String, nullable=False)
    message_ts: Mapped[str] = mapped_column(String, nullable=False)
    thread_ts: Mapped[str | None] = mapped_column(String, nullable=True)
    parent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("pending_actions.id"),
        nullable=True,
    )
    triggered_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    timeout_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# ---------------------------------------------------------------------------
# RSS digest model
# ---------------------------------------------------------------------------


class RssDigestEntry(Base):
    __tablename__ = "rss_digest_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    miniflux_entry_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    feed_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    digest_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window: Mapped[str] = mapped_column(String(10), nullable=False)
    slack_channel_id: Mapped[str] = mapped_column(String, nullable=False)
    slack_message_ts: Mapped[str] = mapped_column(String, nullable=False)
    reaction: Mapped[str | None] = mapped_column(String(20), nullable=True)

    __table_args__ = (
        Index("ix_rss_digest_entries_message_ts", "slack_message_ts"),
    )
