from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import TextContent

from mimir.agent.config import agent_config
from mimir.logger import logger


@asynccontextmanager
async def _mcp_session():
    """Open a fully-initialized MCP session via streamable HTTP transport."""
    logger.debug("establishing_mcp_session", url=agent_config.mcp_url)
    async with streamable_http_client(f"{agent_config.mcp_url}/mcp") as (
        read,
        write,
        close,
    ):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def _tool_to_openai(tool) -> dict:
    """Convert a single MCP Tool object to OpenAI function-calling format."""
    annotations = tool.annotations
    destructive = bool(annotations and annotations.destructiveHint)
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        },
        "destructive": destructive,
    }


def _call_result_to_dict(result) -> dict:
    """Convert MCP CallToolResult to a plain dict."""
    text_parts = []
    for block in result.content:
        if isinstance(block, TextContent):
            text_parts.append(block.text)
        else:
            logger.warning(
                "non_text_content_skipped", content_type=type(block).__name__
            )

    return {
        "result": "\n".join(text_parts),
        "isError": result.isError,
    }


async def fetch_tools_openai_format() -> list[dict]:
    """Fetch available tools from MCP server in OpenAI format."""
    async with _mcp_session() as session:
        result = await session.list_tools()
        tools = [_tool_to_openai(t) for t in result.tools]
        logger.debug("fetched_tool_schemas", count=len(tools))
        return tools


async def call_tool(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Call a tool on the MCP server and return the result dict."""
    async with _mcp_session() as session:
        result = await session.call_tool(tool_name, args)
        return _call_result_to_dict(result)
