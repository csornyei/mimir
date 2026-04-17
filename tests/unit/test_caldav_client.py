from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from mimir.external.caldav.client import CalDAVClient


START = datetime(2026, 4, 1, tzinfo=timezone.utc)
END = datetime(2026, 4, 30, tzinfo=timezone.utc)


def _make_vevent(
    uid="uid-1",
    summary="Meeting",
    dtstart=datetime(2026, 4, 10, 9, 0, tzinfo=timezone.utc),
    dtend=datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc),
    description=None,
    location=None,
) -> MagicMock:
    """Build a mock icalendar VEVENT component."""
    data = {
        "UID": uid,
        "SUMMARY": summary,
        "DTSTART": MagicMock(dt=dtstart),
        "DTEND": MagicMock(dt=dtend) if dtend else None,
        "DESCRIPTION": description,
        "LOCATION": location,
    }

    component = MagicMock()
    component.get.side_effect = lambda key, default=None: data.get(key, default)
    return component


def _make_caldav_event(vevents: list[MagicMock]) -> MagicMock:
    """Build a mock caldav Event wrapping a list of VEVENT components."""
    cal = MagicMock()
    cal.walk.return_value = vevents
    event = MagicMock()
    event.icalendar_component = cal
    return event


def _make_calendar(events: list[MagicMock]) -> MagicMock:
    calendar = MagicMock()
    calendar.date_search.return_value = events
    return calendar


def _make_dav_client(calendars: list[MagicMock]) -> MagicMock:
    principal = MagicMock()
    principal.calendars.return_value = calendars
    client = MagicMock()
    client.principal.return_value = principal
    return client


# --- Tests ---


@pytest.mark.asyncio
async def test_get_events_raises_when_url_missing():
    client = CalDAVClient(url=None, username="user", password="pass")
    with pytest.raises(RuntimeError, match="CALDAV_URL"):
        await client.get_events(START, END)


@pytest.mark.asyncio
async def test_get_events_raises_when_username_missing():
    client = CalDAVClient(url="https://cal.example.com", username=None, password="pass")
    with pytest.raises(RuntimeError, match="CALDAV_USERNAME"):
        await client.get_events(START, END)


@pytest.mark.asyncio
async def test_get_events_raises_when_password_missing():
    client = CalDAVClient(url="https://cal.example.com", username="user", password=None)
    with pytest.raises(RuntimeError, match="CALDAV_PASSWORD"):
        await client.get_events(START, END)


@pytest.mark.asyncio
async def test_get_events_returns_parsed_events():
    vevent = _make_vevent(
        uid="uid-1",
        summary="Team Standup",
        dtstart=datetime(2026, 4, 10, 9, 0, tzinfo=timezone.utc),
        dtend=datetime(2026, 4, 10, 9, 30, tzinfo=timezone.utc),
        description="Daily sync",
        location="Room A",
    )
    dav_event = _make_caldav_event([vevent])
    calendar = _make_calendar([dav_event])
    dav_client = _make_dav_client([calendar])

    client = CalDAVClient(
        url="https://cal.example.com", username="user", password="pass"
    )

    with patch("mimir.external.caldav.client.DAVClient", return_value=dav_client):
        result = await client.get_events(START, END)

    assert len(result) == 1
    event = result[0]
    assert event["uid"] == "uid-1"
    assert event["summary"] == "Team Standup"
    assert event["description"] == "Daily sync"
    assert event["location"] == "Room A"
    assert "2026-04-10" in event["start"]
    assert "2026-04-10" in event["end"]


@pytest.mark.asyncio
async def test_get_events_optional_fields_none_when_missing():
    vevent = _make_vevent(dtend=None, description=None, location=None)
    dav_event = _make_caldav_event([vevent])
    calendar = _make_calendar([dav_event])
    dav_client = _make_dav_client([calendar])

    client = CalDAVClient(
        url="https://cal.example.com", username="user", password="pass"
    )

    with patch("mimir.external.caldav.client.DAVClient", return_value=dav_client):
        result = await client.get_events(START, END)

    assert len(result) == 1
    event = result[0]
    assert event["end"] is None
    assert event["description"] is None
    assert event["location"] is None


@pytest.mark.asyncio
async def test_get_events_flattens_multiple_calendars():
    vevent_a = _make_vevent(uid="uid-a", summary="Event A")
    vevent_b = _make_vevent(uid="uid-b", summary="Event B")
    cal_a = _make_calendar([_make_caldav_event([vevent_a])])
    cal_b = _make_calendar([_make_caldav_event([vevent_b])])
    dav_client = _make_dav_client([cal_a, cal_b])

    client = CalDAVClient(
        url="https://cal.example.com", username="user", password="pass"
    )

    with patch("mimir.external.caldav.client.DAVClient", return_value=dav_client):
        result = await client.get_events(START, END)

    assert len(result) == 2
    uids = {e["uid"] for e in result}
    assert uids == {"uid-a", "uid-b"}


@pytest.mark.asyncio
async def test_get_events_passes_date_range_to_search():
    calendar = _make_calendar([])
    dav_client = _make_dav_client([calendar])

    client = CalDAVClient(
        url="https://cal.example.com", username="user", password="pass"
    )

    with patch("mimir.external.caldav.client.DAVClient", return_value=dav_client):
        await client.get_events(START, END)

    calendar.date_search.assert_called_once_with(start=START, end=END, expand=True)


def test_init_does_not_raise_with_none_credentials():
    # Must not raise — validation is deferred to get_events()
    client = CalDAVClient(url=None, username=None, password=None)
    assert client.url is None
    assert client.username is None
    assert client.password is None
