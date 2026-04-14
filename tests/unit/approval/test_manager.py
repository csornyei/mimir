"""Tests for mimir.agent.approval.manager."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from mimir.models import ActionStatus, PendingActionModel


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
def patch_slack(mocker):
    """Replace the module-level _slack client with an AsyncMock."""
    mock = AsyncMock()
    mock.chat_postMessage.return_value = {"ts": "999.000"}
    mocker.patch("mimir.agent.approval.manager._slack", mock)
    return mock


@pytest.fixture(autouse=True)
def patch_config(mocker):
    mocker.patch(
        "mimir.agent.approval.manager.config.slack_dm_channel_id", "CDMCHANNEL"
    )
    mocker.patch("mimir.agent.approval.manager.config.approval_timeout_minutes", 10)
    mocker.patch("mimir.agent.approval.manager.config.approval_reinvoke_llm", False)


# ---------------------------------------------------------------------------
# request_approval
# ---------------------------------------------------------------------------


async def test_request_approval_creates_db_record_and_posts_to_slack(
    mocker, patch_slack
):
    mock_store = mocker.patch("mimir.agent.approval.manager.store")
    mock_store.create = AsyncMock(return_value=_make_action())
    # format_approval_message is imported lazily inside request_approval
    mocker.patch(
        "mimir.interfaces.slack.approval.format_approval_message",
        return_value="Approve?",
    )

    session = AsyncMock()
    from mimir.agent.approval import manager

    result = await manager.request_approval(
        session,
        payload={"description": "do stuff", "content": "x", "operation": "append"},
        triggered_by="user:U123",
    )

    patch_slack.chat_postMessage.assert_called_once()
    mock_store.create.assert_called_once()
    assert result is not None


async def test_request_approval_does_not_create_record_if_slack_fails(
    mocker, patch_slack
):
    patch_slack.chat_postMessage.side_effect = RuntimeError("Slack down")
    mock_store = mocker.patch("mimir.agent.approval.manager.store")
    mocker.patch(
        "mimir.interfaces.slack.approval.format_approval_message",
        return_value="Approve?",
    )

    session = AsyncMock()
    from mimir.agent.approval import manager

    with pytest.raises(RuntimeError):
        await manager.request_approval(
            session,
            payload={"description": "do stuff", "content": "x", "operation": "append"},
            triggered_by="user:U123",
        )

    mock_store.create.assert_not_called()


# ---------------------------------------------------------------------------
# handle_reaction
# ---------------------------------------------------------------------------


async def test_handle_reaction_approve_executes_and_completes(mocker, patch_slack):
    action = _make_action()
    mock_store = mocker.patch("mimir.agent.approval.manager.store")
    mock_store.get_by_message_ts = AsyncMock(return_value=action)
    mock_store.set_status = AsyncMock()
    mocker.patch(
        "mimir.agent.approval.manager.executor.execute",
        new=AsyncMock(return_value="done!"),
    )

    session = AsyncMock()
    from mimir.agent.approval import manager

    await manager.handle_reaction(session, "white_check_mark", "111.222", "U999")

    assert mock_store.set_status.call_count >= 2
    patch_slack.chat_postMessage.assert_called()
    last_call = patch_slack.chat_postMessage.call_args_list[-1]
    assert "✅" in last_call.kwargs.get("text", "") or "✅" in str(last_call)


async def test_handle_reaction_approve_posts_error_on_executor_failure(
    mocker, patch_slack
):
    action = _make_action()
    mock_store = mocker.patch("mimir.agent.approval.manager.store")
    mock_store.get_by_message_ts = AsyncMock(return_value=action)
    mock_store.set_status = AsyncMock()
    mocker.patch(
        "mimir.agent.approval.manager.executor.execute",
        new=AsyncMock(side_effect=RuntimeError("fail")),
    )

    session = AsyncMock()
    from mimir.agent.approval import manager

    await manager.handle_reaction(session, "white_check_mark", "111.222", "U999")

    texts = [
        c.kwargs.get("text", "") for c in patch_slack.chat_postMessage.call_args_list
    ]
    assert any("⚠️" in t for t in texts)


async def test_handle_reaction_reject_sets_rejected_status(mocker, patch_slack):
    action = _make_action()
    mock_store = mocker.patch("mimir.agent.approval.manager.store")
    mock_store.get_by_message_ts = AsyncMock(return_value=action)
    mock_store.set_status = AsyncMock()

    session = AsyncMock()
    from mimir.agent.approval import manager

    await manager.handle_reaction(session, "x", "111.222", "U999")

    mock_store.set_status.assert_called_once()
    call_args = mock_store.set_status.call_args
    assert (
        call_args.args[2] == ActionStatus.rejected
        or call_args.kwargs.get("status") == ActionStatus.rejected
    )
    texts = [
        c.kwargs.get("text", "") for c in patch_slack.chat_postMessage.call_args_list
    ]
    assert any("❌" in t for t in texts)


async def test_handle_reaction_ignores_unknown_emoji(mocker):
    action = _make_action()
    mock_store = mocker.patch("mimir.agent.approval.manager.store")
    mock_store.get_by_message_ts = AsyncMock(return_value=action)
    mock_store.set_status = AsyncMock()

    session = AsyncMock()
    from mimir.agent.approval import manager

    await manager.handle_reaction(session, "wave", "111.222", "U999")

    mock_store.set_status.assert_not_called()


async def test_handle_reaction_ignores_terminal_status(mocker):
    action = _make_action(status=ActionStatus.completed)
    mock_store = mocker.patch("mimir.agent.approval.manager.store")
    mock_store.get_by_message_ts = AsyncMock(return_value=action)
    mock_store.set_status = AsyncMock()

    session = AsyncMock()
    from mimir.agent.approval import manager

    await manager.handle_reaction(session, "white_check_mark", "111.222", "U999")

    mock_store.set_status.assert_not_called()


async def test_handle_reaction_not_found(mocker):
    mock_store = mocker.patch("mimir.agent.approval.manager.store")
    mock_store.get_by_message_ts = AsyncMock(return_value=None)
    mock_store.set_status = AsyncMock()

    session = AsyncMock()
    from mimir.agent.approval import manager

    # Should not raise
    await manager.handle_reaction(session, "white_check_mark", "999.999", "U999")

    mock_store.set_status.assert_not_called()


# ---------------------------------------------------------------------------
# handle_thread_reply
# ---------------------------------------------------------------------------


async def test_handle_thread_reply_transitions_pending_to_discussing(
    mocker, patch_slack
):
    action = _make_action(status=ActionStatus.pending)
    mock_store = mocker.patch("mimir.agent.approval.manager.store")
    mock_store.get_by_thread_ts = AsyncMock(return_value=action)
    mock_store.set_discussing = AsyncMock()
    mocker.patch(
        "mimir.agent.approval.manager.agent_client.send_to_agent",
        new=AsyncMock(return_value="Here's my thought..."),
    )

    say = AsyncMock()
    session = AsyncMock()
    from mimir.agent.approval import manager

    result = await manager.handle_thread_reply(
        session, thread_ts="111.222", text="Why?", user_id="U999", say=say
    )

    assert result is True
    mock_store.set_discussing.assert_called_once()
    say.assert_called_once()


async def test_handle_thread_reply_returns_false_if_no_action(mocker):
    mock_store = mocker.patch("mimir.agent.approval.manager.store")
    mock_store.get_by_thread_ts = AsyncMock(return_value=None)

    session = AsyncMock()
    from mimir.agent.approval import manager

    result = await manager.handle_thread_reply(
        session, thread_ts="999.999", text="hello", user_id="U999", say=AsyncMock()
    )

    assert result is False


# ---------------------------------------------------------------------------
# process_timeouts
# ---------------------------------------------------------------------------


async def test_process_timeouts_rejects_expired_actions(mocker, patch_slack):
    actions = [_make_action(), _make_action()]
    mock_store = mocker.patch("mimir.agent.approval.manager.store")
    mock_store.get_timed_out = AsyncMock(return_value=actions)
    mock_store.set_status = AsyncMock()

    session = AsyncMock()
    from mimir.agent.approval import manager

    await manager.process_timeouts(session)

    assert mock_store.set_status.call_count == 2
    assert patch_slack.chat_postMessage.call_count == 2
