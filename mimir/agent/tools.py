import json
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import StatusCode

from mimir.agent.config import agent_config
from mimir.agent.dispatcher import ToolDispatcher
from mimir.db import get_session
from mimir.logger import logger
from mimir.llm.client import llm_client

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
    ) -> str:
        max_steps = max_steps or agent_config.tool_max_steps
        messages = messages.copy()  # Don't mutate caller's list

        with _tracer.start_as_current_span("agent.tool_loop") as span:
            span.set_attribute("tool_loop.triggered_by", triggered_by)
            span.set_attribute("tool_loop.max_steps", max_steps)

            steps_taken = 0
            tool_calls_total = 0
            approval_requested = False

            for step in range(max_steps):
                steps_taken = step + 1
                logger.debug("tool_loop_step", step=steps_taken, max_steps=max_steps)

                response = await llm_client.complete(messages=messages, tools=tools)

                finish_reason = response.get("finish_reason", "stop")
                content = response.get("content", "")
                tool_calls = response.get("tool_calls", [])

                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": content,
                }
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                messages.append(assistant_msg)

                if not tool_calls or finish_reason == "stop":
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

                    if _is_write_tool(tool_name, tools):
                        result = await self._request_write_approval(
                            tool_name, args, triggered_by
                        )
                        approval_requested = True
                    else:
                        result = await self.dispatch(tool_name, args)

                    tool_calls_total += 1
                    tool_results.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.get("id", ""),
                            "name": tool_name,
                            "content": json.dumps(result),
                        }
                    )

                messages.extend(tool_results)

                if approval_requested:
                    final = await llm_client.complete(messages=messages, tools=tools)
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
        self, tool_name: str, args: dict[str, Any], triggered_by: str
    ) -> dict[str, Any]:
        # Lazy import to avoid circular: tools → manager → executor → tools
        from mimir.agent.approval import manager as approval_manager

        description = f"call `{tool_name}` with: {args}"
        payload = {
            "tool_name": tool_name,
            "arguments": args,
            "description": description,
        }
        try:
            async with get_session() as session:
                await approval_manager.request_approval(
                    session,
                    payload=payload,
                    triggered_by=triggered_by,
                )
            logger.debug("write_tool_approval_requested", tool_name=tool_name)
            return {
                "status": "approval_requested",
                "message": "Approval request sent. I'll proceed once you confirm in the DMs.",
            }
        except Exception as e:
            logger.error(
                "write_tool_approval_failed", tool_name=tool_name, error=str(e)
            )
            return {"error": f"Failed to request approval: {e}"}


tool_loop = ToolLoop()
