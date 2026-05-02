import asyncio
import time
from typing import Any

import httpx
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from slackbot import approval as slack_approval
from slackbot.reactions import on_digest_reaction
from slackbot.config import slack_config
from slackbot.utils import get_bot_user_id
from shared.db import initialize_db, dispose_db
from shared.logger import logger
from shared.telemetry import setup_tracing, slack_span

setup_tracing(service_name=slack_config.service_name)

app = AsyncApp(token=slack_config.slack_bot_token)


def _conversation_id(event: dict) -> str:
    """Return a composite '{channel}|{thread_ts}' conversation ID."""
    channel = event["channel"]
    thread_ts = event.get("thread_ts") or event["ts"]
    return f"{channel}|{thread_ts}"


def _should_ignore_message(event: dict) -> bool:
    """Return True if the message should be silently ignored."""
    return bool(event.get("subtype") or event.get("bot_id"))


def _strip_bot_mention(text: str, bot_id: str) -> str:
    """Strip the bot mention prefix from text and strip whitespace."""
    return text.replace(f"<@{bot_id}>", "").strip()


def _is_bot_in_thread(messages: list[dict], bot_id: str, current_ts: str) -> bool:
    """Check if the bot is already participating in a thread."""
    return any(
        msg.get("user") == bot_id or msg.get("bot_id") == bot_id
        for msg in messages
        if msg.get("ts") != current_ts
    )


async def _send_to_agent(conversation_id: str, user_id: str, message: str) -> str:
    """POST to agent_core /api/chat and return the reply text."""
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{slack_config.agent_url}/api/chat",
            json={
                "conversation_id": conversation_id,
                "user_id": user_id,
                "message": message,
            },
        )
        response.raise_for_status()
        return response.json()["response"]


async def _agent_reply(
    *,
    conversation_id: str,
    user_id: str,
    message: str,
    say: Any,
    thread_ts: str | None = None,
) -> bool:
    """Send a message to the agent and post the reply."""
    try:
        start_time = time.monotonic()
        reply = await _send_to_agent(conversation_id, user_id, message)

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "agent_reply_sent",
            conversation_id=conversation_id,
            user_id=user_id,
            duration_ms=duration_ms,
        )
        if not reply:
            logger.warning(
                "agent_returned_empty_reply",
                conversation_id=conversation_id,
                user_id=user_id,
            )
            reply = "I wasn't able to generate a response. Please try again."
        await say(text=reply, thread_ts=thread_ts)
        return True
    except Exception as e:
        logger.error(
            "agent_reply_failed",
            conversation_id=conversation_id,
            user_id=user_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
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
        await on_digest_reaction(event, client)
    except Exception as e:
        logger.error(
            "rss_feedback_reaction_failed",
            emoji=event.get("reaction"),
            message_ts=event.get("item", {}).get("ts"),
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )


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

    if _should_ignore_message(event):
        logger.debug(
            "message_event_ignored",
            subtype=event.get("subtype"),
            bot_id=event.get("bot_id"),
        )
        return

    channel_type = event.get("channel_type")
    thread_ts = event.get("thread_ts")

    if thread_ts:
        consumed = await slack_approval.on_thread_reply(event, say, client)
        if consumed:
            logger.debug(
                "thread_reply_consumed_by_approval",
                thread_ts=thread_ts,
                user=event["user"],
            )
            return

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
    logger.info("starting_slack_bot")
    initialize_db(slack_config.database_url)
    handler = AsyncSocketModeHandler(app, slack_config.slack_app_token)
    await handler.start_async()


if __name__ == "__main__":
    try:
        asyncio.run(start())
    finally:
        logger.debug("disposing_db")
        asyncio.run(dispose_db())
