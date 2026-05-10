import json
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from opentelemetry import trace
from opentelemetry.trace import StatusCode

from agent_core.config import agent_config
from agent_core.agent.dispatcher import ToolDispatcher
from shared.db import get_session
from shared.logger import logger
from agent_core.llm.client import llm_client

_tracer = trace.get_tracer("mimir.agent.tools")


def _is_write_tool(tool_name: str, tools: list[dict]) -> bool:
    for t in tools:
        if t.get("function", {}).get("name") == tool_name:
            return t.get("destructive", False)
    return False


class ToolLoop(ToolDispatcher):
    """Agentic tool loop: drives LLM ↔ MCP tool calls until a final response."""

    async def run_tool_loop(
        self,
        messages: list[dict],
        tools: list[dict],
        max_steps: int | None = None,
        triggered_by: str = "agent",
        conversation_id: str | None = None,
        # Legacy combined callback kept for backward compat (fires after execution)
        on_tool_call: Callable[[str, dict, dict], Awaitable[None]] | None = None,
        # New separate callbacks
        on_tool_start: Callable[[str, dict, str], Awaitable[None]] | None = None,
        on_tool_done: Callable[[str, str, str], Awaitable[None]] | None = None,
        on_approval_required: Callable[[str, str, dict], Awaitable[None]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        min_p: float | None = None,
        repetition_penalty: float | None = None,
        enable_thinking: bool | None = None,
        thinking_budget: int | None = None,
    ) -> str:
        max_steps = max_steps or agent_config.tool_max_steps
        messages = messages.copy()

        with _tracer.start_as_current_span("agent.tool_loop") as span:
            span.set_attribute("tool_loop.triggered_by", triggered_by)
            span.set_attribute("tool_loop.max_steps", max_steps)

            steps_taken = 0
            tool_calls_total = 0
            approval_requested = False
            seen_individual_calls: set[tuple] = set()

            for step in range(max_steps):
                steps_taken = step + 1
                logger.debug("tool_loop_step", step=steps_taken, max_steps=max_steps)

                response = await llm_client.complete(
                    messages=messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    min_p=min_p,
                    repetition_penalty=repetition_penalty,
                    enable_thinking=enable_thinking,
                    thinking_budget=thinking_budget,
                )

                content = response.get("content", "")
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
                    span.set_attribute("tool_loop.steps_taken", steps_taken)
                    span.set_attribute("tool_loop.tool_calls_total", tool_calls_total)
                    span.set_attribute(
                        "tool_loop.approval_requested", approval_requested
                    )
                    span.set_attribute("tool_loop.termination_reason", "stop")
                    return content

                tool_results = []
                for tc in tool_calls:
                    tool_name = tc.get("function", {}).get("name") or tc.get("name")
                    args_raw = tc.get("function", {}).get("arguments") or tc.get(
                        "arguments", "{}"
                    )
                    call_id: str = tc.get("id") or str(uuid4())

                    call_sig = (
                        tool_name,
                        (
                            args_raw
                            if isinstance(args_raw, str)
                            else json.dumps(args_raw, sort_keys=True)
                        ),
                    )
                    if call_sig in seen_individual_calls:
                        logger.warning(
                            "tool_call_duplicate_skipped",
                            tool_name=tool_name,
                            step=steps_taken,
                        )
                        tool_results.append(
                            {
                                "role": "user",
                                "content": f"Tool `{tool_name}` was already called with the same arguments — skipping duplicate.",
                            }
                        )
                        continue
                    seen_individual_calls.add(call_sig)

                    try:
                        args = (
                            json.loads(args_raw)
                            if isinstance(args_raw, str)
                            else args_raw
                        )
                    except json.JSONDecodeError as e:
                        logger.warning(
                            "tool_args_json_decode_failed",
                            tool_name=tool_name,
                            error=str(e),
                        )
                        args = {}

                    # Fire on_tool_start before dispatch
                    if on_tool_start is not None:
                        try:
                            await on_tool_start(tool_name, args, call_id)
                        except Exception as cb_err:
                            logger.warning(
                                "tool_callback_error",
                                callback="on_tool_start",
                                tool_name=tool_name,
                                error=str(cb_err),
                            )

                    if _is_write_tool(tool_name, tools):
                        result, action_id = await self._request_write_approval(
                            tool_name, args, triggered_by, conversation_id
                        )
                        approval_requested = True
                        if on_approval_required is not None and action_id:
                            try:
                                await on_approval_required(action_id, tool_name, args)
                            except Exception as cb_err:
                                logger.warning(
                                    "tool_callback_error",
                                    callback="on_approval_required",
                                    tool_name=tool_name,
                                    error=str(cb_err),
                                )
                    else:
                        result = await self.dispatch(tool_name, args)

                    tool_calls_total += 1

                    # Legacy callback (fires after read-tool execution; skipped for write tools)
                    if on_tool_call is not None and not _is_write_tool(
                        tool_name, tools
                    ):
                        try:
                            await on_tool_call(tool_name, args, result)
                        except Exception as cb_err:
                            logger.warning(
                                "tool_callback_error",
                                callback="on_tool_call",
                                tool_name=tool_name,
                                error=str(cb_err),
                            )

                    # New separate done callback (only for read tools)
                    if on_tool_done is not None and not _is_write_tool(
                        tool_name, tools
                    ):
                        try:
                            result_str = (
                                json.dumps(result)
                                if not isinstance(result, str)
                                else result
                            )
                            await on_tool_done(tool_name, result_str, call_id)
                        except Exception as cb_err:
                            logger.warning(
                                "tool_callback_error",
                                callback="on_tool_done",
                                tool_name=tool_name,
                                error=str(cb_err),
                            )

                    tool_results.append(
                        {
                            "role": "user",
                            "content": f"Tool result for `{tool_name}`:\n{json.dumps(result)}",
                        }
                    )

                messages.extend(tool_results)

                if approval_requested:
                    final = await llm_client.complete(
                        messages=messages,
                        tools=tools,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                        min_p=min_p,
                        repetition_penalty=repetition_penalty,
                        enable_thinking=enable_thinking,
                        thinking_budget=thinking_budget,
                    )
                    span.set_attribute("tool_loop.steps_taken", steps_taken)
                    span.set_attribute("tool_loop.tool_calls_total", tool_calls_total)
                    span.set_attribute("tool_loop.approval_requested", True)
                    span.set_attribute(
                        "tool_loop.termination_reason", "approval_requested"
                    )
                    return final.get("content", "")

            span.set_attribute("tool_loop.steps_taken", steps_taken)
            span.set_attribute("tool_loop.tool_calls_total", tool_calls_total)
            span.set_attribute("tool_loop.approval_requested", approval_requested)
            span.set_attribute("tool_loop.termination_reason", "max_steps_exceeded")
            span.set_status(StatusCode.ERROR, "max_steps_exceeded")
            logger.warning("tool_loop_max_steps_exceeded", max_steps=max_steps)
            return (
                "I reached the maximum number of tool steps. "
                "Please try a more specific request."
            )

    async def _request_write_approval(
        self,
        tool_name: str,
        args: dict[str, Any],
        triggered_by: str,
        conversation_id: str | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Request approval for a write tool. Returns (result_dict, action_id)."""
        from agent_core.agent.approval import manager as approval_manager

        description = f"call `{tool_name}` with: {args}"
        payload: dict[str, Any] = {
            "tool_name": tool_name,
            "arguments": args,
            "description": description,
        }
        if conversation_id:
            payload["web_conversation_id"] = conversation_id
        try:
            async with get_session() as session:
                action = await approval_manager.request_approval(
                    session,
                    payload=payload,
                    triggered_by=triggered_by,
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
