"""Tests for mimir.agent.approval.executor."""

from unittest.mock import MagicMock, patch
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


async def test_execute_memory_write_append(tmp_path):
    action = _make_action(
        {"operation": "append", "content": "User loves cats"},
    )
    # SemanticMemory is imported lazily inside _execute_memory_write
    with patch("mimir.memory.semantic.SemanticMemory") as MockSM:
        instance = MockSM.return_value
        result = await execute(action)

    instance.append_fact.assert_called_once_with("User loves cats")
    assert "memory.md" in result


async def test_execute_memory_write_overwrite_raises():
    action = _make_action(
        {"operation": "overwrite", "content": "something"},
    )
    with patch("mimir.memory.semantic.SemanticMemory"):
        with pytest.raises(NotImplementedError):
            await execute(action)


async def test_execute_memory_write_unknown_operation_raises():
    action = _make_action(
        {"operation": "delete", "content": "something"},
    )
    with patch("mimir.memory.semantic.SemanticMemory"):
        with pytest.raises(ValueError, match="Unknown memory_write operation"):
            await execute(action)


async def test_execute_tool_call_stub_returns_string():
    action = _make_action(
        {"tool_name": "restart_pod", "arguments": {"pod": "api"}},
    )
    result = await execute(action)
    assert isinstance(result, str)
    assert "restart_pod" in result


async def test_execute_propagates_exception():
    action = _make_action(
        {"operation": "append", "content": "x"},
    )
    # Patch the lazy import target so the exception propagates through execute()
    with patch(
        "mimir.memory.semantic.SemanticMemory",
        side_effect=RuntimeError("boom"),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            await execute(action)
