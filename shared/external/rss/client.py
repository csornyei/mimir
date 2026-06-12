import asyncio
from datetime import datetime
from html.parser import HTMLParser
from typing import Any

import miniflux

_PAGE_SIZE = 100
_SUMMARY_MAX = 200


class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts).strip()


def _strip_html(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


def _strip_escape_chars(text: str) -> str:
    return text.replace("\n", " ").replace("\r", " ").replace("\t", " ").strip()


class RSSClient:
    def __init__(
        self, url: str | None, username: str | None, password: str | None
    ) -> None:
        self.url = url
        self.username = username
        self.password = password
        self.client: miniflux.Client | None = None

    def _set_client(self) -> None:
        if self.url is None:
            raise RuntimeError("MINIFLUX_URL is not configured.")
        if self.username is None:
            raise RuntimeError("MINIFLUX_USERNAME is not configured.")
        if self.password is None:
            raise RuntimeError("MINIFLUX_PASSWORD is not configured.")
        self.client = miniflux.Client(
            self.url, username=self.username, password=self.password
        )

    async def get_entries(
        self, after: datetime, before: datetime
    ) -> list[dict[str, Any]]:
        if self.url is None:
            raise RuntimeError("MINIFLUX_URL is not configured.")
        if self.username is None:
            raise RuntimeError("MINIFLUX_USERNAME is not configured.")
        if self.password is None:
            raise RuntimeError("MINIFLUX_PASSWORD is not configured.")

        return await asyncio.to_thread(self._fetch_entries, after, before)

    def _fetch_entries(self, after: datetime, before: datetime) -> list[dict[str, Any]]:
        if self.client is None:
            self._set_client()

        all_entries: list[dict[str, Any]] = []
        offset = 0
        total = None
        while True:
            response = self.client.get_entries(  # ty: ignore
                status="unread",
                published_after=int(after.timestamp()),
                published_before=int(before.timestamp()),
                limit=_PAGE_SIZE,
                offset=offset,
            )
            if total is None:
                total = response["total"]
            entries = response["entries"]
            if not entries:
                break
            all_entries.extend(self._parse_entry(e) for e in entries)
            offset += len(entries)
            if offset >= total:
                break
        return all_entries

    def _parse_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        content = entry.get("content", "")
        if content:
            text = _strip_escape_chars(_strip_html(content))
            summary: str | None = text[:_SUMMARY_MAX] if text else None
        else:
            summary = None
        feed = entry.get("feed", {})
        category = feed.get("category", {})
        return {
            "id": entry["id"],
            "title": entry["title"],
            "url": entry["url"],
            "published_at": entry["published_at"],
            "feed_name": feed.get("title"),
            "category": category.get("title"),
            "summary": summary,
        }
