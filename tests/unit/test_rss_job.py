from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jobs.rss_digest.main import run_digest

START = datetime(2026, 4, 17, 8, 0, tzinfo=timezone.utc)
END = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)


def _make_job_config(
    miniflux_url: str | None = "http://miniflux",
    miniflux_username: str | None = "user",
    miniflux_password: str | None = "pass",
    agent_core_api_url: str | None = "http://localhost:8000",
    rss_digest_min_entries: int = 10,
    rss_digest_picks: int = 10,
    semantic_memory_path: str = "vault/memory.md",
    ntfy_url: str | None = None,
    ntfy_digest_topic: str | None = None,
    mimir_host: str | None = None,
) -> MagicMock:
    cfg = MagicMock()
    cfg.miniflux_url = miniflux_url
    cfg.miniflux_username = miniflux_username
    cfg.miniflux_password = miniflux_password
    cfg.agent_core_api_url = agent_core_api_url
    cfg.rss_digest_min_entries = rss_digest_min_entries
    cfg.rss_digest_picks = rss_digest_picks
    cfg.semantic_memory_path = semantic_memory_path
    cfg.ntfy_url = ntfy_url
    cfg.ntfy_digest_topic = ntfy_digest_topic
    cfg.mimir_host = mimir_host
    return cfg


def _make_entries(n: int) -> list[dict]:
    return [
        {
            "id": i,
            "title": f"Article {i}",
            "url": f"https://example.com/{i}",
            "feed_name": "Blog",
            "category": "Tech",
            "summary": "A summary.",
        }
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_run_digest_skips_when_miniflux_not_configured() -> None:
    with (
        patch("jobs.rss_digest.main.job_config", _make_job_config(miniflux_url=None)),
        patch("jobs.rss_digest.main.RSSClient") as mock_rss,
    ):
        await run_digest(START, END, "08-12")

    mock_rss.assert_not_called()


@pytest.mark.asyncio
async def test_run_digest_skips_when_agent_core_url_not_configured() -> None:
    with (
        patch(
            "jobs.rss_digest.main.job_config", _make_job_config(agent_core_api_url=None)
        ),
        patch("jobs.rss_digest.main.RSSClient") as mock_rss,
    ):
        await run_digest(START, END, "08-12")

    mock_rss.assert_not_called()


@pytest.mark.asyncio
async def test_run_digest_skips_when_below_threshold() -> None:
    mock_rss_instance = MagicMock()
    mock_rss_instance.get_entries = AsyncMock(return_value=_make_entries(3))  # 3 < 10

    with (
        patch("jobs.rss_digest.main.job_config", _make_job_config()),
        patch("jobs.rss_digest.main.RSSClient", return_value=mock_rss_instance),
        patch("jobs.rss_digest.main.llm_filter") as mock_filter,
    ):
        await run_digest(START, END, "08-12")

    mock_filter.assert_not_called()


@pytest.mark.asyncio
async def test_run_digest_stores_picks() -> None:
    entries = _make_entries(15)
    picks = [
        {
            "id": 0,
            "title": "Article 0",
            "url": "https://example.com/0",
            "reason": "interesting",
        }
    ]

    mock_rss_instance = MagicMock()
    mock_rss_instance.get_entries = AsyncMock(return_value=entries)
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    with (
        patch("jobs.rss_digest.main.job_config", _make_job_config()),
        patch("jobs.rss_digest.main.RSSClient", return_value=mock_rss_instance),
        patch(
            "jobs.rss_digest.main.summarise_feedback",
            new=AsyncMock(return_value="No feedback."),
        ),
        patch("jobs.rss_digest.main.llm_filter", new=AsyncMock(return_value=picks)),
        patch("jobs.rss_digest.main.get_session") as mock_ctx,
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        await run_digest(START, END, "08-12")

    mock_session.add.assert_called_once()
    added = mock_session.add.call_args[0][0]
    assert added.window == "08-12"
    assert added.title == "Article 0"
    assert added.slack_message_ts is None
    assert added.slack_channel_id is None


@pytest.mark.asyncio
async def test_run_digest_skips_store_when_no_picks() -> None:
    entries = _make_entries(15)
    mock_rss_instance = MagicMock()
    mock_rss_instance.get_entries = AsyncMock(return_value=entries)

    with (
        patch("jobs.rss_digest.main.job_config", _make_job_config()),
        patch("jobs.rss_digest.main.RSSClient", return_value=mock_rss_instance),
        patch(
            "jobs.rss_digest.main.summarise_feedback",
            new=AsyncMock(return_value="No feedback."),
        ),
        patch("jobs.rss_digest.main.llm_filter", new=AsyncMock(return_value=[])),
        patch("jobs.rss_digest.main.get_session") as mock_ctx,
    ):
        await run_digest(START, END, "08-12")

    mock_ctx.assert_not_called()
