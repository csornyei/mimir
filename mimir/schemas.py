from datetime import datetime

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
