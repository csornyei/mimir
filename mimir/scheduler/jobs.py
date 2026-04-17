from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from mimir.agent.approval import manager as approval_manager
from mimir.config import config
from mimir.db import get_session
from mimir.scheduler.briefing.job import run_morning_briefing
from mimir.scheduler.memory.consolidate import consolidate_idle_threads
from mimir.scheduler.rss.job import run_digest


async def process_approval_timeouts() -> None:
    """Scheduled job (runs every minute) that auto-rejects timed-out approval requests."""
    async with get_session() as session:
        await approval_manager.process_timeouts(session)


async def send_morning_briefing() -> None:
    """Scheduled job: fetch today's calendar events and post a morning briefing to Slack."""
    await run_morning_briefing()


async def send_rss_digest_08() -> None:
    """Scheduled job: fetch overnight articles (20:00 → 08:00) and post digest."""
    now = datetime.now(UTC)
    end = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if end > now:
        end -= timedelta(days=1)
    start = end - timedelta(hours=12)
    await run_digest(start, end, "20-08")


async def send_rss_digest_12() -> None:
    """Scheduled job: fetch morning articles (08:00 → 12:00) and post digest."""
    end = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=4)
    await run_digest(start, end, "08-12")


async def send_rss_digest_16() -> None:
    """Scheduled job: fetch midday articles (12:00 → 16:00) and post digest."""
    end = datetime.now(UTC).replace(hour=16, minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=4)
    await run_digest(start, end, "12-16")


async def send_rss_digest_20() -> None:
    """Scheduled job: fetch afternoon articles (16:00 → 20:00) and post digest."""
    end = datetime.now(UTC).replace(hour=20, minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=4)
    await run_digest(start, end, "16-20")


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
