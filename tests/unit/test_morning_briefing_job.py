from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jobs.morning_briefing.main import run_morning_briefing
from shared.schemas import LLMSettings


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


def _make_job_config(
    timezone: str | None = "Europe/Amsterdam",
    caldav_url: str | None = "https://cal.example.com",
    caldav_username: str | None = "user",
    caldav_password: str | None = "pass",
    weather_config_path: str | None = "/etc/weather.yaml",
    llm_model: str | None = "gemma4:26b",
    llm_presets_path: str | None = "config/presets.yaml",
    ntfy_url: str | None = "https://ntfy.example.com",
    ntfy_morning_brief_topic: str | None = "morning-brief",
    mimir_host: str | None = "https://mimir.example.com",
    agent_core_api_url: str | None = "http://localhost:8000",
    owner_name: str = "Alice",
    service_name: str = "mimir-jobs",
) -> MagicMock:
    cfg = MagicMock()
    cfg.timezone = timezone
    cfg.caldav_url = caldav_url
    cfg.caldav_username = caldav_username
    cfg.caldav_password = caldav_password
    cfg.weather_config_path = weather_config_path
    cfg.llm_model = llm_model
    cfg.llm_presets_path = llm_presets_path
    cfg.ntfy_url = ntfy_url
    cfg.ntfy_morning_brief_topic = ntfy_morning_brief_topic
    cfg.mimir_host = mimir_host
    cfg.agent_core_api_url = agent_core_api_url
    cfg.owner_name = owner_name
    cfg.service_name = service_name
    return cfg


def _mock_http_client() -> tuple[MagicMock, AsyncMock]:
    """Returns (mock_class, mock_instance) for httpx.AsyncClient."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock(return_value=None)
    mock_instance = AsyncMock()
    mock_instance.post = AsyncMock(return_value=mock_response)
    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_cls, mock_instance


@pytest.mark.asyncio
async def test_run_morning_briefing_skips_when_caldav_url_missing() -> None:
    with (
        patch(
            "jobs.morning_briefing.main.job_config", _make_job_config(caldav_url=None)
        ),
        patch("jobs.morning_briefing.main.CalDAVClient") as mock_dav,
    ):
        await run_morning_briefing()
        mock_dav.assert_not_called()


@pytest.mark.asyncio
async def test_run_morning_briefing_skips_when_caldav_username_missing() -> None:
    with (
        patch(
            "jobs.morning_briefing.main.job_config",
            _make_job_config(caldav_username=None),
        ),
        patch("jobs.morning_briefing.main.CalDAVClient") as mock_dav,
    ):
        await run_morning_briefing()
        mock_dav.assert_not_called()


@pytest.mark.asyncio
async def test_run_morning_briefing_skips_when_caldav_password_missing() -> None:
    with (
        patch(
            "jobs.morning_briefing.main.job_config",
            _make_job_config(caldav_password=None),
        ),
        patch("jobs.morning_briefing.main.CalDAVClient") as mock_dav,
    ):
        await run_morning_briefing()
        mock_dav.assert_not_called()


@pytest.mark.asyncio
async def test_run_morning_briefing_skips_when_agent_core_url_missing() -> None:
    with (
        patch(
            "jobs.morning_briefing.main.job_config",
            _make_job_config(agent_core_api_url=None),
        ),
        patch("jobs.morning_briefing.main.CalDAVClient") as mock_dav,
    ):
        await run_morning_briefing()
        mock_dav.assert_not_called()


@pytest.mark.asyncio
async def test_run_morning_briefing_calls_agent_core_api() -> None:
    mock_cls, mock_instance = _mock_http_client()

    with (
        patch("jobs.morning_briefing.main.job_config", _make_job_config()),
        patch("jobs.morning_briefing.main.CalDAVClient") as mock_dav_class,
        patch(
            "jobs.morning_briefing.main.prepare_llm_settings",
            return_value=LLMSettings(),
        ),
        patch("jobs.morning_briefing.main.send_ntfy", new=AsyncMock()),
        patch("httpx.AsyncClient", mock_cls),
    ):
        mock_dav_instance = AsyncMock()
        mock_dav_instance.get_events = AsyncMock(return_value=SAMPLE_EVENTS)
        mock_dav_instance.get_todos = AsyncMock(return_value=[])
        mock_dav_class.return_value = mock_dav_instance

        await run_morning_briefing()

    mock_instance.post.assert_called_once()


@pytest.mark.asyncio
async def test_run_morning_briefing_creates_caldav_client_with_config_creds() -> None:
    mock_cls, _ = _mock_http_client()

    with (
        patch("jobs.morning_briefing.main.job_config", _make_job_config()),
        patch("jobs.morning_briefing.main.CalDAVClient") as mock_dav_class,
        patch(
            "jobs.morning_briefing.main.prepare_llm_settings",
            return_value=LLMSettings(),
        ),
        patch("jobs.morning_briefing.main.send_ntfy", new=AsyncMock()),
        patch("httpx.AsyncClient", mock_cls),
    ):
        mock_dav_instance = AsyncMock()
        mock_dav_instance.get_events = AsyncMock(return_value=[])
        mock_dav_instance.get_todos = AsyncMock(return_value=[])
        mock_dav_class.return_value = mock_dav_instance

        await run_morning_briefing()

    mock_dav_class.assert_called_once_with(
        url="https://cal.example.com",
        username="user",
        password="pass",
    )


@pytest.mark.asyncio
async def test_run_morning_briefing_does_not_raise_on_caldav_error() -> None:
    mock_cls, _ = _mock_http_client()

    with (
        patch("jobs.morning_briefing.main.job_config", _make_job_config()),
        patch("jobs.morning_briefing.main.CalDAVClient") as mock_dav_class,
        patch(
            "jobs.morning_briefing.main.prepare_llm_settings",
            return_value=LLMSettings(),
        ),
        patch("jobs.morning_briefing.main.send_ntfy", new=AsyncMock()),
        patch("httpx.AsyncClient", mock_cls),
    ):
        mock_dav_instance = AsyncMock()
        mock_dav_instance.get_events = AsyncMock(
            side_effect=Exception("Connection refused")
        )
        mock_dav_instance.get_todos = AsyncMock(return_value=[])
        mock_dav_class.return_value = mock_dav_instance

        await run_morning_briefing()  # must not raise


@pytest.mark.asyncio
async def test_run_morning_briefing_does_not_raise_on_http_error() -> None:
    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(side_effect=Exception("Connection refused"))
    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("jobs.morning_briefing.main.job_config", _make_job_config()),
        patch("jobs.morning_briefing.main.CalDAVClient") as mock_dav_class,
        patch(
            "jobs.morning_briefing.main.prepare_llm_settings",
            return_value=LLMSettings(),
        ),
        patch("httpx.AsyncClient", mock_cls),
    ):
        mock_dav_instance = AsyncMock()
        mock_dav_instance.get_events = AsyncMock(return_value=SAMPLE_EVENTS)
        mock_dav_instance.get_todos = AsyncMock(return_value=[])
        mock_dav_class.return_value = mock_dav_instance

        await run_morning_briefing()  # must not raise
