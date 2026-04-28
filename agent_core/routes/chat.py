from fastapi import APIRouter, Depends
from opentelemetry import trace
from opentelemetry.trace import StatusCode
import structlog.contextvars
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.agent.tool_schema import tool_schema_registry
from agent_core.agent.tools import tool_loop
from shared.db import get_db
from shared.logger import logger
from agent_core.config import agent_config
from agent_core.agent.conversation import conversation_manager
from shared.schemas import ChatRequest, ChatResponse
from agent_core.memory.semantic import SemanticMemory
from agent_core.memory.episodic import EpisodicMemory
from agent_core.llm.prompt import (
    build_system_prompt,
    format_episodic_context,
    token_estimate,
)
from agent_core.llm.client import llm_client
from agent_core.rag.retrieval import retrieve


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

        memory_content = semantic_memory.read()

        rag_chunks_found = 0
        with _tracer.start_as_current_span("chat.rag_retrieval") as rag_span:
            try:
                rag_result = await retrieve(request.message, db)

                rag_result_sorted = sorted(
                    rag_result, key=lambda r: r[1].get("score", 0), reverse=True
                )
                context_sections: list[str] = []
                rag_tokens_used = 0
                for content, metadata in rag_result_sorted:
                    chunk_tokens = token_estimate(content)
                    if rag_tokens_used + chunk_tokens > agent_config.rag_max_tokens:
                        logger.warning(
                            "rag_chunk_dropped",
                            score="N/A"
                            if metadata.get("score") is None
                            else round(metadata.get("score", 0), 4),
                            reason="rag_budget_exceeded",
                        )
                        continue
                    logger.debug(
                        "rag_chunk_retrieved",
                        **metadata,
                    )
                    source = metadata.get("file_name", "")
                    header = metadata.get("header", "")
                    page = metadata.get("page", "")
                    label = (
                        f"{source} {header} {f'(page {page})' if page else ''}".strip()
                    )
                    context_sections.append(f"{label}\n{content}")
                    rag_tokens_used += chunk_tokens
                    rag_chunks_found += 1

                rag_context = "\n\n---\n\n".join(context_sections)
                rag_span.set_attribute("rag.chunks_found", rag_chunks_found)
                rag_span.set_attribute("rag.tokens_used", rag_tokens_used)
            except Exception as e:
                logger.error(
                    "rag_retrieval_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    query_length=len(request.message),
                    exc_info=True,
                )
                rag_span.set_status(StatusCode.ERROR, str(e))
                rag_context = "Error while retrieving relevant information."

        with _tracer.start_as_current_span("chat.episodic_retrieval") as ep_span:
            try:
                episodic_mem = EpisodicMemory(db)
                episodic_memories = await episodic_mem.retrieve(
                    request.message, k=agent_config.episodic_retrieval_k
                )
                episodic_context = format_episodic_context(episodic_memories)
                ep_span.set_attribute("episodic.memories_found", len(episodic_memories))
                logger.debug("episodic_retrieval", count=len(episodic_memories))
            except Exception as e:
                logger.error(
                    "episodic_retrieval_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    query_length=len(request.message),
                    exc_info=True,
                )
                ep_span.set_status(StatusCode.ERROR, str(e))
                episodic_context = ""

        tools: list[dict] = []
        with _tracer.start_as_current_span("chat.tool_schema_fetch") as tools_span:
            try:
                tools = await tool_schema_registry.get_tools()
                tools_span.set_attribute("tools.count", len(tools))
                logger.debug("fetched_tools", count=len(tools))
            except Exception as e:
                logger.warning(
                    "failed_to_fetch_tools",
                    error=str(e),
                    error_type=type(e).__name__,
                    fallback="proceeding_without_tools",
                    exc_info=True,
                )
                tools_span.set_status(StatusCode.ERROR, str(e))
                tools = []

        with _tracer.start_as_current_span("chat.prompt_assembly") as prompt_span:
            system_prompt = build_system_prompt(
                owner=agent_config.owner_name,
                semantic_memory=memory_content,
                episodic_context=episodic_context,
                rag_context=rag_context,
                context_window=agent_config.llm_context_window,
                tools=tools,
            )

            system_tokens = token_estimate(system_prompt)
            budget = (
                agent_config.llm_context_window
                - agent_config.llm_max_tokens
                - 256
                - system_tokens
            )
            n = budget // 200
            n = max(
                agent_config.conversation_window_min,
                min(agent_config.conversation_window_max, n),
            )
            if n < agent_config.conversation_window_max:
                logger.warning("conversation_window_reduced", n=n, budget=budget)

            conversation_messages = await conversation_manager.window(
                db, request.conversation_id, n
            )
            prompt_span.set_attribute("prompt.system_tokens", system_tokens)
            prompt_span.set_attribute("prompt.window_size", n)

        messages = [
            {"role": "system", "content": system_prompt}
        ] + conversation_messages

        system_prompt_reduced = build_system_prompt(
            owner=agent_config.owner_name,
            semantic_memory=memory_content,
            context_window=agent_config.llm_context_window,
            tools=tools,
        )
        system_prompt_minimal = build_system_prompt(
            owner=agent_config.owner_name,
            semantic_memory="",
            context_window=agent_config.llm_context_window,
            tools=tools,
        )
        messages_reduced = [
            {"role": "system", "content": system_prompt_reduced}
        ] + conversation_messages[-5:]
        messages_minimal = [
            {"role": "system", "content": system_prompt_minimal}
        ] + conversation_messages[-agent_config.conversation_window_min :]

        if tools:
            final_response = await tool_loop.run_tool_loop(
                messages=messages,
                tools=tools,
                max_steps=agent_config.tool_max_steps,
                triggered_by=f"user:{request.user_id}",
            )
        else:
            response = await llm_client.complete(
                messages=messages,
                tools=None,
                fallbacks=[messages_reduced, messages_minimal],
            )
            final_response = response["content"]

        await conversation_manager.add_message(
            db, request.conversation_id, "assistant", final_response
        )

        return ChatResponse(
            response=final_response, conversation_id=request.conversation_id
        )
