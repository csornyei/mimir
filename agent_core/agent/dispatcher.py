import asyncio
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import StatusCode

from agent_core.config import agent_config
from agent_core.agent.mcp_client import call_tool
from shared.logger import logger

_tracer = trace.get_tracer("mimir.agent.dispatcher")


class ToolDispatcher:
    """Dispatch tool calls to the MCP server and handle responses."""

    async def dispatch(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        with _tracer.start_as_current_span("tool.dispatch") as span:
            span.set_attribute("tool.name", tool_name)
            try:
                safe_args = {
                    k: (
                        v[: len(v) // 5] + "***" + v[-(len(v) // 5) :]
                        if isinstance(v, str)
                        else v
                    )
                    for k, v in args.items()
                }
                logger.debug("dispatching_tool", tool_name=tool_name, args=safe_args)
                result = await call_tool(tool_name, args)
                logger.debug("tool_executed", tool_name=tool_name)
                return result

            except asyncio.TimeoutError:
                error_msg = f"Tool {tool_name} timed out after {agent_config.tool_call_timeout_seconds}s"
                logger.error(
                    "tool_timeout",
                    tool_name=tool_name,
                    timeout_seconds=agent_config.tool_call_timeout_seconds,
                )
                span.set_status(StatusCode.ERROR, "tool_timeout")
                return {"error": error_msg}

            except Exception as e:
                error_msg = f"Tool execution failed: {str(e)}"
                logger.error(
                    "tool_execution_error",
                    tool_name=tool_name,
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )
                span.set_status(StatusCode.ERROR, str(e))
                return {"error": error_msg}

    async def close(self) -> None:
        pass


tool_dispatcher = ToolDispatcher()
