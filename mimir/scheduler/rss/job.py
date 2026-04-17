from datetime import UTC, datetime
from typing import Any

from mimir.config import config
from mimir.db import get_session
from mimir.external.rss.client import RSSClient
from mimir.logger import logger
from mimir.memory.semantic import SemanticMemory
from mimir.models import RssDigestEntry
from mimir.scheduler.rss.feedback import summarise_feedback
from mimir.scheduler.rss.filter import llm_filter
from mimir.scheduler.rss.slack import post_digest_header, post_pick


async def run_digest(
    window_start: datetime, window_end: datetime, window_label: str
) -> None:
    if not config.newspaper_channel_id:
        logger.warning(
            "rss_digest_skipped", reason="NEWSPAPER_CHANNEL_ID not configured"
        )
        return
    if not all(
        [config.miniflux_url, config.miniflux_username, config.miniflux_password]
    ):
        logger.warning(
            "rss_digest_skipped", reason="Miniflux credentials not fully configured"
        )
        return

    try:
        rss = RSSClient(
            url=config.miniflux_url,
            username=config.miniflux_username,
            password=config.miniflux_password,
        )
        entries = await rss.get_entries(window_start, window_end)

        if len(entries) < config.rss_digest_min_entries:
            logger.info(
                "rss_digest_skipped",
                reason="below_threshold",
                count=len(entries),
                threshold=config.rss_digest_min_entries,
            )
            return

        feedback_summary = await summarise_feedback()
        semantic_memory = SemanticMemory().read()

        picks = await llm_filter(
            entries=entries,
            semantic_memory=semantic_memory,
            feedback_summary=feedback_summary,
            n_picks=config.rss_digest_picks,
        )

        if not picks:
            logger.warning("rss_digest_no_picks", entry_count=len(entries))
            return

        thread_ts = await post_digest_header(
            config.newspaper_channel_id, len(entries), len(picks)
        )

        entries_by_id: dict[int, dict[str, Any]] = {e["id"]: e for e in entries}
        now = datetime.now(UTC)

        for pick in picks:
            pick_id = pick.get("id", 0)
            if pick_id not in entries_by_id:
                logger.warning("rss_digest_pick_id_not_found", pick_id=pick_id)
                continue
            message_ts = await post_pick(config.newspaper_channel_id, thread_ts, pick)
            source = entries_by_id[pick_id]
            async with get_session() as session:
                session.add(
                    RssDigestEntry(
                        miniflux_entry_id=pick_id,
                        title=pick.get("title", ""),
                        url=pick.get("url", ""),
                        feed_name=source.get("feed_name"),
                        category=source.get("category"),
                        digest_run_at=now,
                        window=window_label,
                        slack_channel_id=config.newspaper_channel_id,
                        slack_message_ts=message_ts,
                    )
                )

        logger.info(
            "rss_digest_sent",
            window=window_label,
            entry_count=len(entries),
            pick_count=len(picks),
        )

    except Exception as e:
        logger.error("rss_digest_failed", window=window_label, error=str(e))
