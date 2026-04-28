from datetime import datetime
from typing import Any

from shared.external.caldav.client import CalDAVClient
from shared.logger import logger
from mcp_server.config import mcp_config
from mcp_server.decorators import traced_tool

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
    logger.debug("get_calendar_events", start=start, end=end)
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    return await caldav_client.get_events(start_dt, end_dt)
