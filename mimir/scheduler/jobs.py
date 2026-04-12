from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update

from mimir.agent.approval import manager as approval_manager
from mimir.config import config
from mimir.db import get_session
from mimir.logger import logger
from mimir.memory.episodic import EpisodicMemory
from mimir.models import ConversationModel, MessageModel


async def consolidate_idle_threads() -> None:
    """
    Scheduled job (runs every 5 minutes) that finds conversations eligible for
    consolidation and writes episodic memory summaries.

    Two cases are handled:
    - Fresh: never consolidated, idle for episodic_idle_minutes, under the retry limit.
    - Re-consolidation: already consolidated but new messages arrived since then.
    """
    cutoff = datetime.now(UTC) - timedelta(minutes=config.episodic_idle_minutes)

    fresh_ids: list[str] = []
    re_consolidation_ids: list[str] = []

    async with get_session() as session:
        # Case A — never consolidated.
        fresh_rows = await session.scalars(
            select(ConversationModel).where(
                ConversationModel.last_active < cutoff,
                ConversationModel.consolidated_at.is_(None),
                ConversationModel.consolidation_retries < config.episodic_max_retries,
            )
        )
        fresh_ids = [c.id for c in fresh_rows.all()]

        # Case B — previously consolidated; check for new messages.
        prev_rows = await session.scalars(
            select(ConversationModel).where(
                ConversationModel.last_active < cutoff,
                ConversationModel.consolidated_at.is_not(None),
                ConversationModel.consolidation_retries < config.episodic_max_retries,
            )
        )
        for conv in prev_rows.all():
            new_count = await session.scalar(
                select(func.count()).where(
                    MessageModel.conversation_id == conv.id,
                    MessageModel.timestamp > conv.consolidated_at,
                )
            )
            if new_count is None:
                continue
            if new_count >= config.episodic_new_messages_threshold:
                re_consolidation_ids.append(conv.id)

    all_ids = fresh_ids + re_consolidation_ids
    if not all_ids:
        return

    logger.info(
        "consolidation_job_start",
        fresh=len(fresh_ids),
        re_consolidation=len(re_consolidation_ids),
    )

    for thread_id in all_ids:
        async with get_session() as session:
            memory = EpisodicMemory(session)
            try:
                consolidated = await memory.consolidate(thread_id)
                if consolidated:
                    logger.info("consolidated_thread", thread_id=thread_id)
            except Exception as e:
                logger.error("consolidation_failed", thread_id=thread_id, error=str(e))
                await session.execute(
                    update(ConversationModel)
                    .where(ConversationModel.id == thread_id)
                    .values(
                        consolidation_retries=ConversationModel.consolidation_retries
                        + 1
                    )
                )
                await session.commit()


async def process_approval_timeouts() -> None:
    """Scheduled job (runs every minute) that auto-rejects timed-out approval requests."""
    async with get_session() as session:
        await approval_manager.process_timeouts(session)
