import argparse
import asyncio
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from opentelemetry import trace
from opentelemetry.trace import SpanKind
from sqlalchemy import select, text

from shared.db import dispose_db, get_session, initialize_db
from shared.db_errors import (
    DatabaseConnectionError,
    database_error_context,
    is_database_error,
    to_database_connection_error,
)
from shared.file_api import get_file_api_client
from shared.logger import logger
from shared.models import HealthAnalysis
from shared.prompts.loader import render
from shared.schemas import LLMSettings, Message, RawChatRequest
from shared.telemetry import setup_tracing
from workflows.config import workflow_config as config
from workflows.health_coach.dates import parse_week_start

setup_tracing(service_name=config.service_name)
_tracer = trace.get_tracer("mimir.workflows.health_coach.summarize")
_DB_SECRET_REF = "mimir-db-secret/postgres-url in the argo namespace"
_WORKFLOW_NAME = "Health summarize"


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


def _require_config() -> None:
    if not validate_config():
        raise RuntimeError("Health summarize missing required configuration")


def get_week_start(tz: str) -> date:
    today = datetime.now(ZoneInfo(tz)).date()
    return today - timedelta(days=today.weekday()) - timedelta(weeks=1)


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

        try:
            async with get_session() as session:
                await session.execute(text("SELECT 1"))
        except Exception as exc:
            logger.error(
                "health_summarize_database_failed",
                **database_error_context(
                    database_url=config.database_url,
                    exc=exc,
                    workflow_name=_WORKFLOW_NAME,
                    secret_ref=_DB_SECRET_REF,
                ),
            )
            raise to_database_connection_error(
                database_url=config.database_url,
                exc=exc,
                workflow_name=_WORKFLOW_NAME,
                secret_ref=_DB_SECRET_REF,
            ) from None

        analysis = await get_analysis(week_start)
        if analysis is None:
            logger.error(
                "health_summarize_no_analysis",
                week_start=str(week_start),
            )
            raise RuntimeError(f"No health analysis found for {week_start}")

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
        default=None,
        help="ISO date (YYYY-MM-DD) of the week to summarize. Defaults to last completed week.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    _require_config()

    parsed_week_start: date | None = None
    if args.week_start is not None:
        try:
            parsed_week_start = parse_week_start(args.week_start)
        except ValueError as exc:
            logger.error(
                "health_summarize_invalid_date", date=args.week_start, error=str(exc)
            )
            raise
    if parsed_week_start is not None:
        week_start = parsed_week_start
    else:
        week_start = get_week_start(config.timezone or "UTC")

    async def _run() -> None:
        try:
            initialize_db(config.database_url)
        except Exception as exc:
            logger.error(
                "health_summarize_database_init_failed",
                **database_error_context(
                    database_url=config.database_url,
                    exc=exc,
                    workflow_name=_WORKFLOW_NAME,
                    secret_ref=_DB_SECRET_REF,
                ),
            )
            raise to_database_connection_error(
                database_url=config.database_url,
                exc=exc,
                workflow_name=_WORKFLOW_NAME,
                secret_ref=_DB_SECRET_REF,
            ) from None
        try:
            await run(week_start)
        except DatabaseConnectionError as e:
            logger.error(
                "health_summarize_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise
        except Exception as e:
            if is_database_error(e):
                logger.error(
                    "health_summarize_database_failed",
                    **database_error_context(
                        database_url=config.database_url,
                        exc=e,
                        workflow_name=_WORKFLOW_NAME,
                        secret_ref=_DB_SECRET_REF,
                    ),
                )
                db_error = to_database_connection_error(
                    database_url=config.database_url,
                    exc=e,
                    workflow_name=_WORKFLOW_NAME,
                    secret_ref=_DB_SECRET_REF,
                )
                logger.error(
                    "health_summarize_failed",
                    error=str(db_error),
                    error_type=type(db_error).__name__,
                )
                raise db_error from None
            logger.error(
                "health_summarize_failed",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            raise
        finally:
            await dispose_db()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
