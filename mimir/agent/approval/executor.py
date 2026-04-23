from mimir.agent.dispatcher import tool_dispatcher
from mimir.models import PendingActionModel
from mimir.logger import logger


async def execute(action: PendingActionModel) -> str:
    """Execute an approved action. Raises on failure — caller must catch and notify user."""
    try:
        logger.debug(
            "execute: executing approved action", action=action.id, status=action.status
        )
        result = await _execute_tool_call(action.payload, action.id)
        return result
    except Exception as exc:
        logger.error(
            "approval_execution_failed",
            action_id=str(action.id),
            error=str(exc),
        )
        raise


async def _execute_tool_call(payload: dict, action_id) -> str:
    tool_name = payload.get("tool_name", "unknown")
    args = payload.get("arguments", {})
    # Inject action_id so the MCP @require_approval decorator can validate it
    dispatch_args = {**args, "action_id": str(action_id)}
    result = await tool_dispatcher.dispatch(tool_name, dispatch_args)
    return str(result)
