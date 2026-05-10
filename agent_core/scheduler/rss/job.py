from datetime import UTC, datetime
from typing import Any

from slack_sdk.web.async_client import AsyncWebClient

from agent_core.config import agent_config
from shared.db import get_session
from shared.external.ntfy import send_ntfy
from shared.external.rss.client import RSSClient
from shared.logger import logger
from agent_core.memory.semantic import SemanticMemory
from shared.models import RssDigestEntry
from shared.reactions import summarise_feedback
from agent_core.scheduler.rss.filter import llm_filter


async def post_digest_header(channel_id: str, n_scanned: int, n_picks: int) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    text = f"*RSS Digest — {now}*\nScanned {n_scanned} articles · selected {n_picks} for you."
    slack = AsyncWebClient(token=agent_config.slack_bot_token)
    response = await slack.chat_postMessage(channel=channel_id, text=text)
    logger.info(
        "rss_digest_header_posted",
        channel_id=channel_id,
        n_scanned=n_scanned,
        n_picks=n_picks,
    )
    return response["ts"]


async def post_pick(
    channel_id: str, thread_ts: str, pick: dict[str, Any], url: str
) -> str:
    title = pick.get("title") or "(no title)"
    reason = pick.get("reason", "")
    text = f"<{url}|{title}>\n_{reason}_" if url else f"{title}\n_{reason}_"
    slack = AsyncWebClient(token=agent_config.slack_bot_token)
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


async def run_digest(
    window_start: datetime, window_end: datetime, window_label: str
) -> None:
    if not agent_config.newspaper_channel_id:
        logger.warning(
            "rss_digest_skipped", reason="NEWSPAPER_CHANNEL_ID not configured"
        )
        return
    if not all(
        [
            agent_config.miniflux_url,
            agent_config.miniflux_username,
            agent_config.miniflux_password,
        ]
    ):
        logger.warning(
            "rss_digest_skipped", reason="Miniflux credentials not fully configured"
        )
        return

    try:
        rss = RSSClient(
            url=agent_config.miniflux_url,
            username=agent_config.miniflux_username,
            password=agent_config.miniflux_password,
        )
        entries = await rss.get_entries(window_start, window_end)

        if len(entries) < agent_config.rss_digest_min_entries:
            logger.info(
                "rss_digest_skipped",
                reason="below_threshold",
                count=len(entries),
                threshold=agent_config.rss_digest_min_entries,
            )
            return

        feedback_summary = await summarise_feedback()
        semantic_memory = SemanticMemory().read()

        picks = await llm_filter(
            entries=entries,
            semantic_memory=semantic_memory,
            feedback_summary=feedback_summary,
            n_picks=agent_config.rss_digest_picks,
        )

        if not picks:
            logger.warning("rss_digest_no_picks", entry_count=len(entries))
            return

        thread_ts = await post_digest_header(
            agent_config.newspaper_channel_id, len(entries), len(picks)
        )

        entries_by_id: dict[int, dict[str, Any]] = {e["id"]: e for e in entries}
        now = datetime.now(UTC)

        for pick in picks:
            pick_id = pick.get("id", 0)
            if pick_id not in entries_by_id:
                logger.warning("rss_digest_pick_id_not_found", pick_id=pick_id)
                continue
            source = entries_by_id[pick_id]
            raw_url = source.get("url", "")
            if raw_url.startswith("https"):
                verified_url = raw_url
            else:
                verified_url = f"{agent_config.miniflux_url}/unread/entry/{pick_id}"
            message_ts = await post_pick(
                agent_config.newspaper_channel_id, thread_ts, pick, verified_url
            )
            async with get_session() as session:
                session.add(
                    RssDigestEntry(
                        miniflux_entry_id=pick_id,
                        title=pick.get("title", ""),
                        url=verified_url,
                        feed_name=source.get("feed_name"),
                        category=source.get("category"),
                        digest_run_at=now,
                        window=window_label,
                        slack_channel_id=agent_config.newspaper_channel_id,
                        slack_message_ts=message_ts,
                    )
                )

        logger.info(
            "rss_digest_sent",
            window=window_label,
            entry_count=len(entries),
            pick_count=len(picks),
        )

        if agent_config.ntfy_url and agent_config.ntfy_digest_topic:
            click = (
                f"{agent_config.mimir_host}/digest" if agent_config.mimir_host else None
            )
            await send_ntfy(
                url=agent_config.ntfy_url,
                topic=agent_config.ntfy_digest_topic,
                message=(
                    f"Mimir: new reads digest for {window_label}. "
                    f"Scanned {len(entries)} articles and selected {len(picks)} for you!"
                ),
                title="Mimir - News Digest",
                click_url=click,
                tags="newspaper_roll",
            )

    except Exception as e:
        logger.error(
            "rss_digest_failed",
            window=window_label,
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

        now = datetime.now(UTC)
        window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        window_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        await run_digest(window_start, window_end, "today")

        await dispose_db()

    asyncio.run(main())
