from dataclasses import dataclass


@dataclass
class ChatContext:
    semantic_memory: str
    rag_context: str
    episodic_context: str
    tools: list[dict]
