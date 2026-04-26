from datetime import UTC, datetime
from typing import Any

from slack_sdk.web.async_client import AsyncWebClient

from mimir.interfaces.slack.config import slack_config
from mimir.logger import logger


async def post_digest_header(channel_id: str, n_scanned: int, n_picks: int) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    text = f"*RSS Digest — {now}*\nScanned {n_scanned} articles · selected {n_picks} for you."
    slack = AsyncWebClient(token=slack_config.slack_bot_token)
    response = await slack.chat_postMessage(channel=channel_id, text=text)
    logger.info(
        "rss_digest_header_posted",
        channel_id=channel_id,
        n_scanned=n_scanned,
        n_picks=n_picks,
    )
    return response["ts"]


async def post_pick(channel_id: str, thread_ts: str, pick: dict[str, Any]) -> str:
    title = pick.get("title") or "(no title)"
    url = pick.get("url") or ""
    reason = pick.get("reason", "")
    text = f"<{url}|{title}>\n_{reason}_" if url else f"{title}\n_{reason}_"
    slack = AsyncWebClient(token=slack_config.slack_bot_token)
    response = await slack.chat_postMessage(
        channel=channel_id,
        thread_ts=thread_ts,
        text=text,
    )
    logger.debug(
        "rss_digest_pick_posted",
        channel_id=channel_id,
        thread_ts=thread_ts,
        title=title,
    )
    return response["ts"]
