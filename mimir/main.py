import json

from fastapi import FastAPI

from mimir.agent.conversation import ConversationManager
from mimir.models import ChatRequest, ChatResponse
from mimir.memory.semantic import SemanticMemory
from mimir.llm.prompt import build_system_prompt
from mimir.llm.client import llm_client
from mimir.logger import logger

app = FastAPI()

conversation_manager = ConversationManager()
semantic_memory = SemanticMemory()


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    conversation = conversation_manager.get_conversation(request.convesation_id)

    conversation.add_message("user", request.message)

    memory_content = semantic_memory.read()

    rag_context = ""

    system_prompt = build_system_prompt(
        owner="Máté",
        semantic_memory=memory_content,
        rag_context=rag_context,
    )

    messages = [{"role": "system", "content": system_prompt}] + conversation.window(20)

    logger.info(f"Conversation history:\n{messages}")

    result = await llm_client.complete(messages=messages)

    logger.info(f"LLM response: {result}")

    conversation.add_message("assistant", result)

    return ChatResponse(
        response=json.dumps(result), convesation_id=request.convesation_id
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
