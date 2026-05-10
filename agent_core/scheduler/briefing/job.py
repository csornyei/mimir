from datetime import UTC, datetime

from slack_sdk.web.async_client import AsyncWebClient

from agent_core.config import agent_config
from agent_core.agent.conversation import conversation_manager
from shared.db import get_session
from shared.external.caldav.client import CalDAVClient
from shared.external.ntfy import send_ntfy
from shared.external.weather.weather import get_weather_data
from agent_core.llm.client import llm_client
from shared.logger import logger
from agent_core.scheduler.briefing.prompt import build_morning_prompt


async def run_morning_briefing() -> None:
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
        today_date = now.date().isoformat()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)

        client = CalDAVClient(
            url=agent_config.caldav_url,
            username=agent_config.caldav_username,
            password=agent_config.caldav_password,
        )
        events = await client.get_events(today_start, today_end)
        todos = await client.get_todos(today_end)

        weather_data = None
        if agent_config.weather_config_path:
            weather_data = await get_weather_data(agent_config.weather_config_path)

        messages = build_morning_prompt(events, weather_data, todos)
        response = await llm_client.complete(messages=messages)
        briefing_text = response.get("content", "")

        # Persist to DB — both the user prompt and the assistant response
        conversation_id = f"morning|{today_date}"
        user_prompt_content = messages[-1]["content"] if messages else ""
        async with get_session() as session:
            await conversation_manager.get_or_create_conversation(
                session, conversation_id
            )
            await conversation_manager.add_message(
                session, conversation_id, "user", user_prompt_content
            )
            await conversation_manager.add_message(
                session, conversation_id, "assistant", briefing_text
            )

        logger.info(
            "morning_briefing_persisted",
            conversation_id=conversation_id,
        )

        # ntfy notification
        if agent_config.ntfy_url and agent_config.ntfy_morning_brief_topic:
            click = (
                f"{agent_config.mimir_host}/brief" if agent_config.mimir_host else None
            )
            await send_ntfy(
                url=agent_config.ntfy_url,
                topic=agent_config.ntfy_morning_brief_topic,
                message=f"Mimir: your morning brief for {today_date} is ready",
                title="Mimir - Morning Brief",
                click_url=click,
                tags="sunrise_over_mountains",
            )

        # Slack — best-effort, failure does not affect the above
        if agent_config.morning_brief_channel_id and agent_config.slack_bot_token:
            try:
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
                    "morning_briefing_sent_to_slack",
                    channel=agent_config.morning_brief_channel_id,
                    event_count=len(events),
                )
            except Exception as slack_exc:
                logger.warning(
                    "morning_briefing_slack_failed",
                    error=str(slack_exc),
                    error_type=type(slack_exc).__name__,
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
    from shared.db import initialize_db, dispose_db
    from shared.config import shared_config

    async def main():
        initialize_db(shared_config.database_url)

        await run_morning_briefing()

        await dispose_db()

    asyncio.run(main())
