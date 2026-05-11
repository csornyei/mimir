import time
from uuid import uuid4

from opentelemetry import trace

from agent_core.agent.context import ChatContext
from agent_core.agent.conversation import conversation_manager
from agent_core.agent.events import (
    AgentEvent,
    ApprovalRequired,
    ResponseToken,
    ThinkingToken,
    ToolDone,
    ToolPending,
    ToolStart,
)
from agent_core.agent.llm_dispatch import run_llm
from agent_core.agent.tool_schema import tool_schema_registry
from agent_core.agent.types import RunContext
from agent_core.config import agent_config
from agent_core.llm.messages import build_messages
from agent_core.llm.params import llm_params_from_settings
from agent_core.llm.prompt import format_episodic_context
from agent_core.memory.episodic import EpisodicMemory
from agent_core.memory.semantic import SemanticMemory
from agent_core.rag.context import retrieve_rag_context
from agent_core.ws import registry as ws_registry
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
                    "type": "error",
                    "request_id": data.get("request_id"),
                    "message": f"Invalid request: {e}",
                }
            )
            return

        span.set_attribute("chat.conversation_id", str(req.conversation_id))
        span.set_attribute("chat.user_id", req.user_id)

        settings = req.settings

        # Validate thinking settings consistency before dispatching
        if settings and settings.enable_thinking and settings.thinking_budget == 0:
            await sender.send(
                {
                    "type": "error",
                    "request_id": data.get("request_id"),
                    "message": "Invalid settings: enable_thinking=True but thinking_budget=0. "
                    "Set thinking_budget to null (unlimited) or a positive integer, "
                    "or set enable_thinking=False.",
                }
            )
            return
        if (
            settings
            and not settings.enable_thinking
            and settings.thinking_budget
            and settings.thinking_budget > 0
        ):
            await sender.send(
                {
                    "type": "error",
                    "request_id": data.get("request_id"),
                    "message": "Invalid settings: enable_thinking=False but thinking_budget is set. "
                    "Set thinking_budget to 0 or null when thinking is disabled.",
                }
            )
            return

        params = llm_params_from_settings(settings)

        t_start = time.monotonic()
        _conv_id: str | None = None

        try:
            # Ensure conversation exists; create if null
            async with get_session() as db:
                if req.conversation_id:
                    await conversation_manager.get_or_create_conversation(
                        db, req.conversation_id
                    )
                    conversation_id = req.conversation_id
                else:
                    conversation_id = f"web|{uuid4()}"
                    await conversation_manager.get_or_create_conversation(
                        db, conversation_id
                    )
                await conversation_manager.add_message(
                    db, conversation_id, "user", req.message
                )

            span.set_attribute("chat.resolved_conversation_id", conversation_id)
            _conv_id = conversation_id
            ws_registry.register(conversation_id, sender)

            try:
                semantic_memory_content = _semantic_memory.read()

                async with get_session() as db:
                    rag_context, _chunks_used, rag_sources = await retrieve_rag_context(
                        req.message, db, agent_config.rag_max_tokens, rag_params=req.rag
                    )
                    episodic_memories_raw = await EpisodicMemory(db).retrieve(
                        req.message, k=agent_config.episodic_retrieval_k
                    )

                episodic_context = format_episodic_context(episodic_memories_raw)

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
                        context, conversation_id, db, agent_config
                    )

                run_ctx = RunContext(
                    triggered_by=f"user:{req.user_id}",
                    conversation_id=conversation_id,
                )

                # ── Single typed event callback ────────────────────────────────

                _did_stream = False
                _did_think = False

                async def on_event(event: AgentEvent) -> None:
                    nonlocal _did_stream, _did_think
                    match event:
                        case ResponseToken(content=c):
                            _did_stream = True
                            await ws_registry.send(
                                conversation_id,
                                {
                                    "type": "response",
                                    "request_id": req.request_id,
                                    "conversation_id": conversation_id,
                                    "content": c,
                                },
                            )
                        case ThinkingToken(content=c):
                            _did_think = True
                            await ws_registry.send(
                                conversation_id,
                                {"type": "thinking", "content": c},
                            )
                        case ToolPending(name=n, call_id=cid):
                            await ws_registry.send(
                                conversation_id,
                                {
                                    "type": "tool_pending",
                                    "request_id": req.request_id,
                                    "name": n,
                                    "call_id": cid,
                                },
                            )
                        case ToolStart(name=n, call_id=cid, arguments=a):
                            await ws_registry.send(
                                conversation_id,
                                {
                                    "type": "tool_call",
                                    "request_id": req.request_id,
                                    "name": n,
                                    "arguments": a,
                                    "call_id": cid,
                                },
                            )
                        case ToolDone(name=n, call_id=cid, result=r):
                            await ws_registry.send(
                                conversation_id,
                                {
                                    "type": "tool_result",
                                    "request_id": req.request_id,
                                    "name": n,
                                    "result": r,
                                    "call_id": cid,
                                },
                            )
                        case ApprovalRequired(action_id=aid, tool_name=tn, arguments=a):
                            await ws_registry.send(
                                conversation_id,
                                {
                                    "type": "approval_required",
                                    "request_id": req.request_id,
                                    "action_id": aid,
                                    "tool_name": tn,
                                    "arguments": a,
                                },
                            )

                # ── Run LLM ───────────────────────────────────────────────────

                result = await run_llm(
                    bundle,
                    context.tools,
                    context=run_ctx,
                    params=params,
                    on_event=on_event,
                )

                async with get_session() as db:
                    await conversation_manager.add_message(
                        db, conversation_id, "assistant", result.content
                    )

                latency_ms = int((time.monotonic() - t_start) * 1000)
                span.set_attribute("chat.response_length", len(result.content))
                span.set_attribute("chat.latency_ms", latency_ms)

                # ── thinking event (non-streaming path only) ──────────────────
                if not _did_think and result.thinking:
                    await ws_registry.send(
                        conversation_id,
                        {"type": "thinking", "content": result.thinking},
                    )

                # ── response event (non-streaming path only) ──────────────────
                if not _did_stream:
                    await ws_registry.send(
                        conversation_id,
                        {
                            "type": "response",
                            "request_id": req.request_id,
                            "conversation_id": conversation_id,
                            "content": result.content,
                        },
                    )

                # ── done event with metadata ──────────────────────────────────
                thinking_tokens = len(result.thinking) // 4 if result.thinking else 0
                episodic_for_metadata = [
                    {
                        "summary": m.get("summary", ""),
                        "started_at": m["started_at"].isoformat()
                        if m.get("started_at")
                        else None,
                        "similarity_score": float(m.get("score", 0.0)),
                    }
                    for m in episodic_memories_raw
                ]

                await ws_registry.send(
                    conversation_id,
                    {
                        "type": "done",
                        "request_id": req.request_id,
                        "metadata": {
                            "thinking_tokens": thinking_tokens,
                            "response_tokens": result.usage.get("completion_tokens", 0),
                            "prompt_tokens": result.usage.get("prompt_tokens", 0),
                            "latency_ms": latency_ms,
                            "rag_sources": rag_sources,
                            "episodic_memories": episodic_for_metadata,
                        },
                    },
                )

            finally:
                ws_registry.unregister(conversation_id)

        except Exception as e:
            logger.error(
                "ws_chat_handler_error",
                conversation_id=req.conversation_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            span.record_exception(e)
            err_payload = {
                "type": "error",
                "request_id": req.request_id,
                "message": str(e),
            }
            if _conv_id:
                await ws_registry.send(_conv_id, err_payload)
            else:
                await sender.send(err_payload)
