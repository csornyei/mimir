from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shared.approvals import (
    create,
    get_by_id,
    get_by_message_ts,
    get_by_thread_ts,
    get_all,
    get_timed_out,
    set_status,
    set_discussing as _set_discussing,
)
from shared.models import ActionStatus, PendingActionModel
from agent_core.config import agent_config

__all__ = [
    "create",
    "get_by_id",
    "get_by_message_ts",
    "get_by_thread_ts",
    "get_all",
    "get_timed_out",
    "set_status",
    "set_discussing",
    "ActionStatus",
    "PendingActionModel",
]


async def set_discussing(
    session: AsyncSession, action_id: UUID, thread_ts: str
) -> None:
    """Transition to DISCUSSING, injecting timeout hours from agent config."""
    await _set_discussing(
        session,
        action_id,
        thread_ts,
        agent_config.approval_discuss_timeout_hours,
    )
