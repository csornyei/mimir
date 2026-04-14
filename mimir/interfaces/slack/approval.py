from typing import Any

from mimir.agent.approval import manager
from mimir.db import get_session
from mimir.interfaces.slack.utils import get_bot_user_id
from mimir.logger import logger


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
    logger.info(
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

    async with get_session() as session:
        await manager.handle_reaction(session, base, message_ts, user_id)


async def on_thread_reply(event: dict, say: Any, client: Any) -> bool:
    thread_ts: str | None = event.get("thread_ts")
    if not thread_ts:
        return False

    async with get_session() as session:
        return await manager.handle_thread_reply(
            session,
            thread_ts=thread_ts,
            text=event.get("text", ""),
            user_id=event["user"],
            say=say,
        )
