import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional

from caldav.davclient import DAVClient


class CalDAVClient:
    def __init__(
        self, url: str | None, username: str | None, password: str | None
    ) -> None:
        self.url = url
        self.username = username
        self.password = password

    async def get_events(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        self._validate_credentials()
        return await asyncio.to_thread(self._fetch_events, start, end)

    async def get_todos(self, end: datetime) -> list[dict[str, Any]]:
        self._validate_credentials()
        return await asyncio.to_thread(self._fetch_todos, end)

    async def create_event(
        self,
        calendar_name: str,
        start: datetime,
        end: datetime,
        summary: str,
        description: Optional[str] = None,
        location: Optional[str] = None,
        alarm_trigger: Optional[timedelta] = None,
        alarm_action: Optional[str] = None,
    ) -> None:
        self._validate_credentials()
        await asyncio.to_thread(
            self._create_event,
            calendar_name,
            start,
            end,
            summary,
            description,
            location,
            alarm_trigger,
            alarm_action,
        )

    async def create_todo(
        self,
        calendar_name: str,
        due: datetime,
        summary: str,
        description: Optional[str] = None,
        status: Optional[str] = None,
    ) -> None:
        self._validate_credentials()
        await asyncio.to_thread(
            self._create_todo,
            calendar_name,
            due,
            summary,
            description,
            status,
        )

    def _create_event(
        self,
        calendar_name: str,
        start: datetime,
        end: datetime,
        summary: str,
        description: Optional[str],
        location: Optional[str],
        alarm_trigger: Optional[timedelta],
        alarm_action: Optional[str],
    ) -> None:
        client = DAVClient(url=self.url, username=self.username, password=self.password)
        principal = client.principal()
        calendars = principal.calendars()

        if not calendars:
            raise RuntimeError("No calendars found for the user.")

        if (
            not calendar_name
            or calendar_name == ""
            or [c.get_display_name() for c in calendars].count(calendar_name) == 0
        ):
            raise RuntimeError(
                f"Calendar with name '{calendar_name}' not found. Available calendars: {[c.get_display_name() for c in calendars]}"
            )

        if start >= end:
            raise ValueError("Event start time must be before end time.")

        if summary == "":
            raise ValueError("Event summary cannot be empty.")

        if alarm_trigger is not None and alarm_action is None:
            alarm_action = "DISPLAY"

        calendar = next(c for c in calendars if c.get_display_name() == calendar_name)

        calendar.add_event(
            dtstart=start,
            dtend=end,
            summary=summary,
            description=description,
            location=location,
            alarm_trigger=alarm_trigger,
            alarm_action=alarm_action,
        )

    def _create_todo(
        self,
        calendar_name: str,
        due: datetime,
        summary: str,
        description: Optional[str],
        status: Optional[str],
    ) -> None:
        client = DAVClient(url=self.url, username=self.username, password=self.password)
        principal = client.principal()
        calendars = principal.calendars()

        if not calendars:
            raise RuntimeError("No calendars found for the user.")

        if (
            not calendar_name
            or calendar_name == ""
            or [c.get_display_name() for c in calendars].count(calendar_name) == 0
        ):
            raise RuntimeError(
                f"Calendar with name '{calendar_name}' not found. Available calendars: {[c.get_display_name() for c in calendars]}"
            )

        if summary == "":
            raise ValueError("To-Do summary cannot be empty.")

        calendar = next(c for c in calendars if c.get_display_name() == calendar_name)

        calendar.add_todo(
            due=due,
            summary=summary,
            description=description,
            status=status,
        )

    def _validate_credentials(self) -> None:
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

    def _fetch_events(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        client = DAVClient(url=self.url, username=self.username, password=self.password)
        principal = client.principal()
        calendars = principal.calendars()

        events: list[dict[str, Any]] = []
        for calendar in calendars:
            results = calendar.search(start=start, end=end, event=True, expand=True)
            for event in results:
                for component in event.icalendar_component.walk("VEVENT"):
                    events.append(self._parse_event(component))
        return events

    def _fetch_todos(self, end: datetime) -> list[dict[str, Any]]:
        client = DAVClient(url=self.url, username=self.username, password=self.password)
        principal = client.principal()
        calendars = principal.calendars()

        todos: list[dict[str, Any]] = []
        for calendar in calendars:
            results = calendar.search(end=end, todo=True)
            for todo in results:
                for component in todo.icalendar_component.walk("VTODO"):
                    todos.append(self._parse_todo(component))
        return todos

    def _parse_todo(self, component: Any) -> dict[str, Any]:
        def _dt(field: str) -> str | None:
            val = component.get(field)
            if val is None:
                return None
            return val.dt.isoformat()

        return {
            "uid": str(component.get("UID", "")),
            "summary": str(component.get("SUMMARY", "")),
            "due": _dt("DUE"),
            "description": (
                str(component.get("DESCRIPTION"))
                if component.get("DESCRIPTION")
                else None
            ),
            "status": str(component.get("STATUS")) if component.get("STATUS") else None,
        }

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
            "description": (
                str(component.get("DESCRIPTION"))
                if component.get("DESCRIPTION")
                else None
            ),
            "location": (
                str(component.get("LOCATION")) if component.get("LOCATION") else None
            ),
        }


if __name__ == "__main__":
    from shared.config import shared_config

    client = CalDAVClient(
        url=shared_config.caldav_url,
        username=shared_config.caldav_username,
        password=shared_config.caldav_password,
    )

    if not shared_config.default_calendar_name:
        print(
            "No default calendar name configured. Please set SHARED_CALDAV_DEFAULT_CALENDAR_NAME in your .env file to run the test."
        )
        exit(1)

    client._create_event(
        calendar_name=shared_config.default_calendar_name,
        start=datetime(2026, 5, 5, 14, 0),
        end=datetime(2026, 5, 5, 15, 0),
        summary="Test Event",
        description="This is a test event created by the CalDAV client.",
        location="Virtual",
        alarm_trigger=timedelta(minutes=-15),
        alarm_action="DISPLAY",
    )

    client._create_todo(
        calendar_name=shared_config.default_calendar_name,
        due=datetime(2026, 5, 6, 17, 0),
        summary="TEST TODO",
        description="DELETE THIS TODO!",
        status="NEEDS-ACTION",
    )

    async def test() -> None:
        events = await client.get_events(datetime(2026, 5, 1), datetime(2026, 5, 10))
        print("\n----\nEvents:")
        for event in events:
            print(f"\t{event}")

        todos = client._fetch_todos(datetime(2026, 5, 10))
        print("\n----\nTo-Dos:")
        for todo in todos:
            print(f"\t{todo}")

    asyncio.run(test())
