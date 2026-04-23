import asyncio
from typing import Any

from mimir.agent.config import agent_config
from mimir.agent.mcp_client import call_tool
from mimir.logger import logger


class ToolDispatcher:
    """Dispatch tool calls to the MCP server and handle responses."""

    async def dispatch(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            logger.debug("dispatching_tool", tool_name=tool_name, args=args)
            result = await call_tool(tool_name, args)
            logger.debug("tool_executed", tool_name=tool_name)
            return result

        except asyncio.TimeoutError:
            error_msg = f"Tool {tool_name} timed out after {agent_config.tool_call_timeout_seconds}s"
            logger.error("tool_timeout", tool_name=tool_name)
            return {"error": error_msg}

        except Exception as e:
            error_msg = f"Tool execution failed: {str(e)}"
            logger.error("tool_execution_error", tool_name=tool_name, error=str(e))
            return {"error": error_msg}

    async def close(self) -> None:
        pass


tool_dispatcher = ToolDispatcher()
