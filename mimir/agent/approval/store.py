from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mimir.models import ActionStatus, ActionType, PendingActionModel
from mimir.config import config


async def create(
    session: AsyncSession,
    *,
    action_type: ActionType,
    payload: dict,
    channel_id: str,
    message_ts: str,
    triggered_by: str,
    timeout_at: datetime | None,
    parent_id: UUID | None = None,
) -> PendingActionModel:
    action = PendingActionModel(
        action_type=action_type,
        status=ActionStatus.pending,
        payload=payload,
        channel_id=channel_id,
        message_ts=message_ts,
        triggered_by=triggered_by,
        timeout_at=timeout_at,
        parent_id=parent_id,
    )
    session.add(action)
    await session.flush()  # populate server-defaults (id, created_at)
    await session.refresh(action)
    return action


async def get_by_id(
    session: AsyncSession, action_id: UUID
) -> PendingActionModel | None:
    return await session.get(PendingActionModel, action_id)


async def get_by_message_ts(
    session: AsyncSession, message_ts: str
) -> PendingActionModel | None:
    result = await session.scalars(
        select(PendingActionModel).where(PendingActionModel.message_ts == message_ts)
    )
    return result.first()


async def get_by_thread_ts(
    session: AsyncSession, thread_ts: str
) -> PendingActionModel | None:
    """Return the most recent non-terminal action for the given thread_ts."""
    result = await session.scalars(
        select(PendingActionModel)
        .where(
            PendingActionModel.thread_ts == thread_ts,
            PendingActionModel.status.in_(
                [ActionStatus.pending, ActionStatus.discussing]
            ),
        )
        .order_by(PendingActionModel.created_at.desc())
        .limit(1)
    )
    return result.first()


async def get_all(
    session: AsyncSession,
    message_ts: str | None = None,
    thread_ts: str | None = None,
    timed_out: bool = False,
) -> list[PendingActionModel]:
    """List actions with optional filters. Used by the admin API."""
    stmt = select(PendingActionModel)
    if message_ts is not None:
        stmt = stmt.where(PendingActionModel.message_ts == message_ts)
    if thread_ts is not None:
        stmt = stmt.where(PendingActionModel.thread_ts == thread_ts)
    if timed_out:
        now = datetime.now(UTC)
        stmt = stmt.where(
            PendingActionModel.status.in_(
                [ActionStatus.pending, ActionStatus.discussing]
            ),
            PendingActionModel.timeout_at <= now,
        )
    result = await session.scalars(stmt.order_by(PendingActionModel.created_at.desc()))
    return list(result.all())


async def get_timed_out(session: AsyncSession) -> list[PendingActionModel]:
    """Return all non-terminal actions whose timeout_at has passed."""
    now = datetime.now(UTC)
    result = await session.scalars(
        select(PendingActionModel).where(
            PendingActionModel.status.in_(
                [ActionStatus.pending, ActionStatus.discussing]
            ),
            PendingActionModel.timeout_at.is_not(None),
            PendingActionModel.timeout_at <= now,
        )
    )
    return list(result.all())


async def set_status(
    session: AsyncSession,
    action_id: UUID,
    status: ActionStatus,
    resolved_at: datetime | None = None,
) -> None:
    action = await session.get(PendingActionModel, action_id)
    if action is None:
        return
    action.status = status
    if resolved_at is not None:
        action.resolved_at = resolved_at


async def set_discussing(
    session: AsyncSession, action_id: UUID, thread_ts: str
) -> None:
    """Transition to DISCUSSING: set thread_ts and update timeout."""
    action = await session.get(PendingActionModel, action_id)
    if action is None:
        return
    action.status = ActionStatus.discussing
    action.thread_ts = thread_ts
    if config.approval_discuss_timeout_hours > 0:
        action.timeout_at = datetime.now(UTC) + timedelta(
            hours=config.approval_discuss_timeout_hours
        )
    else:
        action.timeout_at = None
