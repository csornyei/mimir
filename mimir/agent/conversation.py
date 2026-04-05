from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict


@dataclass
class Message:
    role: str  # e.g., "user", "assistant", "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Conversation:
    id: str
    messages: List[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)

    def add_message(self, role: str, content: str, **kwargs):
        self.messages.append(Message(role=role, content=content, **kwargs))
        self.last_active = datetime.now()

    def window(self, n: int) -> List[Message]:
        return [{"role": m.role, "content": m.content} for m in self.messages[-n:]]


class ConversationManager:
    def __init__(self):
        self._conversations: Dict[str, Conversation] = {}

    def get_conversation(self, conversation_id: str) -> Conversation:
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = Conversation(id=conversation_id)
        return self._conversations[conversation_id]
