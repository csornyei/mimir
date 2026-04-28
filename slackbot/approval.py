from typing import Any

import httpx

from slackbot.config import slack_config
from slackbot.utils import get_bot_user_id
from shared.logger import logger


def _base_emoji(reaction: str) -> str:
    """Strip skin-tone and other variant suffixes, e.g. '+1::skin-tone-2' → '+1'."""
    return reaction.split("::")[0]


def format_approval_message(payload: dict) -> str:
    description = payload.get("description", "perform an action")
    return (
        f"I'd like to {description}.\n\n"
        "✅ to go ahead · ❌ to cancel · or reply here to discuss"
    )


async def on_reaction_added(event: dict, client: Any) -> None:
    logger.debug(
        "reaction_added_event",
        reaction=event.get("reaction"),
        user=event.get("user"),
    )

    bot_id = await get_bot_user_id(client)
    if event.get("user") == bot_id:
        return

    item = event.get("item", {})
    if item.get("type") != "message":
        return

    base = _base_emoji(event["reaction"])
    message_ts: str = item["ts"]
    user_id: str = event["user"]

    try:
        async with httpx.AsyncClient(timeout=30) as http:
            await http.post(
                f"{slack_config.agent_url}/api/approvals/reaction",
                json={"message_ts": message_ts, "reaction": base, "user_id": user_id},
            )
    except Exception as e:
        logger.error("approval_reaction_failed", error=str(e))


async def on_thread_reply(event: dict, say: Any, client: Any) -> bool:
    thread_ts: str | None = event.get("thread_ts")
    if not thread_ts:
        return False

    try:
        async with httpx.AsyncClient(timeout=120) as http:
            response = await http.post(
                f"{slack_config.agent_url}/api/approvals/reply",
                json={
                    "thread_ts": thread_ts,
                    "text": event.get("text", ""),
                    "user_id": event["user"],
                },
            )
            response.raise_for_status()
            result = response.json()
    except Exception as e:
        logger.error("approval_reply_failed", error=str(e))
        return False

    consumed = result.get("consumed", False)
    reply = result.get("reply")
    if consumed and reply:
        await say(text=reply, thread_ts=thread_ts)
    return consumed
