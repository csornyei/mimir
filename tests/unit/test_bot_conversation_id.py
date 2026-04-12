"""Tests for mimir.interfaces.slack.bot._conversation_id."""

from mimir.interfaces.slack.bot import _conversation_id


def test_conversation_id_dm():
    event = {
        "channel": "D123",
        "channel_type": "im",
        "ts": "111.000",
    }
    result = _conversation_id(event)
    assert result == "D123|111.000"


def test_conversation_id_thread():
    event = {
        "channel": "C456",
        "channel_type": "channel",
        "ts": "100.000",
        "thread_ts": "99.000",
    }
    result = _conversation_id(event)
    assert result == "C456|99.000"


def test_conversation_id_fallback_to_ts_when_no_thread():
    event = {
        "channel": "C456",
        "channel_type": "channel",
        "ts": "100.000",
    }
    result = _conversation_id(event)
    assert result == "C456|100.000"
