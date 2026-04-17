from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from mimir.agent.approval import manager as approval_manager
from mimir.config import config
from mimir.db import get_session
from mimir.scheduler.briefing.job import run_morning_briefing
from mimir.scheduler.memory.consolidate import consolidate_idle_threads


async def process_approval_timeouts() -> None:
    """Scheduled job (runs every minute) that auto-rejects timed-out approval requests."""
    async with get_session() as session:
        await approval_manager.process_timeouts(session)


async def send_morning_briefing() -> None:
    """Scheduled job: fetch today's calendar events and post a morning briefing to Slack."""
    await run_morning_briefing()


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
        CronTrigger(hour=config.morning_brief_hour, timezone="UTC"),
        id="morning_briefing",
        replace_existing=True,
    )
    return scheduler
