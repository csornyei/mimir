from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from mimir.agent.conversation import conversation_manager
from mimir.db import engine, get_db
from mimir.models import ChatRequest, ChatResponse
from mimir.memory.semantic import SemanticMemory
from mimir.llm.prompt import build_system_prompt
from mimir.llm.client import llm_client
from mimir.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()
    await llm_client.close()


app = FastAPI(lifespan=lifespan)

semantic_memory = SemanticMemory()


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    await conversation_manager.get_or_create_conversation(db, request.conversation_id)

    await conversation_manager.add_message(db, request.conversation_id, "user", request.message)

    memory_content = semantic_memory.read()

    rag_context = ""

    system_prompt = build_system_prompt(
        owner="Máté",
        semantic_memory=memory_content,
        rag_context=rag_context,
    )

    messages = [{"role": "system", "content": system_prompt}] + await conversation_manager.window(db, request.conversation_id, 20)

    logger.info(f"Conversation history:\n{messages}")

    result = await llm_client.complete(messages=messages)

    logger.info(f"LLM response: {result}")

    await conversation_manager.add_message(db, request.conversation_id, "assistant", result)

    return ChatResponse(response=result, conversation_id=request.conversation_id)


@app.get("/health")
async def health():
    return {"status": "ok"}
