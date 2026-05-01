from datetime import UTC, datetime

from slack_sdk.web.async_client import AsyncWebClient

from agent_core.config import agent_config
from shared.external.caldav.client import CalDAVClient
from shared.external.weather.weather import get_weather_data
from agent_core.llm.client import llm_client
from shared.logger import logger
from agent_core.scheduler.briefing.prompt import build_morning_prompt


async def run_morning_briefing() -> None:
    if not agent_config.morning_brief_channel_id:
        logger.warning(
            "morning_briefing_skipped", reason="MORNING_BRIEF_CHANNEL_ID not configured"
        )
        return
    if not all(
        [
            agent_config.caldav_url,
            agent_config.caldav_username,
            agent_config.caldav_password,
        ]
    ):
        logger.warning(
            "morning_briefing_skipped", reason="CalDAV credentials not fully configured"
        )
        return

    try:
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)

        client = CalDAVClient(
            url=agent_config.caldav_url,
            username=agent_config.caldav_username,
            password=agent_config.caldav_password,
        )
        events = await client.get_events(today_start, today_end)

        weather_data = None
        if agent_config.weather_config_path:
            weather_data = await get_weather_data(agent_config.weather_config_path)

        messages = build_morning_prompt(events, weather_data)
        response = await llm_client.complete(messages=messages)
        briefing_text = response.get("content", "")

        briefing_with_header = (
            f"*Good Morning <@{agent_config.slack_user_id}>! "
            f"Here's your briefing for today:*\n\n{briefing_text}"
        )

        slack = AsyncWebClient(token=agent_config.slack_bot_token)
        await slack.chat_postMessage(
            channel=agent_config.morning_brief_channel_id,
            text=briefing_with_header,
        )
        logger.info(
            "morning_briefing_sent",
            channel=agent_config.morning_brief_channel_id,
            event_count=len(events),
        )

    except Exception as e:
        logger.error(
            "morning_briefing_failed",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_morning_briefing())
