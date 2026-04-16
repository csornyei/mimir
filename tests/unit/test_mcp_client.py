from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mimir.agent.mcp_client import (
    _call_result_to_dict,
    _tool_to_openai,
    call_tool,
    fetch_tools_openai_format,
)


# ---------------------------------------------------------------------------
# _tool_to_openai
# ---------------------------------------------------------------------------


def test_tool_to_openai_normal():
    tool = MagicMock()
    tool.name = "web_search"
    tool.description = "Search the web"
    tool.inputSchema = {"type": "object", "properties": {"query": {"type": "string"}}}

    result = _tool_to_openai(tool)

    assert result == {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
        },
    }


def test_tool_to_openai_null_description():
    tool = MagicMock()
    tool.name = "list_files"
    tool.description = None
    tool.inputSchema = {"type": "object"}

    result = _tool_to_openai(tool)

    assert result["function"]["description"] == ""
    assert result["function"]["name"] == "list_files"


# ---------------------------------------------------------------------------
# _call_result_to_dict
# ---------------------------------------------------------------------------


def test_call_result_to_dict_single_text():
    from mcp.types import TextContent

    block = TextContent(type="text", text="hello world")
    result_mock = MagicMock()
    result_mock.content = [block]
    result_mock.isError = False

    result = _call_result_to_dict(result_mock)

    assert result == {"result": "hello world", "isError": False}


def test_call_result_to_dict_multiple_text_blocks():
    from mcp.types import TextContent

    result_mock = MagicMock()
    result_mock.content = [
        TextContent(type="text", text="line 1"),
        TextContent(type="text", text="line 2"),
    ]
    result_mock.isError = False

    result = _call_result_to_dict(result_mock)

    assert result == {"result": "line 1\nline 2", "isError": False}


def test_call_result_to_dict_with_error():
    from mcp.types import TextContent

    result_mock = MagicMock()
    result_mock.content = [TextContent(type="text", text="something failed")]
    result_mock.isError = True

    result = _call_result_to_dict(result_mock)

    assert result["isError"] is True
    assert result["result"] == "something failed"


def test_call_result_to_dict_empty_content():
    result_mock = MagicMock()
    result_mock.content = []
    result_mock.isError = False

    result = _call_result_to_dict(result_mock)

    assert result == {"result": "", "isError": False}


def test_call_result_to_dict_non_text_block_skipped():
    from mcp.types import TextContent

    non_text = MagicMock(spec=[])  # not a TextContent
    text = TextContent(type="text", text="valid")
    result_mock = MagicMock()
    result_mock.content = [non_text, text]
    result_mock.isError = False

    result = _call_result_to_dict(result_mock)

    assert result["result"] == "valid"


# ---------------------------------------------------------------------------
# fetch_tools_openai_format
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_tools_openai_format_returns_converted_tools():
    tool = MagicMock()
    tool.name = "search"
    tool.description = "Search docs"
    tool.inputSchema = {"type": "object"}

    list_result = MagicMock()
    list_result.tools = [tool]

    mock_session = AsyncMock()
    mock_session.list_tools = AsyncMock(return_value=list_result)

    with patch("mimir.agent.mcp_client._mcp_session") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await fetch_tools_openai_format()

    assert len(result) == 1
    assert result[0]["function"]["name"] == "search"
    assert result[0]["type"] == "function"


@pytest.mark.asyncio
async def test_fetch_tools_openai_format_empty():
    list_result = MagicMock()
    list_result.tools = []

    mock_session = AsyncMock()
    mock_session.list_tools = AsyncMock(return_value=list_result)

    with patch("mimir.agent.mcp_client._mcp_session") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await fetch_tools_openai_format()

    assert result == []


# ---------------------------------------------------------------------------
# call_tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_tool_returns_result_dict():
    from mcp.types import TextContent

    call_result = MagicMock()
    call_result.content = [TextContent(type="text", text="42 pods running")]
    call_result.isError = False

    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=call_result)

    with patch("mimir.agent.mcp_client._mcp_session") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await call_tool("list_pods", {"namespace": "default"})

    assert result == {"result": "42 pods running", "isError": False}
    mock_session.call_tool.assert_awaited_once_with("list_pods", {"namespace": "default"})


@pytest.mark.asyncio
async def test_call_tool_propagates_exception():
    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(side_effect=ConnectionError("server down"))

    with patch("mimir.agent.mcp_client._mcp_session") as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(ConnectionError):
            await call_tool("any_tool", {})
