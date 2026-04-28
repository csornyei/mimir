from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_core.agent.conversation import ConversationManager
from shared.models import ConversationModel, MessageModel


@pytest.fixture
def manager():
    return ConversationManager()


@pytest.fixture
def session():
    # session.add() is synchronous in SQLAlchemy; only DB I/O methods are async.
    s = MagicMock()
    s.get = AsyncMock()
    s.execute = AsyncMock()
    s.flush = AsyncMock()
    s.scalars = AsyncMock()
    s.commit = AsyncMock()
    return s


# ---------------------------------------------------------------------------
# get_or_create_conversation
# ---------------------------------------------------------------------------


async def test_get_or_create_returns_existing(manager, session):
    existing = ConversationModel(id="conv-1")
    session.get.return_value = existing

    result = await manager.get_or_create_conversation(session, "conv-1")

    assert result is existing
    session.add.assert_not_called()
    session.flush.assert_not_called()


async def test_get_or_create_creates_new_when_missing(manager, session):
    session.get.return_value = None

    await manager.get_or_create_conversation(session, "new-conv")

    session.add.assert_called_once()
    added = session.add.call_args[0][0]
    assert isinstance(added, ConversationModel)
    assert added.id == "new-conv"
    session.flush.assert_called_once()


async def test_get_or_create_returns_new_model(manager, session):
    session.get.return_value = None

    result = await manager.get_or_create_conversation(session, "brand-new")

    assert isinstance(result, ConversationModel)
    assert result.id == "brand-new"


# ---------------------------------------------------------------------------
# add_message
# ---------------------------------------------------------------------------


async def test_add_message_adds_correct_model(manager, session):
    await manager.add_message(session, "conv-1", "user", "Hello world")

    session.add.assert_called_once()
    added = session.add.call_args[0][0]
    assert isinstance(added, MessageModel)
    assert added.conversation_id == "conv-1"
    assert added.role == "user"
    assert added.content == "Hello world"


async def test_add_message_updates_last_active(manager, session):
    await manager.add_message(session, "conv-1", "assistant", "Hi")

    # An UPDATE statement should have been executed to set last_active
    session.execute.assert_called_once()


async def test_add_message_assistant_role(manager, session):
    await manager.add_message(session, "conv-1", "assistant", "Response text")

    added = session.add.call_args[0][0]
    assert added.role == "assistant"


# ---------------------------------------------------------------------------
# window
# ---------------------------------------------------------------------------


async def test_window_returns_messages_in_chronological_order(manager, session):
    # DB returns newest-first (DESC), window() reverses to oldest-first
    msg_new = MagicMock(spec=MessageModel, role="assistant", content="Hi")
    msg_old = MagicMock(spec=MessageModel, role="user", content="Hello")

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [msg_new, msg_old]
    session.execute.return_value = mock_result

    result = await manager.window(session, "conv-1", n=2)

    assert result == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]


async def test_window_empty_conversation(manager, session):
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result

    result = await manager.window(session, "conv-1", n=20)

    assert result == []


async def test_window_returns_role_content_dicts(manager, session):
    msg = MagicMock(spec=MessageModel, role="user", content="test")
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [msg]
    session.execute.return_value = mock_result

    result = await manager.window(session, "conv-1", n=1)

    assert len(result) == 1
    assert set(result[0].keys()) == {"role", "content"}
