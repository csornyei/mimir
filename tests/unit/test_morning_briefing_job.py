from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mimir.scheduler.briefing.job import run_morning_briefing


def _make_config(
    channel_id="C123456",
    caldav_url="https://cal.example.com",
    caldav_username="user",
    caldav_password="pass",
    slack_bot_token="xoxb-test",
    morning_brief_hour=7,
):
    cfg = MagicMock()
    cfg.morning_brief_channel_id = channel_id
    cfg.caldav_url = caldav_url
    cfg.caldav_username = caldav_username
    cfg.caldav_password = caldav_password
    cfg.slack_bot_token = slack_bot_token
    cfg.morning_brief_hour = morning_brief_hour
    return cfg


SAMPLE_EVENTS = [
    {
        "uid": "uid-1",
        "summary": "Standup",
        "start": "2026-04-17T09:00:00+00:00",
        "end": "2026-04-17T09:30:00+00:00",
        "description": None,
        "location": None,
    }
]


@pytest.mark.asyncio
async def test_run_morning_briefing_skips_when_channel_id_missing():
    cfg = _make_config(channel_id=None)
    with patch("mimir.scheduler.briefing.job.config", cfg), \
         patch("mimir.scheduler.briefing.job.CalDAVClient") as mock_dav:
        await run_morning_briefing()
        mock_dav.assert_not_called()


@pytest.mark.asyncio
async def test_run_morning_briefing_skips_when_caldav_url_missing():
    cfg = _make_config(caldav_url=None)
    with patch("mimir.scheduler.briefing.job.config", cfg), \
         patch("mimir.scheduler.briefing.job.CalDAVClient") as mock_dav:
        await run_morning_briefing()
        mock_dav.assert_not_called()


@pytest.mark.asyncio
async def test_run_morning_briefing_skips_when_caldav_username_missing():
    cfg = _make_config(caldav_username=None)
    with patch("mimir.scheduler.briefing.job.config", cfg), \
         patch("mimir.scheduler.briefing.job.CalDAVClient") as mock_dav:
        await run_morning_briefing()
        mock_dav.assert_not_called()


@pytest.mark.asyncio
async def test_run_morning_briefing_skips_when_caldav_password_missing():
    cfg = _make_config(caldav_password=None)
    with patch("mimir.scheduler.briefing.job.config", cfg), \
         patch("mimir.scheduler.briefing.job.CalDAVClient") as mock_dav:
        await run_morning_briefing()
        mock_dav.assert_not_called()


@pytest.mark.asyncio
async def test_run_morning_briefing_posts_llm_response_to_slack():
    cfg = _make_config()
    mock_dav_instance = AsyncMock()
    mock_dav_instance.get_events.return_value = SAMPLE_EVENTS
    mock_slack_instance = AsyncMock()

    with patch("mimir.scheduler.briefing.job.config", cfg), \
         patch("mimir.scheduler.briefing.job.CalDAVClient", return_value=mock_dav_instance), \
         patch("mimir.scheduler.briefing.job.llm_client") as mock_llm, \
         patch("mimir.scheduler.briefing.job.AsyncWebClient", return_value=mock_slack_instance):
        mock_llm.complete = AsyncMock(return_value={
            "content": "Good morning! You have a standup at 9.",
            "tool_calls": [],
            "finish_reason": "stop",
        })
        await run_morning_briefing()

    mock_slack_instance.chat_postMessage.assert_called_once_with(
        channel="C123456",
        text="Good morning! You have a standup at 9.",
    )


@pytest.mark.asyncio
async def test_run_morning_briefing_creates_caldav_client_with_config_creds():
    cfg = _make_config()
    mock_dav_instance = AsyncMock()
    mock_dav_instance.get_events.return_value = []
    mock_slack_instance = AsyncMock()

    with patch("mimir.scheduler.briefing.job.config", cfg), \
         patch("mimir.scheduler.briefing.job.CalDAVClient", return_value=mock_dav_instance) as mock_dav_class, \
         patch("mimir.scheduler.briefing.job.llm_client") as mock_llm, \
         patch("mimir.scheduler.briefing.job.AsyncWebClient", return_value=mock_slack_instance):
        mock_llm.complete = AsyncMock(return_value={"content": "Good morning!", "tool_calls": [], "finish_reason": "stop"})
        await run_morning_briefing()

    mock_dav_class.assert_called_once_with(
        url="https://cal.example.com",
        username="user",
        password="pass",
    )


@pytest.mark.asyncio
async def test_run_morning_briefing_does_not_raise_on_caldav_error():
    cfg = _make_config()
    mock_dav_instance = AsyncMock()
    mock_dav_instance.get_events.side_effect = Exception("Connection refused")
    mock_slack_instance = AsyncMock()

    with patch("mimir.scheduler.briefing.job.config", cfg), \
         patch("mimir.scheduler.briefing.job.CalDAVClient", return_value=mock_dav_instance), \
         patch("mimir.scheduler.briefing.job.AsyncWebClient", return_value=mock_slack_instance):
        await run_morning_briefing()  # must not raise

    mock_slack_instance.chat_postMessage.assert_not_called()


@pytest.mark.asyncio
async def test_run_morning_briefing_does_not_raise_on_llm_error():
    cfg = _make_config()
    mock_dav_instance = AsyncMock()
    mock_dav_instance.get_events.return_value = SAMPLE_EVENTS
    mock_slack_instance = AsyncMock()

    with patch("mimir.scheduler.briefing.job.config", cfg), \
         patch("mimir.scheduler.briefing.job.CalDAVClient", return_value=mock_dav_instance), \
         patch("mimir.scheduler.briefing.job.llm_client") as mock_llm, \
         patch("mimir.scheduler.briefing.job.AsyncWebClient", return_value=mock_slack_instance):
        mock_llm.complete = AsyncMock(side_effect=Exception("LLM unavailable"))
        await run_morning_briefing()  # must not raise

    mock_slack_instance.chat_postMessage.assert_not_called()
