import json
import re
from typing import Any

from mimir.llm.client import llm_client
from mimir.logger import logger


def _build_prompt(
    entries: list[dict[str, Any]],
    semantic_memory: str,
    feedback_summary: str,
    n_picks: int,
) -> list[dict[str, str]]:
    entry_lines = []
    for e in entries:
        feed = e.get("feed_name") or "Unknown"
        cat = e.get("category") or "Unknown"
        line = f"[{e['id']}] {e['title']} ({feed} / {cat})"
        if e.get("summary"):
            line += f"\n    {e['summary'][:200]}"
        entry_lines.append(line)

    system = (
        "You are Mimir, a personal AI assistant. "
        f"Select up to {n_picks} articles most likely to interest the user. "
        "Return ONLY a valid JSON array — no prose, no markdown fences. "
        'Each element must have keys: "id" (integer), "title" (string), "url" (string), "reason" (one sentence string).'
    )

    user_parts: list[str] = []
    if semantic_memory:
        user_parts.append(f"## About the user\n{semantic_memory}")
    if feedback_summary and feedback_summary != "No feedback recorded yet.":
        user_parts.append(f"## Past feedback\n{feedback_summary}")
    user_parts.append("## Articles to consider\n" + "\n".join(entry_lines))
    user_parts.append(f"Select up to {n_picks} articles. Return the JSON array.")

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]


def _parse_picks(content: str) -> list[dict[str, Any]]:
    stripped = re.sub(
        r"```(?:json)?\n?(.*?)```", r"\1", content, flags=re.DOTALL
    ).strip()
    # Try direct parse first
    try:
        result = json.loads(stripped)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    # Fall back to extracting the first JSON array from the content
    start = stripped.find("[")
    end = stripped.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            result = json.loads(stripped[start : end + 1])
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
    logger.warning("rss_filter_parse_failed", preview=content[:200])
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
