import argparse
import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import SpanKind, StatusCode

from shared.external.rss.client import RSSClient
from shared.logger import logger
from shared.telemetry import setup_tracing
from shared.tokens import truncate_to_tokens
from workflows.config import workflow_config as config

setup_tracing(service_name=config.service_name)

_tracer = trace.get_tracer("mimir.workflows.rss_digest.fetcher")


def validate_config() -> bool:
    required = [
        ("miniflux_url", config.miniflux_url),
        ("miniflux_username", config.miniflux_username),
        ("miniflux_password", config.miniflux_password),
    ]
    missing = [name for name, value in required if not value]
    if missing:
        logger.warning(
            "rss_fetcher_skipped",
            reason=f"Missing required config fields: {', '.join(missing)}",
        )
        return False
    return True


def _to_article(entry: dict[str, Any]) -> dict[str, Any]:
    content = entry.get("content") or entry.get("summary") or ""
    return {
        "id": entry["id"],
        "title": entry["title"],
        "url": entry["url"],
        "feed_name": entry.get("feed_name"),
        "category": entry.get("category"),
        "content": truncate_to_tokens(content, config.rss_article_max_tokens),
    }


async def fetch(
    window_start: datetime, window_end: datetime, window_label: str
) -> list[dict[str, Any]]:
    with _tracer.start_as_current_span(
        "fetch_rss_entries", kind=SpanKind.INTERNAL
    ) as span:
        span.set_attribute("window", window_label)
        rss = RSSClient(
            url=config.miniflux_url,
            username=config.miniflux_username,
            password=config.miniflux_password,
        )
        try:
            entries = await rss.get_entries(window_start, window_end)
        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(
                "rss_fetcher_failed",
                window=window_label,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            return []
        span.set_attribute("entry_count", len(entries))

    articles = [_to_article(e) for e in entries]
    logger.info("rss_fetcher_done", window=window_label, article_count=len(articles))
    return articles


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RSS digest fetcher pod")
    parser.add_argument(
        "--start", type=int, required=True, help="Window start hour (UTC, 0-23)"
    )
    parser.add_argument(
        "--end", type=int, required=True, help="Window end hour (UTC, 0-23)"
    )
    parser.add_argument("--label", type=str, help="Window label (e.g. '08-12')")
    parser.add_argument(
        "--output",
        type=str,
        default="/tmp/articles.json",
        help="Path to write the articles JSON list",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    now = datetime.now(UTC)
    w_end = now.replace(hour=args.end, minute=0, second=0, microsecond=0)
    w_start = now.replace(hour=args.start, minute=0, second=0, microsecond=0)
    if args.start > args.end:  # window crosses midnight
        w_end += timedelta(days=1)
    w_label = args.label or f"{args.start:02d}-{args.end:02d}"

    if not validate_config():
        articles: list[dict[str, Any]] = []
    else:
        articles = asyncio.run(fetch(w_start, w_end, w_label))

    Path(args.output).write_text(json.dumps(articles), encoding="utf-8")


if __name__ == "__main__":
    main()
