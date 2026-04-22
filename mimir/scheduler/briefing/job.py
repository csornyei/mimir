from datetime import UTC, datetime

from slack_sdk.web.async_client import AsyncWebClient

from mimir.config import config
from mimir.external.caldav.client import CalDAVClient
from mimir.llm.client import llm_client
from mimir.logger import logger
from mimir.scheduler.briefing.prompt import build_morning_prompt


async def run_morning_briefing() -> None:
    if not config.morning_brief_channel_id:
        logger.warning(
            "morning_briefing_skipped", reason="MORNING_BRIEF_CHANNEL_ID not configured"
        )
        return
    if not all([config.caldav_url, config.caldav_username, config.caldav_password]):
        logger.warning(
            "morning_briefing_skipped", reason="CalDAV credentials not fully configured"
        )
        return

    try:
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)

        client = CalDAVClient(
            url=config.caldav_url,
            username=config.caldav_username,
            password=config.caldav_password,
        )
        events = await client.get_events(today_start, today_end)

        messages = build_morning_prompt(events)
        response = await llm_client.complete(messages=messages)
        briefing_text = response.get("content", "")

        briefing_with_header = f"*Good Morning <@{config.slack_user_id}>! Here's your briefing for today:*\n\n{briefing_text}"

        slack = AsyncWebClient(token=config.slack_bot_token)
        await slack.chat_postMessage(
            channel=config.morning_brief_channel_id,
            text=briefing_with_header,
        )
        logger.info(
            "morning_briefing_sent",
            channel=config.morning_brief_channel_id,
            event_count=len(events),
        )

    except Exception as e:
        logger.error("morning_briefing_failed", error=str(e))
