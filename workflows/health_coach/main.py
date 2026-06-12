import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from opentelemetry import trace
from opentelemetry.trace import SpanKind

from shared.external.ntfy import send_ntfy
from shared.logger import logger
from shared.prompts.loader import render
from shared.schemas import LLMSettings, Message, RawChatRequest
from shared.telemetry import setup_tracing
from workflows.config import workflow_config as config

setup_tracing(service_name=config.service_name)

_tracer = trace.get_tracer("mimir.workflows.health_coach")

COACH_TYPES = {"week": {"prompt": "health_coach_weekly.j2", "summary_type": "week"}}


def validate_config() -> bool:
    required = [
        ("health_coach_endpoint_url", config.health_coach_endpoint_url),
        ("agent_core_api_url", config.agent_core_api_url),
        ("health_coach_type", config.health_coach_type),
    ]
    missing = [name for name, value in required if not value]
    if missing:
        logger.warning(
            "health_coach_skipped",
            reason=f"Missing required config fields: {', '.join(missing)}",
        )
        return False
    return True


async def fetch_fitness_data(endpoint_url: str, summary_type: str) -> str:
    with _tracer.start_as_current_span(
        "fetch_fitness_data", kind=SpanKind.CLIENT
    ) as span:
        base_url = f"{endpoint_url}/api/v1/health/summary"

        today = datetime.now(ZoneInfo(config.timezone or "UTC")).date().isoformat()

        span.set_attribute("endpoint_url", base_url)
        span.set_attribute("end_date", today)
        span.set_attribute("summary_type", summary_type)
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                base_url,
                params={"end_date": today, "summary_type": summary_type},
            )
        response.raise_for_status()
    try:
        return json.dumps(response.json(), indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        return response.text


def _build_messages(template: str, data: str) -> list[dict[str, str]]:
    return [
        {
            "role": "user",
            "content": render(
                template,
                data=data,
                user=config.owner_name,
            ),
        }
    ]


async def send_notification() -> None:
    if not config.ntfy_url:
        return
    click = f"{config.mimir_host}/" if config.mimir_host else None
    await send_ntfy(
        url=config.ntfy_url,
        topic=config.ntfy_health_topic,
        message="Mimir: your health coach update is ready",
        title="Mimir - Health Coach",
        click_url=click,
        tags="muscle",
    )


async def run_health_coach() -> None:
    if not validate_config():
        return

    # Guaranteed non-None by validate_config; narrow for the type checker.
    assert config.health_coach_endpoint_url is not None
    assert config.agent_core_api_url is not None

    coaching_type = None
    if not config.health_coach_type or config.health_coach_type not in COACH_TYPES:
        coaching_type = COACH_TYPES["week"]
    else:
        coaching_type = COACH_TYPES[config.health_coach_type]

    logger.info(
        "health_coach_started",
    )

    try:
        data = await fetch_fitness_data(
            config.health_coach_endpoint_url, summary_type=coaching_type["summary_type"]
        )

        today = datetime.now(UTC).date().isoformat()
        messages: list[dict[str, Any]] = _build_messages(coaching_type["prompt"], data)
        payload = RawChatRequest(
            conversation_id=f"health_coach|{today}",
            user_id="health_coach_job",
            messages=[Message(**m) for m in messages],
            llm_parameters=LLMSettings(
                mode="balanced",
                model=config.llm_model,
                enable_thinking=False,
                thinking_budget=0,
                temperature=0.5,
                max_tokens=1000,
            ),
        )

        with _tracer.start_as_current_span(
            "call_agent_core_api", kind=SpanKind.CLIENT
        ) as span:
            span.set_attribute(
                "agent_core_api_url", config.agent_core_api_url or "none"
            )
            async with httpx.AsyncClient(
                base_url=config.agent_core_api_url, timeout=300.0
            ) as client:
                response = await client.post("/api/raw", json=payload.model_dump())
            response.raise_for_status()

        logger.info("health_coach_persisted", date=today)

        await send_notification()

    except Exception as e:
        logger.error(
            "health_coach_failed",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )


if __name__ == "__main__":
    asyncio.run(run_health_coach())
