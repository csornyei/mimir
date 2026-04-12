from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ChatRequest(BaseModel):
    conversation_id: str
    user_id: str
    message: str


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
    action_type: str
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
    action_type: str
    payload: dict
    channel_id: str
    message_ts: str
    triggered_by: str
    timeout_at: datetime | None = None
    parent_id: UUID | None = None


class PendingActionPatch(BaseModel):
    status: str
