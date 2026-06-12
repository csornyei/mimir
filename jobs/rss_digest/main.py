import argparse
import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import SpanKind

from jobs.config import job_config
from jobs.rss_digest.filter import llm_filter
from shared.db import dispose_db, get_session, initialize_db
from shared.external.ntfy import send_ntfy
from shared.external.rss.client import RSSClient
from shared.logger import logger
from shared.models import RssDigestEntry
from shared.reactions import summarise_feedback
from shared.telemetry import setup_tracing

setup_tracing(service_name=job_config.service_name)

_tracer = trace.get_tracer("mimir.jobs.rss_digest")


def validate_config() -> bool:
    required = [
        ("miniflux_url", job_config.miniflux_url),
        ("miniflux_username", job_config.miniflux_username),
        ("miniflux_password", job_config.miniflux_password),
        ("agent_core_api_url", job_config.agent_core_api_url),
    ]
    missing = [name for name, value in required if not value]
    if missing:
        logger.warning(
            "rss_digest_skipped",
            reason=f"Missing required config fields: {', '.join(missing)}",
        )
        return False
    return True


async def run_digest(
    window_start: datetime, window_end: datetime, window_label: str
) -> None:
    if not validate_config():
        return

    logger.info(
        "rss_digest_started",
        window=window_label,
        start=window_start.isoformat(),
        end=window_end.isoformat(),
    )

    try:
        with _tracer.start_as_current_span(
            "fetch_rss_entries", kind=SpanKind.INTERNAL
        ) as span:
            span.set_attribute("window", window_label)
            rss = RSSClient(
                url=job_config.miniflux_url,
                username=job_config.miniflux_username,
                password=job_config.miniflux_password,
            )
            entries = await rss.get_entries(window_start, window_end)

        if len(entries) < job_config.rss_digest_min_entries:
            logger.info(
                "rss_digest_skipped",
                reason="below_threshold",
                count=len(entries),
                threshold=job_config.rss_digest_min_entries,
            )
            return

        logger.info(
            "rss_digest_fetched_entries", window=window_label, count=len(entries)
        )

        feedback_summary = await summarise_feedback()

        memory_path = Path(job_config.semantic_memory_path)
        semantic_memory = (
            memory_path.read_text(encoding="utf-8") if memory_path.exists() else ""
        )

        picks = await llm_filter(
            entries=entries,
            semantic_memory=semantic_memory,
            feedback_summary=feedback_summary,
            n_picks=job_config.rss_digest_picks,
        )

        print(picks)

        if not picks:
            logger.warning(
                "rss_digest_no_picks", entry_count=len(entries), window=window_label
            )
            return

        entries_by_id: dict[int, dict[str, Any]] = {e["id"]: e for e in entries}
        now = datetime.now(UTC)

        async with get_session() as session:
            for pick in picks:
                pick_id = pick.get("id", 0)
                if pick_id not in entries_by_id:
                    logger.warning(
                        "rss_digest_pick_id_not_found",
                        pick_id=pick_id,
                        window=window_label,
                    )
                    continue
                source = entries_by_id[pick_id]
                url = source.get("url", "")
                if not url.startswith("https"):
                    url = f"{job_config.miniflux_url}/unread/entry/{pick_id}"
                session.add(
                    RssDigestEntry(
                        miniflux_entry_id=pick_id,
                        title=pick.get("title", ""),
                        url=url,
                        feed_name=source.get("feed_name"),
                        category=source.get("category"),
                        digest_run_at=now,
                        window=window_label,
                    )
                )
            await session.commit()

        logger.info(
            "rss_digest_stored",
            window=window_label,
            entry_count=len(entries),
            pick_count=len(picks),
        )

        if job_config.ntfy_url and job_config.ntfy_digest_topic:
            click = f"{job_config.mimir_host}/digest" if job_config.mimir_host else None
            await send_ntfy(
                url=job_config.ntfy_url,
                topic=job_config.ntfy_digest_topic,
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
    parser = argparse.ArgumentParser(description="Run RSS digest job")
    parser.add_argument(
        "--start", type=int, required=True, help="Window start hour (UTC, 0-23)"
    )
    parser.add_argument(
        "--end", type=int, required=True, help="Window end hour (UTC, 0-23)"
    )
    parser.add_argument(
        "--label", type=str, help="Window label for logging (e.g. '08-12')"
    )
    args = parser.parse_args()

    now = datetime.now(UTC)
    w_end = now.replace(hour=args.end, minute=0, second=0, microsecond=0)
    w_start = now.replace(hour=args.start, minute=0, second=0, microsecond=0)
    if args.start > args.end:  # window crosses midnight
        w_end += timedelta(days=1)
    w_label = args.label or f"{args.start:02d}-{args.end:02d}"

    async def main():
        initialize_db(job_config.database_url)
        try:
            await run_digest(w_start, w_end, w_label)
        finally:
            await dispose_db()

    asyncio.run(main())
