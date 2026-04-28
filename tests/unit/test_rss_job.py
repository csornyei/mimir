from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

START = datetime(2026, 4, 17, 8, 0, tzinfo=timezone.utc)
END = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)

_BASE_AGENT_CONFIG = dict(
    miniflux_url="http://miniflux",
    miniflux_username="user",
    miniflux_password="pass",
    rss_digest_min_entries=10,
    rss_digest_picks=10,
    newspaper_channel_id="C123",
    slack_bot_token="xoxb-test",
)


def _make_agent_config(**overrides):
    cfg = MagicMock()
    for k, v in {**_BASE_AGENT_CONFIG, **overrides}.items():
        setattr(cfg, k, v)
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
async def test_run_digest_skips_when_channel_not_configured():
    from agent_core.scheduler.rss.job import run_digest

    with (
        patch(
            "agent_core.scheduler.rss.job.agent_config",
            _make_agent_config(newspaper_channel_id=None),
        ),
        patch("agent_core.scheduler.rss.job.RSSClient") as mock_rss,
    ):
        await run_digest(START, END, "08-12")

    mock_rss.assert_not_called()


@pytest.mark.asyncio
async def test_run_digest_skips_when_miniflux_not_configured():
    from agent_core.scheduler.rss.job import run_digest

    with (
        patch(
            "agent_core.scheduler.rss.job.agent_config",
            _make_agent_config(miniflux_url=None),
        ),
        patch("agent_core.scheduler.rss.job.RSSClient") as mock_rss,
    ):
        await run_digest(START, END, "08-12")

    mock_rss.assert_not_called()


@pytest.mark.asyncio
async def test_run_digest_skips_when_below_threshold():
    from agent_core.scheduler.rss.job import run_digest

    mock_rss = MagicMock()
    mock_rss.get_entries = AsyncMock(return_value=_make_entries(3))  # 3 < 10

    with (
        patch("agent_core.scheduler.rss.job.agent_config", _make_agent_config()),
        patch("agent_core.scheduler.rss.job.RSSClient", return_value=mock_rss),
        patch("agent_core.scheduler.rss.job.post_digest_header") as mock_post,
    ):
        await run_digest(START, END, "08-12")

    mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_run_digest_posts_header_and_picks():
    from agent_core.scheduler.rss.job import run_digest

    entries = _make_entries(15)
    picks = [
        {
            "id": 0,
            "title": "Article 0",
            "url": "https://example.com/0",
            "reason": "interesting",
        }
    ]

    mock_rss = MagicMock()
    mock_rss.get_entries = AsyncMock(return_value=entries)

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    with (
        patch("agent_core.scheduler.rss.job.agent_config", _make_agent_config()),
        patch("agent_core.scheduler.rss.job.RSSClient", return_value=mock_rss),
        patch(
            "agent_core.scheduler.rss.job.summarise_feedback",
            new=AsyncMock(return_value="No feedback."),
        ),
        patch("agent_core.scheduler.rss.job.SemanticMemory") as mock_mem,
        patch(
            "agent_core.scheduler.rss.job.llm_filter", new=AsyncMock(return_value=picks)
        ),
        patch(
            "agent_core.scheduler.rss.job.post_digest_header",
            new=AsyncMock(return_value="111.000"),
        ),
        patch(
            "agent_core.scheduler.rss.job.post_pick",
            new=AsyncMock(return_value="222.000"),
        ),
        patch("agent_core.scheduler.rss.job.get_session") as mock_ctx,
    ):
        mock_mem.return_value.read.return_value = ""
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        await run_digest(START, END, "08-12")

    mock_session.add.assert_called_once()
    added_entry = mock_session.add.call_args[0][0]
    assert added_entry.slack_message_ts == "222.000"
    assert added_entry.window == "08-12"


@pytest.mark.asyncio
async def test_run_digest_skips_post_when_no_picks():
    from agent_core.scheduler.rss.job import run_digest

    entries = _make_entries(15)

    mock_rss = MagicMock()
    mock_rss.get_entries = AsyncMock(return_value=entries)

    with (
        patch("agent_core.scheduler.rss.job.agent_config", _make_agent_config()),
        patch("agent_core.scheduler.rss.job.RSSClient", return_value=mock_rss),
        patch(
            "agent_core.scheduler.rss.job.summarise_feedback",
            new=AsyncMock(return_value="No feedback."),
        ),
        patch("agent_core.scheduler.rss.job.SemanticMemory") as mock_mem,
        patch(
            "agent_core.scheduler.rss.job.llm_filter", new=AsyncMock(return_value=[])
        ),
        patch("agent_core.scheduler.rss.job.post_digest_header") as mock_post,
    ):
        mock_mem.return_value.read.return_value = ""
        await run_digest(START, END, "08-12")

    mock_post.assert_not_called()
