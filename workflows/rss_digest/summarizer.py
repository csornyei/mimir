import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from opentelemetry import trace
from opentelemetry.trace import SpanKind, StatusCode

from shared.file_api import get_file_api_client
from shared.logger import logger
from shared.schemas import LLMSettings, Message, RawChatRequest
from shared.telemetry import setup_tracing
from workflows.config import workflow_config as config
from workflows.rss_digest.prompt import build_summarize_prompt
from workflows.rss_digest.window import resolve_window

_tracer = trace.get_tracer("mimir.workflows.rss_digest.summarizer")

_PASSTHROUGH_KEYS = ("id", "title", "url", "feed_name", "category")


def validate_config() -> bool:
    if not config.agent_core_api_url:
        logger.warning("rss_summarizer_skipped", reason="Missing agent_core_api_url")
        return False
    if not config.file_api_url:
        logger.warning("rss_summarizer_skipped", reason="Missing file_api_url")
        return False
    return True


def _require_config() -> None:
    if not validate_config():
        raise RuntimeError("RSS summarizer missing required configuration")


async def _load_semantic_memory() -> str:
    return await get_file_api_client().read_file(config.semantic_memory_path)


def _extract_json_object(content: str) -> dict[str, Any] | None:
    try:
        result = json.loads(content.strip())
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Fallback: scan for the first complete JSON object by brace depth.
    for start in (i for i, c in enumerate(content) if c == "{"):
        depth = 0
        for i in range(start, len(content)):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        result = json.loads(content[start : i + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(result, dict):
                        return result
                    break

    logger.warning("rss_summarizer_parse_failed", preview=content[:200])
    return None


async def _summarize_one(
    client: httpx.AsyncClient,
    article: dict[str, Any],
    semantic_memory: str,
    conversation_id: str,
) -> dict[str, Any] | None:
    messages = build_summarize_prompt(article, semantic_memory)
    payload = RawChatRequest(
        conversation_id=conversation_id,
        user_id="rss_digest_summarizer",
        messages=[Message(**m) for m in messages],
        llm_parameters=LLMSettings(
            mode="fast",
            model=config.llm_model,
            enable_thinking=False,
            thinking_budget=0,
            temperature=0.3,
            max_tokens=1200,
            response_format="json",
        ),
    )
    response = await client.post("/api/raw", json=payload.model_dump())
    response.raise_for_status()
    parsed = _extract_json_object(response.json().get("content", ""))
    if parsed is None:
        return None
    return {
        **{key: article.get(key) for key in _PASSTHROUGH_KEYS},
        "summary": parsed.get("summary"),
        "tags": parsed.get("tags"),
        "interesting_score": parsed.get("interesting_score"),
        "relevance_score": parsed.get("relevance_score"),
    }


async def summarize(
    articles: list[dict[str, Any]], conversation_id: str
) -> list[dict[str, Any]]:
    if not config.agent_core_api_url:
        raise RuntimeError("agent_core_api_url is not configured")
    semantic_memory = await _load_semantic_memory()
    sem = asyncio.Semaphore(config.rss_summarizer_concurrency)

    async def _bounded(article: dict[str, Any]) -> dict[str, Any] | None:
        async with sem:
            with _tracer.start_as_current_span(
                "summarize_article", kind=SpanKind.CLIENT
            ) as span:
                span.set_attribute("article_id", article.get("id", 0))
                try:
                    return await _summarize_one(
                        client, article, semantic_memory, conversation_id
                    )
                except Exception as e:
                    span.set_status(StatusCode.ERROR, str(e))
                    logger.error(
                        "rss_summarizer_article_failed",
                        article_id=article.get("id"),
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    return None

    async with httpx.AsyncClient(
        base_url=config.agent_core_api_url, timeout=300.0
    ) as client:
        results = await asyncio.gather(*(_bounded(a) for a in articles))

    summaries = [r for r in results if r is not None]
    logger.info(
        "rss_summarizer_done",
        input_count=len(articles),
        summary_count=len(summaries),
    )
    return summaries


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RSS digest summarizer pod")
    parser.add_argument(
        "--input",
        type=str,
        default="/tmp/articles.json",
        help="Path to the articles JSON list",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="/tmp/summaries.json",
        help="Path to write the summaries JSON list",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=None,
        help="Window start hour (UTC, 0-23). Defaults to the previous window.",
    )
    parser.add_argument(
        "--window-hours",
        type=int,
        default=6,
        help="Window size to infer when --start is omitted.",
    )
    return parser.parse_args()


def main() -> None:
    setup_tracing(service_name=config.service_name)
    args = _parse_args()

    try:
        articles: list[dict[str, Any]] = json.loads(
            Path(args.input).read_text(encoding="utf-8")
        )
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error("rss_summarizer_input_failed", error=str(e), path=args.input)
        raise

    _require_config()
    if args.start is None:
        start_hour = resolve_window(window_hours=args.window_hours).start.hour
    else:
        start_hour = args.start
    conversation_id = (
        f"rss_digest|{datetime.now(UTC).strftime('%Y-%m-%d')}--{start_hour:02d}"
    )
    summaries = asyncio.run(summarize(articles, conversation_id))

    Path(args.output).write_text(json.dumps(summaries), encoding="utf-8")


if __name__ == "__main__":
    main()
