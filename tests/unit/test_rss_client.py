from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from mimir.external.rss.client import RSSClient


START = datetime(2026, 4, 17, 8, 0, tzinfo=timezone.utc)
END = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)


def _make_entry(
    entry_id=1,
    title="Test Article",
    url="https://example.com/article",
    published_at="2026-04-17T10:00:00Z",
    content="<p>Article body text here.</p>",
    feed_title="Tech Blog",
    category_title="Technology",
) -> dict:
    return {
        "id": entry_id,
        "title": title,
        "url": url,
        "published_at": published_at,
        "content": content,
        "feed": {
            "id": 10,
            "title": feed_title,
            "category": {"id": 1, "title": category_title},
        },
    }


def _make_miniflux_response(entries: list[dict]) -> dict:
    return {"total": len(entries), "entries": entries}


def test_init_does_not_raise_with_none_credentials():
    client = RSSClient(url=None, username=None, password=None)
    assert client.url is None
    assert client.username is None
    assert client.password is None


@pytest.mark.asyncio
async def test_get_entries_raises_when_url_missing():
    client = RSSClient(url=None, username="user", password="pass")
    with pytest.raises(RuntimeError, match="MINIFLUX_URL"):
        await client.get_entries(START, END)


@pytest.mark.asyncio
async def test_get_entries_raises_when_username_missing():
    client = RSSClient(url="https://miniflux.example.com", username=None, password="pass")
    with pytest.raises(RuntimeError, match="MINIFLUX_USERNAME"):
        await client.get_entries(START, END)


@pytest.mark.asyncio
async def test_get_entries_raises_when_password_missing():
    client = RSSClient(url="https://miniflux.example.com", username="user", password=None)
    with pytest.raises(RuntimeError, match="MINIFLUX_PASSWORD"):
        await client.get_entries(START, END)


@pytest.mark.asyncio
async def test_get_entries_returns_parsed_entries():
    entry = _make_entry()
    mock_client = MagicMock()
    mock_client.get_entries.return_value = _make_miniflux_response([entry])

    client = RSSClient(url="https://miniflux.example.com", username="user", password="pass")
    with patch("mimir.external.rss.client.miniflux.Client", return_value=mock_client):
        result = await client.get_entries(START, END)

    assert len(result) == 1
    item = result[0]
    assert item["id"] == 1
    assert item["title"] == "Test Article"
    assert item["url"] == "https://example.com/article"
    assert item["feed_name"] == "Tech Blog"
    assert item["category"] == "Technology"
    assert item["published_at"] == "2026-04-17T10:00:00Z"
    assert item["summary"] is not None


@pytest.mark.asyncio
async def test_get_entries_passes_correct_params():
    mock_client = MagicMock()
    mock_client.get_entries.return_value = _make_miniflux_response([])

    client = RSSClient(url="https://miniflux.example.com", username="user", password="pass")
    with patch("mimir.external.rss.client.miniflux.Client", return_value=mock_client):
        await client.get_entries(START, END)

    call_kwargs = mock_client.get_entries.call_args.kwargs
    assert call_kwargs["status"] == "unread"
    assert call_kwargs["published_after"] == int(START.timestamp())
    assert call_kwargs["published_before"] == int(END.timestamp())


@pytest.mark.asyncio
async def test_get_entries_summary_truncated_to_500_chars():
    long_content = "x" * 1000
    entry = _make_entry(content=long_content)
    mock_client = MagicMock()
    mock_client.get_entries.return_value = _make_miniflux_response([entry])

    client = RSSClient(url="https://miniflux.example.com", username="user", password="pass")
    with patch("mimir.external.rss.client.miniflux.Client", return_value=mock_client):
        result = await client.get_entries(START, END)

    assert len(result[0]["summary"]) == 500


@pytest.mark.asyncio
async def test_get_entries_summary_none_when_no_content():
    entry = _make_entry(content="")
    mock_client = MagicMock()
    mock_client.get_entries.return_value = _make_miniflux_response([entry])

    client = RSSClient(url="https://miniflux.example.com", username="user", password="pass")
    with patch("mimir.external.rss.client.miniflux.Client", return_value=mock_client):
        result = await client.get_entries(START, END)

    assert result[0]["summary"] is None


@pytest.mark.asyncio
async def test_get_entries_paginates_when_total_exceeds_page():
    entries_page1 = [_make_entry(entry_id=i) for i in range(1, 101)]
    entries_page2 = [_make_entry(entry_id=i) for i in range(101, 106)]

    mock_client = MagicMock()
    mock_client.get_entries.side_effect = [
        {"total": 105, "entries": entries_page1},
        {"total": 105, "entries": entries_page2},
        {"total": 105, "entries": []},
    ]

    client = RSSClient(url="https://miniflux.example.com", username="user", password="pass")
    with patch("mimir.external.rss.client.miniflux.Client", return_value=mock_client):
        result = await client.get_entries(START, END)

    assert len(result) == 105
    assert mock_client.get_entries.call_count == 2
