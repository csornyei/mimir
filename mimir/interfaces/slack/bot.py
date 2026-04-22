import asyncio
import time
from typing import Any

from slack_bolt.async_app import AsyncApp

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from mimir.interfaces.slack import approval as slack_approval
from mimir.scheduler.rss import feedback as rss_feedback
from mimir.agent import client as agent_client
from mimir.db import initialize_db, dispose_db
from mimir.interfaces.slack.config import slack_config
from mimir.interfaces.slack.utils import get_bot_user_id
from mimir.logger import logger
from mimir.telemetry import setup_tracing, slack_span

setup_tracing(service_name="mimir-slack-bot")

app = AsyncApp(token=slack_config.slack_bot_token)


def _conversation_id(event: dict) -> str:
    """Return a composite '{channel}|{thread_ts}' conversation ID.

    Threads use thread_ts; top-level messages use their own ts.
    This works for both channels and DMs.
    """
    channel = event["channel"]
    thread_ts = event.get("thread_ts") or event["ts"]
    return f"{channel}|{thread_ts}"


def _should_ignore_message(event: dict) -> bool:
    """Return True if the message should be silently ignored.

    Ignores edits, deletions, and bot-originated messages.
    """
    return bool(event.get("subtype") or event.get("bot_id"))


def _strip_bot_mention(text: str, bot_id: str) -> str:
    """Strip the bot mention prefix from text and strip whitespace."""
    return text.replace(f"<@{bot_id}>", "").strip()


def _is_bot_in_thread(messages: list[dict], bot_id: str, current_ts: str) -> bool:
    """Check if the bot is already participating in a thread.

    Returns True if the bot (either as user or bot_id) appears in the message
    list, excluding the current message.
    """
    return any(
        msg.get("user") == bot_id or msg.get("bot_id") == bot_id
        for msg in messages
        if msg.get("ts") != current_ts
    )


async def _agent_reply(
    *,
    conversation_id: str,
    user_id: str,
    message: str,
    say: Any,
    thread_ts: str | None = None,
) -> bool:
    """Send a message to the agent and post the reply.

    Args:
        conversation_id: The conversation ID for context
        user_id: The Slack user ID
        message: The user's message
        say: Slack say callback (posts a reply)
        thread_ts: Optional thread timestamp to reply in

    Returns:
        True if successful, False if an error occurred.
    """
    try:
        start_time = time.monotonic()
        reply = await agent_client.send_to_agent(
            conversation_id=conversation_id,
            user_id=user_id,
            message=message,
        )
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "agent_reply_sent",
            conversation_id=conversation_id,
            user_id=user_id,
            duration_ms=duration_ms,
        )
        await say(text=reply, thread_ts=thread_ts)
        return True
    except Exception as e:
        logger.error(
            "agent_reply_failed",
            conversation_id=conversation_id,
            user_id=user_id,
            error=str(e),
        )
        await say(
            text="Sorry, something went wrong.",
            thread_ts=thread_ts,
        )
        return False


@app.event("reaction_added")
@slack_span("reaction_added")
async def handle_reaction_added(event: dict, client: Any) -> None:
    logger.debug("received_reaction_added_event", slack_event=event)
    await slack_approval.on_reaction_added(event, client)
    try:
        await rss_feedback.on_digest_reaction(event, client)
    except Exception as e:
        logger.error("rss_feedback_reaction_failed", error=str(e))


@app.event("app_mention")
@slack_span("app_mention")
async def handle_mention(event: dict, say: Any, client: Any) -> None:
    logger.debug("received_mention_event", slack_event=event)
    bot_id = await get_bot_user_id(client)
    text = _strip_bot_mention(event.get("text", ""), bot_id)

    if not text:
        logger.warning(
            "mention_text_empty",
            user=event["user"],
            channel=event["channel"],
        )
        await say(text="I need some text to respond to. Try: `@mimir <your question>`")
        return

    conversation_id = _conversation_id(event)
    thread_ts = event.get("thread_ts") or event["ts"]

    logger.info(
        "mention_received",
        user=event["user"],
        channel=event["channel"],
        conversation_id=conversation_id,
    )

    await _agent_reply(
        conversation_id=conversation_id,
        user_id=event["user"],
        message=text,
        say=say,
        thread_ts=thread_ts,
    )


@app.event("message")
@slack_span("message")
async def handle_message(event: dict, say: Any, client: Any) -> None:
    logger.debug("received_message_event", slack_event=event)

    # Ignore edits, deletions, and bot messages
    if _should_ignore_message(event):
        logger.debug(
            "message_event_ignored",
            subtype=event.get("subtype"),
            bot_id=event.get("bot_id"),
        )
        return

    channel_type = event.get("channel_type")
    thread_ts = event.get("thread_ts")

    # Check if this is a reply in an approval thread
    if thread_ts:
        consumed = await slack_approval.on_thread_reply(event, say, client)
        if consumed:
            logger.debug(
                "thread_reply_consumed_by_approval",
                thread_ts=thread_ts,
                user=event["user"],
            )
            return

    # Handle direct messages
    if channel_type == "im":
        conversation_id = _conversation_id(event)
        logger.info(
            "dm_received",
            user=event["user"],
            channel=event["channel"],
            conversation_id=conversation_id,
        )
        await _agent_reply(
            conversation_id=conversation_id,
            user_id=event["user"],
            message=event.get("text", ""),
            say=say,
        )
        return

    # Handle channel threads (only respond if bot is already in the thread)
    if channel_type in ("channel", "group") and thread_ts:
        history = await client.conversations_replies(
            channel=event["channel"],
            ts=thread_ts,
        )
        bot_id = await get_bot_user_id(client)

        if not _is_bot_in_thread(
            history.get("messages", []),
            bot_id,
            event["ts"],
        ):
            logger.debug(
                "thread_reply_ignored_bot_not_in_thread",
                channel=event["channel"],
                thread_ts=thread_ts,
                user=event["user"],
            )
            return

        conversation_id = _conversation_id(event)
        logger.info(
            "thread_reply_received",
            user=event["user"],
            channel=event["channel"],
            thread_ts=thread_ts,
            conversation_id=conversation_id,
        )

        await _agent_reply(
            conversation_id=conversation_id,
            user_id=event["user"],
            message=event.get("text", ""),
            say=say,
            thread_ts=thread_ts,
        )


async def start():
    logger.debug("configuring_slack_bot", config=slack_config.model_dump())
    logger.info("Starting Slack bot")
    initialize_db(slack_config.database_url)
    handler = AsyncSocketModeHandler(app, slack_config.slack_app_token)
    await handler.start_async()


if __name__ == "__main__":
    try:
        asyncio.run(start())
    finally:
        logger.debug("disposing_db")
        asyncio.run(dispose_db())
