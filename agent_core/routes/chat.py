from fastapi import APIRouter, Depends
from opentelemetry import trace
import structlog.contextvars
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.agent.context import ChatContext
from agent_core.agent.conversation import conversation_manager
from agent_core.agent.llm_dispatch import run_llm
from agent_core.agent.tool_schema import tool_schema_registry
from agent_core.config import agent_config
from agent_core.llm.messages import build_messages
from agent_core.llm.prompt import format_episodic_context
from agent_core.memory.episodic import EpisodicMemory
from agent_core.memory.semantic import SemanticMemory
from agent_core.rag.context import retrieve_rag_context
from shared.db import get_db
from shared.logger import logger
from shared.schemas import ChatRequest, ChatResponse

router = APIRouter()

semantic_memory = SemanticMemory()
_tracer = trace.get_tracer("mimir.routes.chat")


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        conversation_id=request.conversation_id,
        user_id=request.user_id,
    )

    with _tracer.start_as_current_span("chat.request") as span:
        span.set_attribute("chat.conversation_id", request.conversation_id)
        span.set_attribute("chat.user_id", request.user_id)
        span.set_attribute("chat.message_length", len(request.message))

        await conversation_manager.get_or_create_conversation(
            db, request.conversation_id
        )
        await conversation_manager.add_message(
            db, request.conversation_id, "user", request.message
        )

        # Each step is explicit so the future WS handler can emit progress between them
        semantic_memory_content = semantic_memory.read()
        rag_context, _ = await retrieve_rag_context(
            request.message, db, agent_config.rag_max_tokens
        )
        episodic_context = await EpisodicMemory(db).retrieve(
            request.message, k=agent_config.episodic_retrieval_k
        )

        episodic_context_formatted = format_episodic_context(episodic_context)

        try:
            tools = await tool_schema_registry.get_tools()
            logger.debug("fetched_tools", count=len(tools))
        except Exception as e:
            logger.warning(
                "failed_to_fetch_tools",
                error=str(e),
                error_type=type(e).__name__,
                fallback="proceeding_without_tools",
                exc_info=True,
            )
            tools = []

        context = ChatContext(
            semantic_memory=semantic_memory_content,
            rag_context=rag_context,
            episodic_context=episodic_context_formatted,
            tools=tools,
        )

        bundle = await build_messages(
            context, request.conversation_id, db, agent_config
        )
        response = await run_llm(
            bundle, context.tools, triggered_by=f"user:{request.user_id}"
        )

        await conversation_manager.add_message(
            db, request.conversation_id, "assistant", response
        )
        return ChatResponse(response=response, conversation_id=request.conversation_id)
