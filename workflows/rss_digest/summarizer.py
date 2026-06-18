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

setup_tracing(service_name=config.service_name)

_tracer = trace.get_tracer("mimir.workflows.rss_digest.summarizer")

_PASSTHROUGH_KEYS = ("id", "title", "url", "feed_name", "category")


def validate_config() -> bool:
    if not config.agent_core_api_url:
        logger.warning("rss_summarizer_skipped", reason="Missing agent_core_api_url")
        return False
    return True


async def _load_semantic_memory() -> str:
    vault_path = config.semantic_memory_path.removeprefix("vault/")
    return await get_file_api_client().read_file(vault_path)


def _extract_json_object(content: str) -> dict[str, Any] | None:
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
    client: httpx.AsyncClient, article: dict[str, Any], semantic_memory: str
) -> dict[str, Any] | None:
    messages = build_summarize_prompt(article, semantic_memory)
    payload = RawChatRequest(
        conversation_id=f"rss_summarize|{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}|{article['id']}",
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


async def summarize(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Guaranteed non-None by validate_config; narrow for the type checker.
    assert config.agent_core_api_url is not None
    semantic_memory = await _load_semantic_memory()
    summaries: list[dict[str, Any]] = []
    async with httpx.AsyncClient(
        base_url=config.agent_core_api_url, timeout=300.0
    ) as client:
        for article in articles:
            with _tracer.start_as_current_span(
                "summarize_article", kind=SpanKind.CLIENT
            ) as span:
                span.set_attribute("article_id", article.get("id", 0))
                try:
                    result = await _summarize_one(client, article, semantic_memory)
                except Exception as e:
                    span.set_status(StatusCode.ERROR, str(e))
                    logger.error(
                        "rss_summarizer_article_failed",
                        article_id=article.get("id"),
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    continue
            if result is not None:
                summaries.append(result)
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
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    articles: list[dict[str, Any]] = json.loads(
        Path(args.input).read_text(encoding="utf-8")
    )

    if not validate_config():
        summaries: list[dict[str, Any]] = []
    else:
        summaries = asyncio.run(summarize(articles))

    Path(args.output).write_text(json.dumps(summaries), encoding="utf-8")


if __name__ == "__main__":
    main()
