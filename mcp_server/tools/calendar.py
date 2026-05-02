from datetime import datetime, timedelta
from typing import Any

from shared.external.caldav.client import CalDAVClient
from shared.logger import logger
from mcp_server.config import mcp_config
from mcp_server.decorators import traced_tool, write_tool

caldav_client = CalDAVClient(
    url=mcp_config.caldav_url,
    username=mcp_config.caldav_username,
    password=mcp_config.caldav_password,
)


@traced_tool
async def get_calendar_events(start: str, end: str) -> list[dict[str, Any]]:
    """Fetch all calendar events from the configured CalDAV server within a date range.

    Args:
        start: Start of the date range in ISO 8601 format (e.g. "2026-04-01T00:00:00+00:00")
        end: End of the date range in ISO 8601 format (e.g. "2026-04-30T23:59:59+00:00")

    Returns:
        List of events with uid, summary, start, end, description, and location fields.
    """
    try:
        logger.debug("get_calendar_events", start=start, end=end)
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        return await caldav_client.get_events(start_dt, end_dt)
    except Exception as e:
        logger.error("Error fetching calendar events", error=str(e), exec_info=True)
        return []


@traced_tool
async def get_calendar_todos(end: str) -> list[dict[str, Any]]:
    """Fetch all calendar todos from the configured CalDAV server that are due before a certain date.

    Args:
        end: End of the date range in ISO 8601 format (e.g. "2026-04-30T23:59:59+00:00")

    Returns:
        List of todos with uid, summary, due, description, and status fields.
    """
    logger.debug("get_calendar_todos", end=end)
    end_dt = datetime.fromisoformat(end)
    return await caldav_client.get_todos(end_dt)


@write_tool
async def create_calendar_event(
    calendar_name: str,
    start: str,
    end: str,
    summary: str,
    description: str | None = None,
    location: str | None = None,
    alarm_trigger: Any | None = None,
) -> dict[str, str]:
    """Create a calendar event on the configured CalDAV server.

    Args:
        start: Start of the event in ISO 8601 format (e.g. "2026-05-05T14:00:00+00:00")
        end: End of the event in ISO 8601 format (e.g. "2026-05-05T15:00:00+00:00")
        summary: Summary of the event
        description: Description of the event (optional)
        location: Location of the event (optional)
        alarm_trigger: Time before the event to trigger an alarm (optional), either 15m, 30m or 1h. Default is 1h.
        calendar_name: Name of the calendar to create the event in (optional). If not provided, the default calendar will be used.

    Returns:
        Dictionary with the UID of the created event.
    """
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)

    alarm_triggers = {
        "15m": timedelta(minutes=-15),
        "30m": timedelta(minutes=-30),
        "1h": timedelta(hours=-1),
        "default": timedelta(hours=-1),
    }

    if alarm_trigger is not None and alarm_trigger in alarm_triggers:
        alarm_trigger_delta = alarm_triggers[alarm_trigger]
    else:
        alarm_trigger_delta = alarm_triggers["default"]

    await caldav_client.create_event(
        start=start_dt,
        end=end_dt,
        summary=summary,
        description=description,
        location=location,
        alarm_trigger=alarm_trigger_delta,
        alarm_action="DISPLAY",
        calendar_name=calendar_name,
    )
    return {"message": "Event created successfully."}


@write_tool
async def create_calendar_todo(
    calendar_name: str,
    due: str,
    summary: str,
    description: str | None = None,
    status: str = "NEEDS-ACTION",
) -> dict[str, str]:
    """Create a calendar todo on the configured CalDAV server.

    Args:
        due: Due date of the todo in ISO 8601 format (e.g. "2026-05-06T17:00:00+00:00")
        summary: Summary of the todo
        description: Description of the todo (optional)
        status: Status of the todo (optional), either NEEDS-ACTION, COMPLETED, IN-PROCESS or CANCELLED. Default is NEEDS-ACTION.
        calendar_name: Name of the calendar to create the todo in (optional). If not provided, the default calendar will be used.
    """

    due_dt = datetime.fromisoformat(due)

    await caldav_client.create_todo(
        due=due_dt,
        summary=summary,
        description=description,
        status=status,
        calendar_name=calendar_name,
    )
    return {"message": "Todo created successfully."}
