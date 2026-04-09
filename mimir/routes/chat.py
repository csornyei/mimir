from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from mimir.db import get_db
from mimir.logger import logger
from mimir.config import config
from mimir.agent.conversation import conversation_manager
from mimir.schemas import ChatRequest, ChatResponse
from mimir.memory.semantic import SemanticMemory
from mimir.memory.episodic import EpisodicMemory
from mimir.llm.prompt import (
    build_system_prompt,
    format_episodic_context,
    token_estimate,
)
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

    # --- RAG retrieval with budget enforcement ---
    try:
        rag_result = await retrieve(request.message, db)

        # Sort highest-score first; drop whole chunks that would exceed the cap.
        rag_result_sorted = sorted(
            rag_result, key=lambda r: r[1].get("score", 0), reverse=True
        )
        context_sections: list[str] = []
        rag_tokens_used = 0
        for content, metadata in rag_result_sorted:
            chunk_tokens = token_estimate(content)
            if rag_tokens_used + chunk_tokens > config.rag_max_tokens:
                logger.warning(
                    "rag_chunk_dropped",
                    score=metadata.get("score"),
                    reason="rag_budget_exceeded",
                )
                continue
            logger.info(
                f"Retrieved chunk with score {metadata.get('score'):.4f}", **metadata
            )
            source = metadata.get("file_name", "")
            header = metadata.get("header", "")
            page = metadata.get("page", "")
            label = f"{source} {header} {f'(page {page})' if page else ''}".strip()
            context_sections.append(f"{label}\n{content}")
            rag_tokens_used += chunk_tokens

        rag_context = "\n\n---\n\n".join(context_sections)
    except Exception as e:
        logger.error(f"Error during retrieval: {e}")
        rag_context = "Error while retrieving relevant information."

    # --- Episodic memory retrieval ---
    try:
        episodic_mem = EpisodicMemory(db)
        episodic_memories = await episodic_mem.retrieve(
            request.message, k=config.episodic_retrieval_k
        )
        episodic_context = format_episodic_context(episodic_memories)
        logger.info("episodic_retrieval", count=len(episodic_memories))
    except Exception as e:
        logger.error(f"Error during episodic retrieval: {e}")
        episodic_context = ""

    # --- Assemble system prompt (trims semantic memory + episodic internally) ---
    system_prompt = build_system_prompt(
        owner=config.owner_name,
        semantic_memory=memory_content,
        episodic_context=episodic_context,
        rag_context=rag_context,
        context_window=config.llm_context_window,
    )

    # --- Dynamic conversation window ---
    system_tokens = token_estimate(system_prompt)
    budget = config.llm_context_window - config.llm_max_tokens - 256 - system_tokens
    n = budget // 200  # rough estimate: ~200 tokens per message
    n = max(config.conversation_window_min, min(config.conversation_window_max, n))
    if n < config.conversation_window_max:
        logger.warning("conversation_window_reduced", n=n, budget=budget)

    conversation_messages = await conversation_manager.window(
        db, request.conversation_id, n
    )
    messages = [{"role": "system", "content": system_prompt}] + conversation_messages

    logger.info(f"Conversation history:\n{messages}")

    # --- Pre-build fallback message lists for the 413 safety net ---
    system_prompt_reduced = build_system_prompt(
        owner=config.owner_name,
        semantic_memory=memory_content,
        context_window=config.llm_context_window,
    )
    system_prompt_minimal = build_system_prompt(
        owner=config.owner_name,
        semantic_memory="",
        context_window=config.llm_context_window,
    )
    messages_reduced = [
        {"role": "system", "content": system_prompt_reduced}
    ] + conversation_messages[-5:]
    messages_minimal = [
        {"role": "system", "content": system_prompt_minimal}
    ] + conversation_messages[-config.conversation_window_min :]

    result = await llm_client.complete(
        messages=messages,
        fallbacks=[messages_reduced, messages_minimal],
    )

    logger.info(f"LLM response: {result}")

    await conversation_manager.add_message(
        db, request.conversation_id, "assistant", result
    )

    return ChatResponse(response=result, conversation_id=request.conversation_id)
