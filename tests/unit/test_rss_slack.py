from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_post_digest_header_returns_ts():
    from agent_core.scheduler.rss.job import post_digest_header

    mock_client = MagicMock()
    mock_client.chat_postMessage = AsyncMock(return_value={"ts": "111.222"})

    with patch("agent_core.scheduler.rss.job.AsyncWebClient", return_value=mock_client):
        ts = await post_digest_header("C123", 50, 8)

    assert ts == "111.222"


@pytest.mark.asyncio
async def test_post_digest_header_message_contains_counts():
    from agent_core.scheduler.rss.job import post_digest_header

    mock_client = MagicMock()
    mock_client.chat_postMessage = AsyncMock(return_value={"ts": "111.222"})

    with patch("agent_core.scheduler.rss.job.AsyncWebClient", return_value=mock_client):
        await post_digest_header("C123", 50, 8)

    call_kwargs = mock_client.chat_postMessage.call_args.kwargs
    assert call_kwargs["channel"] == "C123"
    assert "50" in call_kwargs["text"]
    assert "8" in call_kwargs["text"]


@pytest.mark.asyncio
async def test_post_pick_returns_ts():
    from agent_core.scheduler.rss.job import post_pick

    mock_client = MagicMock()
    mock_client.chat_postMessage = AsyncMock(return_value={"ts": "333.444"})
    pick = {
        "id": 1,
        "title": "Great Article",
        "url": "https://example.com",
        "reason": "Very relevant",
    }

    with patch("agent_core.scheduler.rss.job.AsyncWebClient", return_value=mock_client):
        ts = await post_pick("C123", "111.222", pick, pick["url"])

    assert ts == "333.444"


@pytest.mark.asyncio
async def test_post_pick_posts_to_thread():
    from agent_core.scheduler.rss.job import post_pick

    mock_client = MagicMock()
    mock_client.chat_postMessage = AsyncMock(return_value={"ts": "333.444"})
    pick = {
        "id": 1,
        "title": "Great Article",
        "url": "https://example.com",
        "reason": "Very relevant",
    }

    with patch("agent_core.scheduler.rss.job.AsyncWebClient", return_value=mock_client):
        await post_pick("C123", "111.222", pick, pick["url"])

    call_kwargs = mock_client.chat_postMessage.call_args.kwargs
    assert call_kwargs["channel"] == "C123"
    assert call_kwargs["thread_ts"] == "111.222"


@pytest.mark.asyncio
async def test_post_pick_message_contains_title_and_reason():
    from agent_core.scheduler.rss.job import post_pick

    mock_client = MagicMock()
    mock_client.chat_postMessage = AsyncMock(return_value={"ts": "333.444"})
    pick = {
        "id": 1,
        "title": "Great Article",
        "url": "https://example.com",
        "reason": "Very relevant",
    }

    with patch("agent_core.scheduler.rss.job.AsyncWebClient", return_value=mock_client):
        await post_pick("C123", "111.222", pick, pick["url"])

    call_kwargs = mock_client.chat_postMessage.call_args.kwargs
    assert "Great Article" in call_kwargs["text"]
    assert "Very relevant" in call_kwargs["text"]
    assert "<https://example.com|Great Article>" in call_kwargs["text"]


@pytest.mark.asyncio
async def test_post_pick_handles_missing_reason():
    from agent_core.scheduler.rss.job import post_pick

    mock_client = MagicMock()
    mock_client.chat_postMessage = AsyncMock(return_value={"ts": "333.444"})
    pick = {
        "id": 1,
        "title": "Great Article",
        "url": "https://example.com",
    }  # no reason

    with patch("agent_core.scheduler.rss.job.AsyncWebClient", return_value=mock_client):
        ts = await post_pick("C123", "111.222", pick, pick["url"])

    assert ts == "333.444"
    call_kwargs = mock_client.chat_postMessage.call_args.kwargs
    assert "Great Article" in call_kwargs["text"]
    assert "_None_" not in call_kwargs["text"]
