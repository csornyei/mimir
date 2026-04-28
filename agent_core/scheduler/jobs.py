from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from opentelemetry import trace
from opentelemetry.trace import SpanKind, StatusCode

from agent_core.agent.approval import manager as approval_manager
from agent_core.config import agent_config
from shared.db import get_session
from agent_core.scheduler.briefing.job import run_morning_briefing
from agent_core.scheduler.memory.consolidate import consolidate_idle_threads
from agent_core.scheduler.rss.job import run_digest

_tracer = trace.get_tracer("mimir.scheduler.jobs")


async def process_approval_timeouts() -> None:
    with _tracer.start_as_current_span(
        "scheduler.process_approval_timeouts", kind=SpanKind.INTERNAL
    ) as span:
        span.set_attribute("job.name", "process_approval_timeouts")
        try:
            async with get_session() as session:
                await approval_manager.process_timeouts(session)
        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            raise


async def send_morning_briefing() -> None:
    with _tracer.start_as_current_span(
        "scheduler.morning_briefing", kind=SpanKind.INTERNAL
    ) as span:
        span.set_attribute("job.name", "morning_briefing")
        try:
            await run_morning_briefing()
        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            raise


async def send_rss_digest_08() -> None:
    with _tracer.start_as_current_span(
        "scheduler.rss_digest", kind=SpanKind.INTERNAL
    ) as span:
        span.set_attribute("job.name", "rss_digest")
        span.set_attribute("job.window", "20-08")
        try:
            now = datetime.now(UTC)
            end = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if end > now:
                end -= timedelta(days=1)
            start = end - timedelta(hours=12)
            await run_digest(start, end, "20-08")
        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            raise


async def send_rss_digest_12() -> None:
    with _tracer.start_as_current_span(
        "scheduler.rss_digest", kind=SpanKind.INTERNAL
    ) as span:
        span.set_attribute("job.name", "rss_digest")
        span.set_attribute("job.window", "08-12")
        try:
            end = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
            start = end - timedelta(hours=4)
            await run_digest(start, end, "08-12")
        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            raise


async def send_rss_digest_16() -> None:
    with _tracer.start_as_current_span(
        "scheduler.rss_digest", kind=SpanKind.INTERNAL
    ) as span:
        span.set_attribute("job.name", "rss_digest")
        span.set_attribute("job.window", "12-16")
        try:
            end = datetime.now(UTC).replace(hour=16, minute=0, second=0, microsecond=0)
            start = end - timedelta(hours=4)
            await run_digest(start, end, "12-16")
        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            raise


async def send_rss_digest_20() -> None:
    with _tracer.start_as_current_span(
        "scheduler.rss_digest", kind=SpanKind.INTERNAL
    ) as span:
        span.set_attribute("job.name", "rss_digest")
        span.set_attribute("job.window", "16-20")
        try:
            end = datetime.now(UTC).replace(hour=20, minute=0, second=0, microsecond=0)
            start = end - timedelta(hours=4)
            await run_digest(start, end, "16-20")
        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            raise


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        consolidate_idle_threads,
        IntervalTrigger(minutes=5),
        id="consolidate_idle_threads",
        replace_existing=True,
    )
    scheduler.add_job(
        process_approval_timeouts,
        IntervalTrigger(minutes=1),
        id="process_approval_timeouts",
        replace_existing=True,
    )
    scheduler.add_job(
        send_morning_briefing,
        CronTrigger(hour=agent_config.morning_brief_hour, timezone="UTC"),
        id="morning_briefing",
        replace_existing=True,
    )
    scheduler.add_job(
        send_rss_digest_08,
        CronTrigger(hour=8, minute=0, timezone="UTC"),
        id="rss_digest_08",
        replace_existing=True,
    )
    scheduler.add_job(
        send_rss_digest_12,
        CronTrigger(hour=12, minute=0, timezone="UTC"),
        id="rss_digest_12",
        replace_existing=True,
    )
    scheduler.add_job(
        send_rss_digest_16,
        CronTrigger(hour=16, minute=0, timezone="UTC"),
        id="rss_digest_16",
        replace_existing=True,
    )
    scheduler.add_job(
        send_rss_digest_20,
        CronTrigger(hour=20, minute=0, timezone="UTC"),
        id="rss_digest_20",
        replace_existing=True,
    )
    return scheduler
