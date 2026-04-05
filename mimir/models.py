from pydantic import BaseModel


class ChatRequest(BaseModel):
    convesation_id: str
    user_id: str
    message: str


class ChatResponse(BaseModel):
    response: str
    convesation_id: str
