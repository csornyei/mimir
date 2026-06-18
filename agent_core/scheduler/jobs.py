from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from opentelemetry import trace
from opentelemetry.trace import SpanKind, StatusCode

from agent_core.agent.approval import manager as approval_manager
from agent_core.scheduler.memory.consolidate import consolidate_idle_threads
from shared.db import get_session

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
    return scheduler
