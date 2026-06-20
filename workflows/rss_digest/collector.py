import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import SpanKind

from shared.db import dispose_db, get_session, initialize_db
from shared.external.ntfy import send_ntfy
from shared.logger import logger
from shared.models import RssDigestEntry
from shared.telemetry import setup_tracing
from workflows.config import workflow_config as config

_tracer = trace.get_tracer("mimir.workflows.rss_digest.collector")


def validate_config() -> bool:
    if not config.database_url:
        logger.warning("rss_collector_skipped", reason="Missing database_url")
        return False
    return True


def _passes_threshold(summary: dict[str, Any]) -> bool:
    threshold = config.rss_digest_score_threshold
    interesting = summary.get("interesting_score")
    relevance = summary.get("relevance_score")
    if interesting is None or relevance is None:
        return False
    return interesting >= threshold and relevance >= threshold


def _resolve_url(summary: dict[str, Any]) -> str:
    url = summary.get("url") or ""
    if url.startswith("http"):
        return url
    return f"{config.miniflux_url}/unread/entry/{summary.get('id', 0)}"


async def collect(summaries: list[dict[str, Any]], window_label: str) -> int:
    picks = [s for s in summaries if _passes_threshold(s)]
    now = datetime.now(UTC)

    with _tracer.start_as_current_span("store_digest_entries", kind=SpanKind.INTERNAL):
        async with get_session() as session:
            for pick in picks:
                session.add(
                    RssDigestEntry(
                        miniflux_entry_id=pick.get("id", 0),
                        title=pick.get("title", ""),
                        url=_resolve_url(pick),
                        feed_name=pick.get("feed_name"),
                        category=pick.get("category"),
                        digest_run_at=now,
                        window=window_label,
                        summary=pick.get("summary"),
                        tags=pick.get("tags"),
                        interesting_score=pick.get("interesting_score"),
                        relevance_score=pick.get("relevance_score"),
                    )
                )
            await session.commit()

    logger.info(
        "rss_collector_stored",
        window=window_label,
        input_count=len(summaries),
        stored_count=len(picks),
    )

    if picks and config.ntfy_url and config.ntfy_digest_topic:
        click = f"{config.mimir_host}/digest" if config.mimir_host else None
        await send_ntfy(
            url=config.ntfy_url,
            topic=config.ntfy_digest_topic,
            message=(
                f"Mimir: new reads digest for {window_label}. "
                f"Picked {len(picks)} of {len(summaries)} summarised articles!"
            ),
            title="Mimir - News Digest",
            click_url=click,
            tags="newspaper_roll",
        )
    return len(picks)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RSS digest collector pod")
    parser.add_argument(
        "--input",
        type=str,
        default="/tmp/summaries.json",
        help="Path to the summaries JSON list",
    )
    parser.add_argument("--label", type=str, help="Window label (e.g. '08-12')")
    return parser.parse_args()


def main() -> None:
    setup_tracing(service_name=config.service_name)
    args = _parse_args()
    if not validate_config():
        return
    summaries: list[dict[str, Any]] = json.loads(
        Path(args.input).read_text(encoding="utf-8")
    )
    window_label = args.label or "unknown"

    async def _run() -> None:
        initialize_db(config.database_url)
        try:
            await collect(summaries, window_label)
        finally:
            await dispose_db()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
