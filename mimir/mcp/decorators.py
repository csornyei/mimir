import functools
import inspect
from datetime import UTC, datetime
from uuid import UUID

from mcp.types import ToolAnnotations
from sqlalchemy import select

from mimir.db import get_session
from mimir.logger import logger
from mimir.models import ActionStatus, PendingActionModel
from mimir.mcp.app import mcp


def write_tool(func):
    """Register an MCP tool that requires user approval before execution.

    Replaces @mcp.tool() + @require_approval. Sets destructiveHint=True so the
    agent can detect write tools from the schema without any config.
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
            logger.error("write_tool: missing action_id in kwargs")
            return {"error": "Missing required parameter: action_id"}

        action_id = kwargs.pop("action_id")
        logger.debug(
            "write_tool_called",
            tool_name=func.__name__,
            args=args,
            kwargs=kwargs,
            action_id=action_id,
        )

        try:
            action_uuid = UUID(action_id)
        except ValueError:
            logger.error("write_tool: invalid action_id", action_id=action_id)
            return {"error": f"Invalid action_id format: {action_id}"}

        async with get_session() as session:
            logger.debug(
                "write_tool: querying for approved action", action_id=action_id
            )
            result = await session.scalars(
                select(PendingActionModel)
                .where(
                    PendingActionModel.id == action_uuid,
                    PendingActionModel.status == ActionStatus.approved,
                )
                .with_for_update()
            )
            action = result.first()

            logger.debug(
                "write_tool: action query result",
                action_id=action_id,
                action_found=action is not None,
            )

            if action is None:
                logger.warning(
                    "write_tool: no approved action found",
                    action_id=action_id,
                )
                return {"error": f"No approved action found with id {action_id}."}

            try:
                tool_result = await func(*args, **kwargs)
                logger.debug(
                    "write_tool: tool execution succeeded",
                    action_id=action_id,
                )
            except Exception as e:
                logger.error(
                    "write_tool: tool execution failed",
                    action_id=action_id,
                    error=str(e),
                )
                return {"error": f"Tool execution failed: {e}"}
            finally:
                await session.commit()

        return tool_result

    wrapper.__signature__ = new_sig  # ty: ignore
    return mcp.tool(annotations=ToolAnnotations(destructiveHint=True))(wrapper)
