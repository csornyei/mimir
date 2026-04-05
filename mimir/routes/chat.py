from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from mimir.db import get_db
from mimir.logger import logger
from mimir.config import config
from mimir.agent.conversation import conversation_manager
from mimir.models import ChatRequest, ChatResponse
from mimir.memory.semantic import SemanticMemory
from mimir.llm.prompt import build_system_prompt
from mimir.llm.client import llm_client
from mimir.rag.retrieval import retrieve


router = APIRouter()

semantic_memory = SemanticMemory()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    await conversation_manager.get_or_create_conversation(db, request.conversation_id)

    await conversation_manager.add_message(
        db, request.conversation_id, "user", request.message
    )

    memory_content = semantic_memory.read()

    rag_chunks = await retrieve(request.message, db)
    rag_context = "\n\n---\n\n".join(rag_chunks)

    system_prompt = build_system_prompt(
        owner=config.owner_name,
        semantic_memory=memory_content,
        rag_context=rag_context,
    )

    messages = [
        {"role": "system", "content": system_prompt}
    ] + await conversation_manager.window(db, request.conversation_id, 20)

    logger.info(f"Conversation history:\n{messages}")

    result = await llm_client.complete(messages=messages)

    logger.info(f"LLM response: {result}")

    await conversation_manager.add_message(
        db, request.conversation_id, "assistant", result
    )

    return ChatResponse(response=result, conversation_id=request.conversation_id)
