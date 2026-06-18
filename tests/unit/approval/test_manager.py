"""Tests for agent_core.agent.approval.manager."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.models import ActionStatus, PendingActionModel


def _make_action(
    status: ActionStatus = ActionStatus.pending,
) -> MagicMock:
    action = MagicMock(spec=PendingActionModel)
    action.id = uuid4()
    action.status = status
    action.channel_id = "C123"
    action.message_ts = "111.222"
    action.thread_ts = "111.222"
    action.payload = {
        "description": "update memory",
        "content": "foo",
        "operation": "append",
    }
    return action


@pytest.fixture(autouse=True)
def patch_config(mocker):
    mocker.patch(
        "agent_core.agent.approval.manager.agent_config.approval_timeout_minutes", 10
    )
    mocker.patch(
        "agent_core.agent.approval.manager.agent_config.approval_reinvoke_llm", False
    )


# ---------------------------------------------------------------------------
# request_approval
# ---------------------------------------------------------------------------


async def test_request_approval_creates_db_record(mocker):
    mock_store = mocker.patch("agent_core.agent.approval.manager.store")
    mock_store.create = AsyncMock(return_value=_make_action())

    session = AsyncMock()
    from agent_core.agent.approval import manager

    result = await manager.request_approval(
        session,
        payload={"description": "do stuff", "content": "x", "operation": "append"},
        triggered_by="user:U123",
    )

    mock_store.create.assert_called_once()
    assert result is not None


async def test_request_approval_creates_record(mocker):
    mock_store = mocker.patch("agent_core.agent.approval.manager.store")
    mock_store.create = AsyncMock(return_value=_make_action())

    session = AsyncMock()
    from agent_core.agent.approval import manager

    result = await manager.request_approval(
        session,
        payload={"description": "do stuff", "content": "x", "operation": "append"},
        triggered_by="user:U123",
    )

    mock_store.create.assert_called_once()
    assert result is not None


# ---------------------------------------------------------------------------
# approve_action / reject_action
# ---------------------------------------------------------------------------


async def test_approve_action_executes_and_completes(mocker):
    action = _make_action()
    mock_store = mocker.patch("agent_core.agent.approval.manager.store")
    mock_store.set_status = AsyncMock()
    mocker.patch(
        "agent_core.agent.approval.manager.executor.execute",
        new=AsyncMock(return_value="done!"),
    )

    session = AsyncMock()
    from agent_core.agent.approval import manager

    await manager.approve_action(session, action, "web")

    assert mock_store.set_status.call_count >= 2


async def test_approve_action_handles_executor_failure(mocker):
    action = _make_action()
    mock_store = mocker.patch("agent_core.agent.approval.manager.store")
    mock_store.set_status = AsyncMock()
    mocker.patch(
        "agent_core.agent.approval.manager.executor.execute",
        new=AsyncMock(side_effect=RuntimeError("fail")),
    )

    session = AsyncMock()
    from agent_core.agent.approval import manager

    await manager.approve_action(session, action, "web")

    # Verify status was changed to rejected on error
    calls = mock_store.set_status.call_args_list
    final_call = calls[-1]
    assert (
        final_call.args[2] == ActionStatus.rejected
        or final_call.kwargs.get("status") == ActionStatus.rejected
    )


async def test_reject_action_sets_rejected_status(mocker):
    action = _make_action()
    mock_store = mocker.patch("agent_core.agent.approval.manager.store")
    mock_store.set_status = AsyncMock()

    session = AsyncMock()
    from agent_core.agent.approval import manager

    await manager.reject_action(session, action)

    mock_store.set_status.assert_called_once()
    call_args = mock_store.set_status.call_args
    assert (
        call_args.args[2] == ActionStatus.rejected
        or call_args.kwargs.get("status") == ActionStatus.rejected
    )


# ---------------------------------------------------------------------------
# process_timeouts
# ---------------------------------------------------------------------------


async def test_process_timeouts_rejects_expired_actions(mocker):
    actions = [_make_action(), _make_action()]
    mock_store = mocker.patch("agent_core.agent.approval.manager.store")
    mock_store.get_timed_out = AsyncMock(return_value=actions)
    mock_store.set_status = AsyncMock()

    session = AsyncMock()
    from agent_core.agent.approval import manager

    await manager.process_timeouts(session)

    assert mock_store.set_status.call_count == 2
