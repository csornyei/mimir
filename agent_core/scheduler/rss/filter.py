import json
import re
from typing import Any

from agent_core.llm.client import llm_client
from agent_core.prompts import render_rss_filter_system, render_rss_filter_user
from shared.logger import logger


def _build_prompt(
    entries: list[dict[str, Any]],
    semantic_memory: str,
    feedback_summary: str,
    n_picks: int,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": render_rss_filter_system(n_picks=n_picks)},
        {
            "role": "user",
            "content": render_rss_filter_user(
                entries=entries,
                semantic_memory=semantic_memory,
                feedback_summary=feedback_summary,
                n_picks=n_picks,
            ),
        },
    ]


def _parse_picks(content: str) -> list[dict[str, Any]]:
    stripped = re.sub(
        r"```(?:json)?\n?(.*?)```", r"\1", content, flags=re.DOTALL
    ).strip()
    try:
        result = json.loads(stripped)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    start = stripped.find("[")
    end = stripped.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            result = json.loads(stripped[start : end + 1])
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
    logger.warning(
        "rss_filter_parse_failed", preview=content[:200], content_length=len(content)
    )
    return []


async def llm_filter(
    entries: list[dict[str, Any]],
    semantic_memory: str,
    feedback_summary: str,
    n_picks: int,
) -> list[dict[str, Any]]:
    messages = _build_prompt(entries, semantic_memory, feedback_summary, n_picks)
    response = await llm_client.complete(messages=messages)
    return _parse_picks(response["content"])
