import functools
import inspect
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from mimir.db import get_session
from mimir.logger import logger
from mimir.models import ActionStatus, PendingActionModel


def require_approval(func):
    """Gate an MCP tool on an approved PendingActionModel.

    Injects an `action_id: str` parameter into the tool's signature.
    On call:
      - Fetches the row with SELECT FOR UPDATE; returns an error dict if not found
        or not in 'approved' status.
      - Executes the wrapped function.
      - Sets the action status to 'completed' on success, 'failed' on exception.
    """
    sig = inspect.signature(func)
    action_id_param = inspect.Parameter(
        "action_id",
        kind=inspect.Parameter.KEYWORD_ONLY,
        annotation=str,
    )
    new_sig = sig.replace(parameters=list(sig.parameters.values()) + [action_id_param])

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        if "action_id" not in kwargs:
            logger.error("require_approval: missing action_id in kwargs")
            return {"error": "Missing required parameter: action_id"}

        action_id = kwargs.pop("action_id")

        try:
            action_uuid = UUID(action_id)
        except ValueError:
            logger.error("require_approval: invalid action_id", action_id=action_id)
            return {"error": f"Invalid action_id format: {action_id}"}

        async with get_session() as session:
            result = await session.scalars(
                select(PendingActionModel)
                .where(
                    PendingActionModel.id == action_uuid,
                    PendingActionModel.status == ActionStatus.approved,
                )
                .with_for_update()
            )
            action = result.first()

            if action is None:
                logger.warning(
                    "require_approval: no approved action found",
                    action_id=action_id,
                )
                return {"error": f"No approved action found with id {action_id}."}

            try:
                tool_result = await func(*args, **kwargs)
                action.status = ActionStatus.completed
                action.resolved_at = datetime.now(UTC)
            except Exception as e:
                action.status = ActionStatus.failed
                action.resolved_at = datetime.now(UTC)
                logger.error(
                    "require_approval: tool execution failed",
                    action_id=action_id,
                    error=str(e),
                )
                return {"error": f"Tool execution failed: {e}"}
            finally:
                await session.commit()

        return tool_result

    wrapper.__signature__ = new_sig  # ty: ignore
    return wrapper
