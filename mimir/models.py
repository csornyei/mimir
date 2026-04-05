from pydantic import BaseModel


class ChatRequest(BaseModel):
    conversation_id: str
    user_id: str
    message: str


class ChatResponse(BaseModel):
    response: str
    conversation_id: str
