from opentelemetry import trace

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
from agent_core.ws.sender import WSSender
from shared.db import get_session
from shared.logger import logger
from shared.schemas import WSChatRequest

_tracer = trace.get_tracer("mimir.ws.chat")
_semantic_memory = SemanticMemory()


async def handle_chat(sender: WSSender, data: dict) -> None:
    with _tracer.start_as_current_span("ws.chat") as span:
        try:
            req = WSChatRequest.model_validate(data)
        except Exception as e:
            await sender.send(
                {
                    "event_type": "error",
                    "request_id": data.get("request_id"),
                    "error": f"Invalid request: {e}",
                }
            )
            return

        span.set_attribute("chat.conversation_id", req.conversation_id)
        span.set_attribute("chat.user_id", req.user_id)
        span.set_attribute("chat.verbose", req.verbose)

        await sender.send(
            {
                "event_type": "chat_ack",
                "request_id": req.request_id,
                "conversation_id": req.conversation_id,
            }
        )

        try:
            async with get_session() as db:
                await conversation_manager.get_or_create_conversation(
                    db, req.conversation_id
                )
                await conversation_manager.add_message(
                    db, req.conversation_id, "user", req.message
                )

            if req.verbose:
                await sender.send(
                    {
                        "event_type": "chat_thinking",
                        "step": "memory",
                        "request_id": req.request_id,
                    }
                )

            semantic_memory_content = _semantic_memory.read()

            async with get_session() as db:
                rag_context, rag_chunks_used = await retrieve_rag_context(
                    req.message, db, agent_config.rag_max_tokens
                )
                episodic_memories = await EpisodicMemory(db).retrieve(
                    req.message, k=agent_config.episodic_retrieval_k
                )

            episodic_context = format_episodic_context(episodic_memories)

            if req.verbose:
                await sender.send(
                    {
                        "event_type": "chat_thinking",
                        "step": "memory_done",
                        "request_id": req.request_id,
                        "rag_chunks_used": rag_chunks_used,
                        "episodic_count": len(episodic_memories),
                    }
                )

            if req.verbose:
                await sender.send(
                    {
                        "event_type": "chat_thinking",
                        "step": "tools",
                        "request_id": req.request_id,
                    }
                )

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
                episodic_context=episodic_context,
                tools=tools,
            )

            async with get_session() as db:
                bundle = await build_messages(
                    context, req.conversation_id, db, agent_config
                )

            on_tool_call = (
                _make_tool_callback(sender, req.request_id) if req.verbose else None
            )

            response = await run_llm(
                bundle,
                context.tools,
                triggered_by=f"user:{req.user_id}",
                on_tool_call=on_tool_call,
            )

            async with get_session() as db:
                await conversation_manager.add_message(
                    db, req.conversation_id, "assistant", response
                )

            span.set_attribute("chat.response_length", len(response))
            await sender.send(
                {
                    "event_type": "chat_response",
                    "request_id": req.request_id,
                    "conversation_id": req.conversation_id,
                    "response": response,
                }
            )

        except Exception as e:
            logger.error(
                "ws_chat_handler_error",
                conversation_id=req.conversation_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            span.record_exception(e)
            await sender.send(
                {
                    "event_type": "error",
                    "request_id": req.request_id,
                    "error": str(e),
                }
            )


def _make_tool_callback(sender: WSSender, request_id: str | None):
    async def on_tool_call(tool_name: str, args: dict, result: dict) -> None:
        await sender.send(
            {
                "event_type": "chat_tool_call",
                "request_id": request_id,
                "tool": tool_name,
                "args": args,
                "result": result,
            }
        )

    return on_tool_call
