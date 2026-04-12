import asyncio
from typing import Any

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from mimir.agent import client as agent_client
from mimir.config import config
from mimir.interfaces.slack.utils import get_bot_user_id
from mimir.logger import logger

app = AsyncApp(token=config.slack_bot_token)


def _conversation_id(event: dict) -> str:
    """Return a composite '{channel}|{thread_ts}' conversation ID.

    DMs use the message ts as the thread suffix (no persistent thread_ts).
    Channel threads use thread_ts; top-level messages fall back to their own ts.
    """
    channel = event["channel"]
    if event.get("channel_type") == "im":
        return f"{channel}|{event['ts']}"
    thread_ts = event.get("thread_ts") or event["ts"]
    return f"{channel}|{thread_ts}"


@app.event("reaction_added")
async def handle_reaction_added(event: dict, client: Any) -> None:
    from mimir.interfaces.slack import approval as slack_approval

    await slack_approval.on_reaction_added(event, client)


@app.event("app_mention")
async def handle_mention(event: dict, say: Any, client: Any) -> None:
    bot_id = await get_bot_user_id(client)
    text = event.get("text", "").replace(f"<@{bot_id}>", "").strip()

    logger.info("handling_mention", user=event["user"], channel=event["channel"])
    try:
        reply = await agent_client.send_to_agent(
            conversation_id=_conversation_id(event),
            user_id=event["user"],
            message=text,
        )
    except Exception as e:
        logger.error("mention_failed", error=str(e), user=event["user"])
        await say(
            text="Sorry, something went wrong.",
            thread_ts=event.get("thread_ts") or event["ts"],
        )
        return

    await say(text=reply, thread_ts=event.get("thread_ts") or event["ts"])


@app.event("message")
async def handle_message(event: dict, say: Any, client: Any) -> None:
    channel_type = event.get("channel_type")
    subtype = event.get("subtype")
    thread_ts = event.get("thread_ts")

    # ignore edits, deletions, bot messages etc.
    if subtype or event.get("bot_id"):
        return

    # Approval thread intercept — must run before normal channel-thread logic
    if thread_ts:
        from mimir.interfaces.slack import approval as slack_approval

        consumed = await slack_approval.on_thread_reply(event, say, client)
        if consumed:
            return

    # DM: always respond
    if channel_type == "im":
        logger.info("handling_dm", user=event["user"], channel=event["channel"])
        try:
            reply = await agent_client.send_to_agent(
                conversation_id=_conversation_id(event),
                user_id=event["user"],
                message=event.get("text", ""),
            )
        except Exception as e:
            logger.error("dm_failed", error=str(e), user=event["user"])
            await say(text="Sorry, something went wrong.")
            return
        await say(text=reply)
        return

    # Channel Threads: only respond if Mimir is already in the thread
    if channel_type in ("channel", "group") and thread_ts:
        history = await client.conversations_replies(
            channel=event["channel"],
            ts=thread_ts,
        )
        bot_id = await get_bot_user_id(client)

        already_in_thread = any(
            msg.get("user") == bot_id or msg.get("bot_id") == bot_id
            for msg in history.get("messages", [])
            if msg.get("ts") != event["ts"]  # ignore the current message
        )

        if already_in_thread:
            logger.info(
                "handling_thread_reply", user=event["user"], thread_ts=thread_ts
            )
            try:
                reply = await agent_client.send_to_agent(
                    conversation_id=_conversation_id(event),
                    user_id=event["user"],
                    message=event.get("text", ""),
                )
            except Exception as e:
                logger.error("thread_reply_failed", error=str(e), user=event["user"])
                await say(text="Sorry, something went wrong.", thread_ts=thread_ts)
                return
            await say(text=reply, thread_ts=thread_ts)
        return


async def start():
    logger.info("Starting Slack bot")
    handler = AsyncSocketModeHandler(app, config.slack_app_token)
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(start())
