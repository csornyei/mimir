from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ChatRequest(BaseModel):
    conversation_id: str
    user_id: str
    message: str
    message_role: str = "user"


class ChatResponse(BaseModel):
    response: str
    conversation_id: str


class ConversationSummary(BaseModel):
    id: str
    created_at: datetime
    last_active: datetime


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    timestamp: datetime


class ConversationDetail(BaseModel):
    id: str
    created_at: datetime
    last_active: datetime
    messages: list[MessageResponse]
    total: int
    limit: int
    offset: int


class PendingActionResponse(BaseModel):
    id: UUID
    status: str
    payload: dict
    channel_id: str
    message_ts: str
    thread_ts: str | None
    parent_id: UUID | None
    triggered_by: str
    created_at: datetime
    resolved_at: datetime | None
    timeout_at: datetime | None

    model_config = {"from_attributes": True}


class PendingActionCreate(BaseModel):
    payload: dict
    channel_id: str
    message_ts: str
    triggered_by: str
    timeout_at: datetime | None = None
    parent_id: UUID | None = None


class PendingActionPatch(BaseModel):
    status: str


# ── LLM settings sent with every chat WS event ──────────────────────────────


class LLMSettings(BaseModel):
    mode: Literal["precise", "balanced", "creative", "fast"] = "balanced"
    model: str | None = None  # overrides config default when set
    enable_thinking: bool = True
    thinking_budget: int | None = (
        2000  # null = unlimited; 0 = disabled; irrelevant if enable_thinking=False
    )
    temperature: float = 0.5
    top_p: float = 0.9
    min_p: float = 0.05
    repetition_penalty: float = 1.0
    max_tokens: int = 4096


# ── WebSocket ────────────────────────────────────────────────────────────────


class WSChatRequest(BaseModel):
    type: str  # must be "chat"
    request_id: str | None = None
    conversation_id: str | None = None  # null → backend creates a new conversation
    user_id: str = "web"
    message: str
    settings: LLMSettings | None = None


# ── Approval wrappers ────────────────────────────────────────────────────────


class ApproveRequest(BaseModel):
    edited_arguments: dict | None = None


# ── Memory ───────────────────────────────────────────────────────────────────


class MemoryResponse(BaseModel):
    content: str


class MemoryWriteRequest(BaseModel):
    content: str


class MemoryWriteResponse(BaseModel):
    status: str = "ok"


# ── Digest ───────────────────────────────────────────────────────────────────


class DigestArticle(BaseModel):
    id: int
    title: str
    url: str
    feed_name: str | None
    category: str | None
    window: str
    digest_run_at: datetime

    model_config = {"from_attributes": True}


class DigestRun(BaseModel):
    run_at: datetime
    window: str
    article_count: int


class DigestFeedbackRequest(BaseModel):
    article_id: int
    rating: Literal["up", "down"]


# ── Brief ─────────────────────────────────────────────────────────────────────


class BriefSummary(BaseModel):
    id: str
    date: str
    created_at: datetime


class BriefDetail(BaseModel):
    id: str
    date: str
    created_at: datetime
    messages: list[MessageResponse]


# ── Models & Presets ──────────────────────────────────────────────────────────


class OllamaModel(BaseModel):
    name: str
    size: int | None = None
    modified_at: str | None = None
    is_loaded: bool = False


class ModelsResponse(BaseModel):
    models: list[OllamaModel]
    default_model: str


class LLMPreset(BaseModel):
    name: str
    label: str
    enable_thinking: bool
    thinking_budget: int | None
    temperature: float
    top_p: float
    min_p: float
    repetition_penalty: float
    max_tokens: int


class PresetsResponse(BaseModel):
    presets: list[LLMPreset]
    default_preset: str
