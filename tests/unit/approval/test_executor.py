"""Tests for mimir.agent.approval.executor."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from mimir.agent.approval.executor import execute
from mimir.models import ActionStatus, PendingActionModel


def _make_action(payload: dict) -> PendingActionModel:
    action = MagicMock(spec=PendingActionModel)
    action.id = uuid4()
    action.payload = payload
    action.status = ActionStatus.pending
    return action


async def test_execute_tool_call_dispatches_with_action_id():
    """executor.execute() must inject action_id into the dispatch args."""
    action = _make_action({"tool_name": "restart_pod", "arguments": {"pod": "api"}})
    dispatch_mock = AsyncMock(return_value={"result": "pod restarted", "isError": False})

    with patch(
        "mimir.agent.approval.executor.tool_dispatcher.dispatch",
        new=dispatch_mock,
    ):
        result = await execute(action)

    dispatch_mock.assert_awaited_once_with(
        "restart_pod",
        {"pod": "api", "action_id": str(action.id)},
    )
    assert isinstance(result, str)


async def test_execute_propagates_exception():
    action = _make_action({"tool_name": "bad_tool", "arguments": {}})
    with patch(
        "mimir.agent.approval.executor.tool_dispatcher.dispatch",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            await execute(action)
