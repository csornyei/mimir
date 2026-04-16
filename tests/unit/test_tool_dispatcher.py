"""Tests for ToolDispatcher.run_tool_loop write-tool approval gating."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from mimir.agent.tools import ToolDispatcher


def _tool_call(name: str, args: dict | None = None, call_id: str = "c1") -> dict:
    args_json = json.dumps(args or {})
    return {
        "id": call_id,
        "function": {"name": name, "arguments": args_json},
    }


def _llm_response(tool_calls: list[dict]) -> dict:
    return {"finish_reason": "tool_calls", "content": "", "tool_calls": tool_calls}


def _llm_final(content: str) -> dict:
    return {"finish_reason": "stop", "content": content, "tool_calls": []}


@pytest.mark.asyncio
async def test_write_tool_requests_approval_not_dispatch(mocker):
    """Write tools must trigger approval, not dispatch directly."""
    dispatch_mock = AsyncMock()
    fake_action = MagicMock()
    fake_action.id = uuid4()
    approval_mock = AsyncMock(return_value=fake_action)

    llm_responses = [
        _llm_response([_tool_call("restricted_tool", {"key": "val"})]),
        _llm_final("Approval requested for you."),
    ]

    mock_session = AsyncMock()

    with patch("mimir.agent.tools.llm_client") as mock_llm, \
         patch("mimir.agent.tools.get_session") as mock_session_ctx, \
         patch("mimir.agent.approval.manager.request_approval", new=approval_mock), \
         patch("mimir.agent.tools.ToolDispatcher.dispatch", new=dispatch_mock):

        mock_llm.complete = AsyncMock(side_effect=llm_responses)
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        dispatcher = ToolDispatcher()
        result = await dispatcher.run_tool_loop(
            messages=[{"role": "user", "content": "do the thing"}],
            tools=[{"type": "function", "function": {"name": "restricted_tool", "parameters": {}}, "destructive": True}],
            triggered_by="user:U123",
        )

    dispatch_mock.assert_not_awaited()
    approval_mock.assert_awaited_once()
    call_kwargs = approval_mock.call_args.kwargs
    assert call_kwargs["payload"]["tool_name"] == "restricted_tool"
    assert call_kwargs["triggered_by"] == "user:U123"
    assert result == "Approval requested for you."


@pytest.mark.asyncio
async def test_read_tool_dispatches_directly(mocker):
    """Read tools (destructive=False) must dispatch immediately, no approval."""
    dispatch_mock = AsyncMock(return_value={"result": "pods: []", "isError": False})

    llm_responses = [
        _llm_response([_tool_call("list_pods", {})]),
        _llm_final("No pods running."),
    ]

    with patch("mimir.agent.tools.llm_client") as mock_llm, \
         patch("mimir.agent.tools.ToolDispatcher.dispatch", new=dispatch_mock):
        mock_llm.complete = AsyncMock(side_effect=llm_responses)
        dispatcher = ToolDispatcher()
        result = await dispatcher.run_tool_loop(
            messages=[{"role": "user", "content": "list pods"}],
            tools=[{"type": "function", "function": {"name": "list_pods", "parameters": {}}, "destructive": False}],
            triggered_by="user:U123",
        )

    dispatch_mock.assert_awaited_once()
    assert result == "No pods running."


@pytest.mark.asyncio
async def test_write_tool_injects_approval_pending_result(mocker):
    """After requesting approval, the tool result message must contain status=approval_requested."""
    fake_action = MagicMock()
    fake_action.id = uuid4()

    captured_messages: list[list[dict]] = []

    async def capture_complete(messages, tools):
        captured_messages.append(list(messages))
        if len(captured_messages) == 1:
            return _llm_response([_tool_call("write_mem", {})])
        return _llm_final("I've requested approval.")

    mock_session = AsyncMock()

    with patch("mimir.agent.tools.llm_client") as mock_llm, \
         patch("mimir.agent.tools.get_session") as mock_session_ctx, \
         patch("mimir.agent.approval.manager.request_approval", new=AsyncMock(return_value=fake_action)):

        mock_llm.complete = AsyncMock(side_effect=capture_complete)
        mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        dispatcher = ToolDispatcher()
        await dispatcher.run_tool_loop(
            messages=[{"role": "user", "content": "save this"}],
            tools=[{"type": "function", "function": {"name": "write_mem", "parameters": {}}, "destructive": True}],
        )

    second_call_messages = captured_messages[1]
    tool_result_msgs = [m for m in second_call_messages if m.get("role") == "tool"]
    assert len(tool_result_msgs) == 1
    content = json.loads(tool_result_msgs[0]["content"])
    assert content["status"] == "approval_requested"
