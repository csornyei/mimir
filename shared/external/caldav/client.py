import asyncio
from datetime import datetime
from typing import Any

from caldav.davclient import DAVClient


class CalDAVClient:
    def __init__(
        self, url: str | None, username: str | None, password: str | None
    ) -> None:
        self.url = url
        self.username = username
        self.password = password

    async def get_events(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        if self.url is None:
            raise RuntimeError(
                "CalDAV credentials not configured: CALDAV_URL is missing."
            )
        if self.username is None:
            raise RuntimeError(
                "CalDAV credentials not configured: CALDAV_USERNAME is missing."
            )
        if self.password is None:
            raise RuntimeError(
                "CalDAV credentials not configured: CALDAV_PASSWORD is missing."
            )
        return await asyncio.to_thread(self._fetch_events, start, end)

    def _fetch_events(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        client = DAVClient(url=self.url, username=self.username, password=self.password)
        principal = client.principal()
        calendars = principal.calendars()

        events: list[dict[str, Any]] = []
        for calendar in calendars:
            results = calendar.date_search(start=start, end=end, expand=True)
            for event in results:
                for component in event.icalendar_component.walk("VEVENT"):
                    events.append(self._parse_event(component))
        return events

    def _parse_event(self, component: Any) -> dict[str, Any]:
        def _dt(field: str) -> str | None:
            val = component.get(field)
            if val is None:
                return None
            return val.dt.isoformat()

        return {
            "uid": str(component.get("UID", "")),
            "summary": str(component.get("SUMMARY", "")),
            "start": _dt("DTSTART"),
            "end": _dt("DTEND"),
            "description": str(component.get("DESCRIPTION"))
            if component.get("DESCRIPTION")
            else None,
            "location": str(component.get("LOCATION"))
            if component.get("LOCATION")
            else None,
        }
