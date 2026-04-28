"""Tests for mimir.interfaces.slack.approval."""

from unittest.mock import AsyncMock


from slackbot.approval import (
    _base_emoji,
    format_approval_message,
    on_reaction_added,
    on_thread_reply,
)


# ---------------------------------------------------------------------------
# _base_emoji
# ---------------------------------------------------------------------------


def test_base_emoji_strips_skin_tone_variant():
    assert _base_emoji("+1::skin-tone-2") == "+1"


def test_base_emoji_no_variant():
    assert _base_emoji("white_check_mark") == "white_check_mark"


def test_base_emoji_multiple_colons():
    assert _base_emoji("man-gesturing-no::skin-tone-5") == "man-gesturing-no"


# ---------------------------------------------------------------------------
# format_approval_message
# ---------------------------------------------------------------------------


def test_format_approval_message_tool_call():
    msg = format_approval_message({"description": "restart the pod"})
    assert "restart the pod" in msg
    assert "✅" in msg
    assert "❌" in msg


# ---------------------------------------------------------------------------
# on_reaction_added
# ---------------------------------------------------------------------------


async def test_on_reaction_added_skips_bot_own_reaction(mocker):
    mocker.patch(
        "slackbot.approval.get_bot_user_id",
        new=AsyncMock(return_value="UBOT"),
    )
    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)

    event = {
        "user": "UBOT",
        "reaction": "white_check_mark",
        "item": {"type": "message", "ts": "111.222"},
    }
    client = AsyncMock()

    await on_reaction_added(event, client)

    mock_http.post.assert_not_called()


async def test_on_reaction_added_calls_handle_reaction_with_base_emoji(mocker):
    mocker.patch(
        "slackbot.approval.get_bot_user_id",
        new=AsyncMock(return_value="UBOT"),
    )
    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mocker.patch("slackbot.approval.httpx.AsyncClient", return_value=mock_http)

    event = {
        "user": "U999",
        "reaction": "+1::skin-tone-3",
        "item": {"type": "message", "ts": "111.222"},
    }
    client = AsyncMock()

    await on_reaction_added(event, client)

    mock_http.post.assert_called_once()
    call_kwargs = mock_http.post.call_args
    posted_reaction = call_kwargs.kwargs["json"]["reaction"]
    assert posted_reaction == "+1"


# ---------------------------------------------------------------------------
# on_thread_reply
# ---------------------------------------------------------------------------


async def test_on_thread_reply_returns_false_when_no_thread_ts(mocker):
    event = {"user": "U999", "text": "hello"}
    result = await on_thread_reply(event, AsyncMock(), AsyncMock())
    assert result is False
