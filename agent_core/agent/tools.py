import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from opentelemetry import trace
from opentelemetry.trace import StatusCode

from agent_core.agent.dispatcher import ToolDispatcher
from agent_core.agent.events import (
    AgentEvent,
    ApprovalRequired,
    ResponseToken,
    ThinkingToken,
    ToolDone,
    ToolPending,
    ToolStart,
)
from agent_core.agent.types import AgentResult, RunContext
from agent_core.config import agent_config
from agent_core.llm.client import llm_client
from agent_core.llm.params import LLMParams
from shared.db import get_session
from shared.logger import logger

_tracer = trace.get_tracer("mimir.agent.tools")

_DEFAULT_CONTEXT = RunContext(triggered_by="agent")


def _is_write_tool(tool_name: str, tools: list[dict]) -> bool:
    for t in tools:
        if t.get("function", {}).get("name") == tool_name:
            return t.get("destructive", False)
    return False


async def _safe_emit(
    on_event: Callable[[AgentEvent], Awaitable[None]],
    event: AgentEvent,
    label: str,
    tool_name: str,
) -> None:
    try:
        await on_event(event)
    except Exception as cb_err:
        logger.warning(
            "tool_callback_error",
            callback=label,
            tool_name=tool_name,
            error=str(cb_err),
        )


@dataclass
class _EventCallbacks:
    """Bundles all event emission callbacks derived from a single on_event callable."""

    on_event: Callable[[AgentEvent], Awaitable[None]]
    on_token: Callable[[str], Awaitable[None]]
    on_thinking_token: Callable[[str], Awaitable[None]]
    on_tool_pending: Callable[[str, str], Awaitable[None]]


class ToolLoop(ToolDispatcher):
    """Agentic tool loop: drives LLM ↔ MCP tool calls until a final response."""

    def _build_event_callbacks(
        self, on_event: Callable[[AgentEvent], Awaitable[None]] | None
    ) -> _EventCallbacks | None:
        if on_event is None:
            return None

        async def _on_token(delta: str) -> None:
            await on_event(ResponseToken(content=delta))

        async def _on_thinking_token(delta: str) -> None:
            await on_event(ThinkingToken(content=delta))

        async def _on_tool_pending(name: str, call_id: str) -> None:
            await on_event(ToolPending(name=name, call_id=call_id))

        return _EventCallbacks(
            on_event=on_event,
            on_token=_on_token,
            on_thinking_token=_on_thinking_token,
            on_tool_pending=_on_tool_pending,
        )

    async def _call_llm(
        self,
        messages: list[dict],
        tools: list[dict],
        params: LLMParams,
        callbacks: _EventCallbacks | None,
    ) -> dict:
        if callbacks is not None:
            return await llm_client.stream_complete(
                messages=messages,
                on_token=callbacks.on_token,
                on_thinking_token=callbacks.on_thinking_token,
                on_tool_pending=callbacks.on_tool_pending,
                params=params,
                tools=tools,
            )
        return await llm_client.complete(
            messages=messages,
            params=params,
            tools=tools,
        )

    @staticmethod
    def _accumulate_usage(accumulated: dict, step_usage: dict) -> None:
        accumulated["prompt_tokens"] += step_usage.get("prompt_tokens", 0)
        accumulated["completion_tokens"] += step_usage.get("completion_tokens", 0)

    @staticmethod
    def _finalize_span(
        span: Any,
        steps_taken: int,
        tool_calls_total: int,
        approval_requested: bool,
        reason: str,
    ) -> None:
        span.set_attribute("tool_loop.steps_taken", steps_taken)
        span.set_attribute("tool_loop.tool_calls_total", tool_calls_total)
        span.set_attribute("tool_loop.approval_requested", approval_requested)
        span.set_attribute("tool_loop.termination_reason", reason)

    async def _process_tool_call(
        self,
        tc: dict,
        tools: list[dict],
        ctx: RunContext,
        steps_taken: int,
        seen_calls: set[tuple],
        callbacks: _EventCallbacks | None,
    ) -> tuple[dict, bool]:
        """Process one tool call. Returns (tool_result_message, approval_requested)."""
        _raw_name = tc.get("function", {}).get("name") or tc.get("name")
        tool_name: str = _raw_name if isinstance(_raw_name, str) else ""
        _raw_args = tc.get("function", {}).get("arguments") or tc.get("arguments", "{}")
        args_raw: str | dict = _raw_args if isinstance(_raw_args, (str, dict)) else "{}"
        call_id: str = tc.get("id") or str(uuid4())

        call_sig = (
            tool_name,
            args_raw
            if isinstance(args_raw, str)
            else json.dumps(args_raw, sort_keys=True),
        )
        if call_sig in seen_calls:
            logger.warning(
                "tool_call_duplicate_skipped", tool_name=tool_name, step=steps_taken
            )
            return (
                {
                    "role": "user",
                    "content": f"Tool `{tool_name}` was already called with the same arguments — skipping duplicate.",
                },
                False,
            )
        seen_calls.add(call_sig)

        try:
            args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
        except json.JSONDecodeError as e:
            logger.warning(
                "tool_args_json_decode_failed", tool_name=tool_name, error=str(e)
            )
            args = {}

        if callbacks is not None:
            await _safe_emit(
                callbacks.on_event,
                ToolStart(name=tool_name, call_id=call_id, arguments=args),
                "on_event(ToolStart)",
                tool_name,
            )

        is_write = _is_write_tool(tool_name, tools)

        if is_write:
            result, action_id = await self._request_write_approval(tool_name, args, ctx)
            if callbacks is not None and action_id:
                await _safe_emit(
                    callbacks.on_event,
                    ApprovalRequired(
                        action_id=action_id, tool_name=tool_name, arguments=args
                    ),
                    "on_event(ApprovalRequired)",
                    tool_name,
                )
            return (
                {
                    "role": "user",
                    "content": f"Tool result for `{tool_name}`:\n{json.dumps(result)}",
                },
                True,
            )

        result = await self.dispatch(tool_name, args)
        if callbacks is not None:
            result_str = json.dumps(result) if not isinstance(result, str) else result
            await _safe_emit(
                callbacks.on_event,
                ToolDone(name=tool_name, call_id=call_id, result=result_str),
                "on_event(ToolDone)",
                tool_name,
            )

        return (
            {
                "role": "user",
                "content": f"Tool result for `{tool_name}`:\n{json.dumps(result)}",
            },
            False,
        )

    async def run_tool_loop(
        self,
        messages: list[dict],
        tools: list[dict],
        context: RunContext | None = None,
        params: LLMParams | None = None,
        max_steps: int | None = None,
        on_event: Callable[[AgentEvent], Awaitable[None]] | None = None,
    ) -> AgentResult:
        ctx = context or _DEFAULT_CONTEXT
        params = params or LLMParams()
        max_steps = max_steps or agent_config.tool_max_steps
        messages = messages.copy()

        with _tracer.start_as_current_span("agent.tool_loop") as span:
            span.set_attribute("tool_loop.triggered_by", ctx.triggered_by)
            span.set_attribute("tool_loop.max_steps", max_steps)

            steps_taken = 0
            tool_calls_total = 0
            approval_requested = False
            seen_calls: set[tuple] = set()
            accumulated_usage: dict = {"prompt_tokens": 0, "completion_tokens": 0}
            callbacks = self._build_event_callbacks(on_event)

            for step in range(max_steps):
                steps_taken = step + 1
                logger.debug("tool_loop_step", step=steps_taken, max_steps=max_steps)

                response = await self._call_llm(messages, tools, params, callbacks)
                self._accumulate_usage(accumulated_usage, response.get("usage", {}))

                content = response.get("content", "")
                thinking = response.get("thinking", "")
                tool_calls = response.get("tool_calls", [])

                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": content,
                }
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                messages.append(assistant_msg)

                if not tool_calls:
                    logger.debug("tool_loop_final_response", step=steps_taken)
                    self._finalize_span(
                        span, steps_taken, tool_calls_total, approval_requested, "stop"
                    )
                    return AgentResult(
                        content=content, thinking=thinking, usage=accumulated_usage
                    )

                for tc in tool_calls:
                    result_msg, approved = await self._process_tool_call(
                        tc, tools, ctx, steps_taken, seen_calls, callbacks
                    )
                    messages.append(result_msg)
                    if approved:
                        approval_requested = True
                    tool_calls_total += 1

                if approval_requested:
                    final = await self._call_llm(messages, tools, params, callbacks)
                    self._accumulate_usage(accumulated_usage, final.get("usage", {}))
                    self._finalize_span(
                        span, steps_taken, tool_calls_total, True, "approval_requested"
                    )
                    return AgentResult(
                        content=final.get("content", ""),
                        thinking=final.get("thinking", ""),
                        usage=accumulated_usage,
                    )

            self._finalize_span(
                span,
                steps_taken,
                tool_calls_total,
                approval_requested,
                "max_steps_exceeded",
            )
            span.set_status(StatusCode.ERROR, "max_steps_exceeded")
            logger.warning("tool_loop_max_steps_exceeded", max_steps=max_steps)
            return AgentResult(
                content=(
                    "I reached the maximum number of tool steps. "
                    "Please try a more specific request."
                ),
                thinking="",
                usage=accumulated_usage,
            )

    async def _request_write_approval(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: RunContext,
    ) -> tuple[dict[str, Any], str | None]:
        """Request approval for a write tool. Returns (result_dict, action_id)."""
        from agent_core.agent.approval import manager as approval_manager

        description = f"call `{tool_name}` with: {args}"
        payload: dict[str, Any] = {
            "tool_name": tool_name,
            "arguments": args,
            "description": description,
        }
        if context.conversation_id:
            payload["web_conversation_id"] = context.conversation_id
        try:
            async with get_session() as session:
                action = await approval_manager.request_approval(
                    session,
                    payload=payload,
                    triggered_by=context.triggered_by,
                )
            logger.debug("write_tool_approval_requested", tool_name=tool_name)
            return (
                {
                    "status": "approval_requested",
                    "message": "Approval request sent. I'll proceed once you confirm.",
                },
                str(action.id),
            )
        except Exception as e:
            logger.error(
                "write_tool_approval_failed",
                tool_name=tool_name,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            return {"error": f"Failed to request approval: {e}"}, None


tool_loop = ToolLoop()
