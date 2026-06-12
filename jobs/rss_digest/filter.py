import json
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from jobs.config import job_config
from jobs.rss_digest.prompt import render_rss_filter_system, render_rss_filter_user
from shared.logger import logger
from shared.schemas import LLMSettings, Message, RawChatRequest


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


def _is_list_of_dicts(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(i, dict) for i in value)
    )


def _parse_picks(content: str) -> list[dict[str, Any]]:
    # Search all [...] spans in the content and return the first valid list-of-dicts
    for match in re.finditer(r"\[", content):
        start = match.start()
        # Walk forward to find a balanced closing bracket
        depth = 0
        for i in range(start, len(content)):
            if content[i] == "[":
                depth += 1
            elif content[i] == "]":
                depth -= 1
                if depth == 0:
                    candidate = content[start : i + 1]
                    try:
                        result = json.loads(candidate)
                        if _is_list_of_dicts(result):
                            return result
                    except json.JSONDecodeError:
                        pass
                    break
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
    conversation_id = f"rss_filter|{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"

    payload = RawChatRequest(
        conversation_id=conversation_id,
        user_id="rss_digest_job",
        messages=[Message(**m) for m in messages],
        llm_parameters=LLMSettings(
            mode="fast",
            model=job_config.llm_model,
            enable_thinking=False,
            thinking_budget=0,
            temperature=0.3,
            max_tokens=2500,
            response_format="json",
        ),
    )

    print("llm filter payload", payload.model_dump())

    if not job_config.agent_core_api_url:
        raise ValueError("agent_core_api_url is not configured")

    async with httpx.AsyncClient(
        base_url=job_config.agent_core_api_url, timeout=300.0
    ) as client:
        response = await client.post("/api/raw", json=payload.model_dump())
    response.raise_for_status()

    print("LLM filter response", response.json())

    return _parse_picks(response.json()["content"])
