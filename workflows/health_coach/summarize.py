import argparse
import asyncio
from datetime import date

import httpx
from opentelemetry import trace
from opentelemetry.trace import SpanKind
from sqlalchemy import select

from shared.db import dispose_db, get_session, initialize_db
from shared.file_api import get_file_api_client
from shared.logger import logger
from shared.models import HealthAnalysis
from shared.prompts.loader import render
from shared.schemas import LLMSettings, Message, RawChatRequest
from shared.telemetry import setup_tracing
from workflows.config import workflow_config as config

setup_tracing(service_name=config.service_name)
_tracer = trace.get_tracer("mimir.workflows.health_coach.summarize")


def validate_config() -> bool:
    required = [
        ("agent_core_api_url", config.agent_core_api_url),
        ("database_url", config.database_url),
        ("file_api_url", config.file_api_url),
    ]
    missing = [name for name, value in required if not value]
    if missing:
        logger.warning(
            "health_summarize_skipped",
            reason=f"Missing required config: {', '.join(missing)}",
        )
        return False
    return True


async def get_analysis(week_start: date) -> HealthAnalysis | None:
    async with get_session() as session:
        result = await session.execute(
            select(HealthAnalysis).where(HealthAnalysis.week_start == week_start)
        )
        return result.scalar_one_or_none()


async def call_llm(week_start: date, analysis_md: str) -> str:
    assert config.agent_core_api_url is not None
    system_content = render("health_memory_summary_system.j2")
    user_content = render(
        "health_memory_summary_user.j2",
        week_start=str(week_start),
        analysis_md=analysis_md,
    )
    payload = RawChatRequest(
        conversation_id=f"health_summarize|{week_start}",
        user_id="health_coach_job",
        messages=[
            Message(role="system", content=system_content),
            Message(role="user", content=user_content),
        ],
        llm_parameters=LLMSettings(
            mode="balanced",
            model=config.llm_model,
            enable_thinking=False,
            thinking_budget=0,
            temperature=0.3,
            max_tokens=600,
        ),
    )
    with _tracer.start_as_current_span("call_llm_summarize", kind=SpanKind.CLIENT):
        async with httpx.AsyncClient(
            base_url=config.agent_core_api_url, timeout=300.0
        ) as client:
            response = await client.post("/api/raw", json=payload.model_dump())
            response.raise_for_status()
    body = response.json()
    logger.info("llm_response", body=body)
    return body.get("content", "")  # type: ignore[no-any-return]


async def write_memory_file(content: str) -> None:
    await get_file_api_client().save_file(config.health_memory_file_path, content)


async def run(week_start: date) -> None:
    with _tracer.start_as_current_span(
        "health_summarize", kind=SpanKind.INTERNAL
    ) as span:
        span.set_attribute("week_start", str(week_start))

        logger.info("health_summarize", week_start=str(week_start))

        analysis = await get_analysis(week_start)
        if analysis is None:
            logger.error(
                "health_summarize_no_analysis",
                week_start=str(week_start),
            )
            return

        summary_md = await call_llm(week_start, analysis.analysis_md)

        await write_memory_file(summary_md)

        logger.info(
            "health_summarize_done",
            week_start=str(week_start),
            path=config.health_memory_file_path,
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Health coach summarize pod")
    parser.add_argument(
        "--week-start",
        type=str,
        required=True,
        help="ISO date (YYYY-MM-DD) of the week to summarize.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if not validate_config():
        return

    try:
        week_start = date.fromisoformat(args.week_start)
    except ValueError as exc:
        logger.error(
            "health_summarize_invalid_date", date=args.week_start, error=str(exc)
        )
        return

    async def _run() -> None:
        initialize_db(config.database_url)
        try:
            await run(week_start)
        except Exception as e:
            logger.error(
                "health_summarize_failed",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
        finally:
            await dispose_db()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
